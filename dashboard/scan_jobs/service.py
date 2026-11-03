"""ScanJobService: one durable job per physical scan, for the dashboard and the bridge alike.

`run_recorded` is the dashboard button: synchronous, returns the legacy result
dict (plus `scan_id`) so the browser behaves exactly as before. `start` is the
bridge: validated, idempotent, rate-limited, refused while the scanner is
busy or the feature flag is off, and run on a background thread.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

from scan_jobs.artifact_store import ArtifactError
from scan_jobs.document_reader import DocumentError
from scan_jobs.models import (SCANNER_KEYS, ArtifactInfo, BridgeSettings, PageText, RenderedPage,
                              ScanRecord, new_scan_id, rfc3339)
from scan_jobs.ports import (IMazdaVerdictProvider, IScanArtifactStore, IScanDocumentReader,
                             IScanJobRepository, IScannerController)
from scan_jobs.repository import ScanNotFound
from scan_jobs.rendition_cache import RenditionCache

log = logging.getLogger('scan_jobs')

_LEGACY_ERROR_CODES = {'busy': 'device_busy', 'offline': 'device_offline',
                       'not_configured': 'not_configured', 'intake_busy': 'intake_busy'}


class StartRefused(Exception):
    """A bridge start that will not run. `code` and `http` go straight to the API."""

    def __init__(self, code: str, message: str, http: int, retry_after: Optional[int] = None,
                 scan_id: Optional[str] = None):
        super().__init__(message)
        self.code, self.http, self.retry_after, self.scan_id = code, http, retry_after, scan_id


class ScanJobService:
    def __init__(self, repo: IScanJobRepository, store: IScanArtifactStore, controller: IScannerController,
                 reader: IScanDocumentReader, verdicts: IMazdaVerdictProvider,
                 settings: Callable[[], BridgeSettings], clock_ns: Callable[[], int] = time.time_ns,
                 spawn: Callable[[Callable[[], None]], None] | None = None):
        self._repo, self._store, self._controller = repo, store, controller
        self._renditions = RenditionCache(store)        # .jpg files over the same store
        self._reader, self._verdicts, self._settings, self._clock = reader, verdicts, settings, clock_ns
        self._spawn = spawn or (lambda fn: threading.Thread(target=fn, daemon=True, name='scan-job').start())
        self._locks = {key: threading.Lock() for key in SCANNER_KEYS}
        self._start_lock = threading.Lock()

    # -- starting ------------------------------------------------------------------
    def run_recorded(self, key: str) -> dict:
        """The dashboard button. Never worse than the old path: any job-layer
        failure before the scan falls back to it, and any after it is logged."""
        if key not in SCANNER_KEYS:
            return self._controller.run(key)           # the legacy path owns unknown-key errors
        with self._locks[key]:
            try:
                record, _ = self._create(key, 'dashboard', 'dashboard', None, refuse_if_active=False)
            except Exception:  # noqa: BLE001
                log.exception('scan job store unavailable; scanning without a job record')
                return self._controller.run(key)
            return self._execute(record)

    def start(self, scanner: str, requester: str, idempotency_key: Optional[str]) -> tuple[ScanRecord, bool]:
        if scanner not in SCANNER_KEYS:
            raise StartRefused('invalid_scanner', 'scanner must be "window" or "freezer"', 400)
        with self._start_lock:
            settings = self._settings()
            idem = (f'{requester}:start', idempotency_key) if idempotency_key else None
            if not settings.bridge_start_enabled:
                self._repo.audit(None, requester, 'start_refused', 'bridge_scans_disabled')
                raise StartRefused('bridge_scans_disabled',
                                   'Bridge scans are switched off on this machine (scan_bridge settings).', 403)
            self._enforce_rate(scanner, settings, requester, idem)
            try:
                record, created = self._create(scanner, 'bridge', requester, idem, refuse_if_active=True)
            except Exception as exc:
                busy_id = getattr(exc, 'scan_id', None)
                if busy_id:
                    raise StartRefused('scanner_busy', 'That scanner already has a scan in progress.', 409,
                                       scan_id=busy_id) from exc
                raise
        if created:
            self._repo.audit(record.scan_id, requester, 'start_accepted', scanner)
            self._spawn(lambda: self._run_bridge(record))
        else:
            self._repo.audit(record.scan_id, requester, 'start_replayed', scanner)
        return record, created

    def _enforce_rate(self, scanner: str, settings: BridgeSettings, requester: str,
                      idem: Optional[tuple[str, str]]) -> None:
        if idem and self._repo.idempotent_scan_id(*idem):
            return                                       # a replay never counts against the limit
        now = self._clock()
        recent = self._repo.bridge_starts_since(now - settings.min_seconds_between_bridge_scans * 10**9, scanner)
        if recent:
            wait = settings.min_seconds_between_bridge_scans - (now - recent[-1]) // 10**9
            self._repo.audit(None, requester, 'start_refused', 'rate_limited')
            raise StartRefused('rate_limited', 'Too soon after the last bridge scan on this scanner.', 429,
                               retry_after=max(1, int(wait)))
        hour = self._repo.bridge_starts_since(now - 3600 * 10**9, None)
        if len(hour) >= settings.max_bridge_scans_per_hour:
            self._repo.audit(None, requester, 'start_refused', 'rate_limited_hourly')
            raise StartRefused('rate_limited', 'The hourly bridge-scan limit has been reached.', 429,
                               retry_after=max(1, int(3600 - (now - hour[0]) // 10**9)))

    def _create(self, key: str, source: str, requester: str, idem: Optional[tuple[str, str]],
                refuse_if_active: bool) -> tuple[ScanRecord, bool]:
        now = self._clock()
        stamp = rfc3339(now)
        record = ScanRecord(scan_id=new_scan_id(now), scanner=key, scanner_name=self._controller.scanner_name(key),
                            source=source, requester=requester, status='queued', created_at=stamp,
                            updated_at=stamp)
        return self._repo.create(record, now, idem, refuse_if_active)

    def _run_bridge(self, record: ScanRecord) -> None:
        try:
            with self._locks[record.scanner]:
                self._execute(record)
        except Exception:  # noqa: BLE001 -- a background thread has nobody to raise to
            log.exception('bridge scan %s crashed', record.scan_id)

    # -- running -------------------------------------------------------------------
    def _execute(self, record: ScanRecord) -> dict:
        """Caller holds this scanner's lock. Returns the legacy result dict."""
        started_ns = self._clock()
        try:
            self._repo.transition(record.scan_id, 'scanning', started_at=rfc3339(started_ns))
        except Exception:  # noqa: BLE001
            log.exception('could not mark %s scanning; scanning anyway', record.scan_id)
        try:
            result = self._controller.run(record.scanner)
        except Exception as exc:
            self._finish_failed(record.scan_id, 'failed', 'scanner_error', f'scan raised: {type(exc).__name__}')
            raise
        if not isinstance(result, dict):
            self._finish_failed(record.scan_id, 'failed', 'scanner_error', 'scanner returned no result')
            return result
        try:
            self._record_outcome(record, result, started_ns)
        except Exception:  # noqa: BLE001 -- the scan itself happened; never lose its legacy result
            log.exception('could not record the outcome of %s', record.scan_id)
        return {**result, 'scan_id': record.scan_id}

    def _record_outcome(self, record: ScanRecord, result: dict, started_ns: int) -> None:
        status = result.get('status')
        if status == 'ready' and result.get('ok', True):
            path = self._controller.output_path(record.scanner)
            try:
                if not path:
                    raise ArtifactError('capture_failed', 'scanner has no output path')
                sha, mime, size = self._store.put_file(path, not_before_ns=started_ns - 2 * 10**9)
                pages = self._reader.page_count(self._store.read(sha), mime)
            except (ArtifactError, DocumentError) as exc:
                self._finish_failed(record.scan_id, 'failed', exc.code, str(exc))
                return
            now = rfc3339(self._clock())
            artifact = ArtifactInfo(sha256=sha, mime_type=mime, size_bytes=size, page_count=pages, captured_at=now)
            self._repo.transition(record.scan_id, 'captured', finished_at=now, artifact=artifact.model_dump(),
                                  mazda={'status': 'pending', 'updated_at': now})
            return
        error = str(result.get('error') or '')[:500] or None
        if result.get('empty_output'):
            code = 'empty_output'
        elif 'timed out' in (error or '').lower():
            return self._finish_failed(record.scan_id, 'timed_out', 'timeout', error)
        else:
            code = _LEGACY_ERROR_CODES.get(status, 'scanner_error')
        self._finish_failed(record.scan_id, 'failed', code, error)

    def _finish_failed(self, scan_id: str, status: str, code: str, error: Optional[str]) -> None:
        try:
            self._repo.transition(scan_id, status, finished_at=rfc3339(self._clock()), error_code=code,
                                  error=(error or code)[:500])
        except Exception:  # noqa: BLE001
            log.exception('could not record failure of %s', scan_id)

    # -- reading -------------------------------------------------------------------
    def get(self, scan_id: str) -> ScanRecord:
        record = self._repo.get(scan_id)
        if record is None:
            raise ScanNotFound(scan_id)
        return self._refresh_mazda(record)

    def list_recent(self, limit: int, cursor: Optional[str]) -> tuple[list[ScanRecord], Optional[str]]:
        return self._repo.list_recent(limit, cursor)

    def mazda(self, scan_id: str) -> ScanRecord:
        return self.get(scan_id)

    def original(self, scan_id: str) -> tuple[ScanRecord, bytes]:
        record = self._captured(scan_id)
        return record, self._store.read(record.artifact.sha256)

    def page(self, scan_id: str, page: int, rendition: str) -> tuple[ScanRecord, RenderedPage]:
        record, data = self.original(scan_id)
        if rendition not in ('preview', 'full'):
            raise DocumentError('invalid_rendition', 'rendition must be preview or full')
        sha = record.artifact.sha256
        cached = self._renditions.get(sha, page, rendition, data)
        if cached:
            return record, cached
        rendered = self._reader.render_page(data, record.artifact.mime_type, page, rendition)
        self._renditions.put(sha, rendered, data)
        return record, rendered

    def text(self, scan_id: str, page: int) -> tuple[ScanRecord, PageText]:
        record, data = self.original(scan_id)
        name = f'text_p{page}_upright.json'   # pre-rotation entries are not reused
        cached = self._store.get_derived(record.artifact.sha256, name)
        if cached:
            return record, PageText.model_validate_json(cached)
        text = self._reader.page_text(data, record.artifact.mime_type, page)
        if text.source != 'none':
            self._store.put_derived(record.artifact.sha256, name, text.model_dump_json().encode())
        return record, text

    def _captured(self, scan_id: str) -> ScanRecord:
        record = self.get(scan_id)
        if record.status != 'captured' or record.artifact is None:
            raise DocumentError('document_unavailable', f'scan is {record.status}; it has no document')
        return record

    def _refresh_mazda(self, record: ScanRecord) -> ScanRecord:
        if record.status != 'captured' or record.mazda.status in ('completed', 'failed'):
            return record
        summary = self._verdicts.summarize(record)
        if summary.model_dump(exclude={'updated_at'}) == record.mazda.model_dump(exclude={'updated_at'}):
            return record
        try:
            return self._repo.set_mazda(record.scan_id, summary)
        except Exception:  # noqa: BLE001 -- answer with the fresh view even if the snapshot failed
            log.exception('could not snapshot Mazda outcome for %s', record.scan_id)
            return record.model_copy(update={'mazda': summary})


def load_settings(path) -> BridgeSettings:
    """Missing or malformed settings mean the safe default: bridge scans off."""
    try:
        with open(path, encoding='utf-8') as fh:
            return BridgeSettings.model_validate_json(fh.read())
    except (OSError, ValueError):
        return BridgeSettings()
