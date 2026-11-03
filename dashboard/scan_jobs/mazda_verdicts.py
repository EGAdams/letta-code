"""Mazda's outcome for a scan, matched by content hash -- never by "the latest one".

The intake store keeps one record per physical scanner, which the next scan
replaces. A job therefore asks for the scanner's current intake and accepts it
only when its `content_sha256` equals the job's own artifact hash; the service
snapshots a terminal outcome into the job, so it survives the next scan.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Callable, Optional

from intake.scala_handoff import LEFT_FOR_SCALA_PREFIX
from scan_jobs.models import MazdaSummary, ScanRecord, rfc3339

_COMPLETED = frozenset({'pass', 'corrected', 'complete', 'awaiting_vendor_review', 'needs_human_review'})
_FAILED = frozenset({'fail', 'stalled'})
DETAIL_LIMIT = 500
#: What Mazda's books take. Anything else is Scala's to file, so Mazda "failing" it is not a failure.
MAZDA_KINDS = frozenset({'receipt', 'statement', 'bank_statement', 'moms_ledger', 'invoice'})
OUT_OF_SCOPE = 'Not a financial document, so it is outside Mazda\'s scope; Scala, the scanner clerk, files it.'

IntakeLookup = Callable[[str], Optional[dict]]


def _clip(value: object, limit: int = 120) -> Optional[str]:
    text = ' '.join(str(value).split()) if value not in (None, '') else ''
    return (text[:limit - 1] + '…' if len(text) > limit else text) or None


def _iso_ns(value: str) -> int:
    return int(datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp() * 1e9)


class IntakeMazdaVerdicts:
    def __init__(self, intake_lookup: IntakeLookup, pending_window_seconds: int = 900,
                 clock_ns: Callable[[], int] = time.time_ns):
        self._lookup = intake_lookup
        self._window_ns = pending_window_seconds * 10**9
        self._clock = clock_ns

    def summarize(self, record: ScanRecord) -> MazdaSummary:
        if record.status != 'captured' or record.artifact is None:
            return MazdaSummary(status='not_requested')
        if record.mazda.status in ('completed', 'failed'):
            return record.mazda                        # snapshotted earlier; the intake may have moved on
        try:
            intake = self._lookup(record.scanner) or {}
        except Exception:  # noqa: BLE001 -- an unreadable intake store is "no answer yet"
            intake = {}
        if intake.get('content_sha256') == record.artifact.sha256:
            return self._from_intake(intake)
        age = self._clock() - _iso_ns(record.artifact.captured_at)
        if age < self._window_ns:
            return MazdaSummary(status='pending', updated_at=rfc3339(self._clock()))
        return MazdaSummary(status='unavailable', updated_at=rfc3339(self._clock()),
                            warnings=('No Mazda intake was found for this scan\'s image. It may have been '
                                      'rejected before dispatch (e.g. a blank page) or superseded.',))

    def _from_intake(self, intake: dict) -> MazdaSummary:
        raw = str(intake.get('status') or '').strip().lower()
        if raw in _COMPLETED:
            status = 'completed'
        elif raw in _FAILED:
            status = 'failed'
        else:
            status = 'running'
        kind = _clip(intake.get('doc_kind'), 60)
        if str(intake.get('status_detail') or '').startswith(LEFT_FOR_SCALA_PREFIX):
            return MazdaSummary(status='completed', outcome='out_of_scope', doc_kind=kind,
                                detail=_clip(intake.get('status_detail'), DETAIL_LIMIT),
                                updated_at=rfc3339(self._clock()))     # her turn was skipped
        if status == 'failed' and (kind or 'unknown').lower() not in MAZDA_KINDS:
            return MazdaSummary(status='completed', outcome='out_of_scope', doc_kind=kind,
                                vendor=_clip(intake.get('vendor'), 120), detail=OUT_OF_SCOPE,
                                updated_at=rfc3339(self._clock()),
                                warnings=(f'Mazda\'s finance checks said {_clip(raw, 40)}; they apply to receipts '
                                          'and statements only.',))
        return MazdaSummary(
            status=status,
            outcome=_clip(raw, 40) if status != 'running' else None,
            doc_kind=_clip(intake.get('doc_kind'), 60),
            vendor=_clip(intake.get('vendor'), 120),
            detail=_clip(intake.get('status_detail'), DETAIL_LIMIT),
            updated_at=rfc3339(self._clock()),
        )
