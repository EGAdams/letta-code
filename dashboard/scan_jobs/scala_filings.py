"""Scala's filing of a scan, read from her ledger by content hash.

Scala, the scanner clerk, watches the folder the dashboard stages scans into
and files every page she can (bills, documents), hands receipts and statements
to Mazda, and puts what she cannot place into her inbox with a question for
EG. She writes one line per scan to `~/scala/ledger.jsonl`, keyed by the
sha256 of the staged bytes -- the same bytes as the scan's artifact, so a job
finds its own line by hash and never by "the latest one".

The ledger is hers: this only reads it, bounded, and returns no paths.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from scan_jobs.models import ScalaSummary, ScanRecord, rfc3339

_DECISIONS = {'filed': 'filed', 'inbox': 'inbox', 'mazda': 'handed_to_mazda',
              'duplicate': 'duplicate', 'error': 'error'}
TAIL_BYTES = 4 * 1024 * 1024          # the last few thousand filings; older scans are long settled


def _clip(value: object, limit: int) -> Optional[str]:
    text = ' '.join(str(value).split()) if value not in (None, '') else ''
    return (text[:limit - 1] + '…' if len(text) > limit else text) or None


def _iso_ns(value: str) -> int:
    return int(datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp() * 1e9)


class LedgerScalaFilings:
    def __init__(self, ledger_path: Path, pending_window_seconds: int = 900,
                 clock_ns: Callable[[], int] = time.time_ns):
        self._path = Path(ledger_path)
        self._window_ns = pending_window_seconds * 10**9
        self._clock = clock_ns

    def summarize(self, record: ScanRecord) -> ScalaSummary:
        if record.status != 'captured' or record.artifact is None:
            return ScalaSummary(status='not_requested')
        lines = self._lines_for(record.artifact.sha256)
        if lines:
            return self._from_line(lines[-1], earlier=lines[:-1])
        age = self._clock() - _iso_ns(record.artifact.captured_at)
        if age < self._window_ns:
            return ScalaSummary(status='pending', updated_at=rfc3339(self._clock()))
        return ScalaSummary(status='unavailable', updated_at=rfc3339(self._clock()),
                            warnings=('Scala has no ledger line for this scan; her watcher may be stopped.',))

    def _lines_for(self, sha256: str) -> list[dict]:
        try:
            with open(self._path, 'rb') as fh:
                fh.seek(0, 2)
                size = fh.tell()
                fh.seek(max(0, size - TAIL_BYTES))
                raw = fh.read(TAIL_BYTES)
        except OSError:
            return []
        found = []
        for line in raw.splitlines():
            if sha256.encode() not in line:
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if isinstance(entry, dict) and entry.get('sha256') == sha256:
                found.append(entry)
        return found

    @staticmethod
    def _from_line(entry: dict, earlier: list[dict]) -> ScalaSummary:
        status = _DECISIONS.get(str(entry.get('decision') or ''), 'error')
        folder = entry.get('folder')
        if status == 'duplicate':                     # where the first copy went
            folder = next((e.get('folder') for e in reversed(earlier) if e.get('decision') == 'filed'), folder)
        if status != 'filed' and status != 'duplicate':
            folder = None                             # "unsure" and the like are not folders
        try:
            confidence = min(1.0, max(0.0, float(entry.get('confidence'))))
        except (TypeError, ValueError):
            confidence = None
        return ScalaSummary(status=status, folder=_clip(folder, 120), method=_clip(entry.get('method'), 40),
                            confidence=confidence, reason=_clip(entry.get('reason'), 400),
                            updated_at=_clip(entry.get('at'), 40))
