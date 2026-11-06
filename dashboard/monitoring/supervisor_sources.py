"""Read-only ledger Adapter strategies. Neither adapter calls a worker API."""
from __future__ import annotations

import importlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from monitoring.supervisor_contracts import LedgerObservation, TaskObservation


class FileLedgerReader:
    def __init__(self, path: Path, stale_seconds: float = 60) -> None:
        self.path = path
        self.stale_seconds = stale_seconds

    def read(self, now: float) -> LedgerObservation:
        try:
            stat = self.path.stat()
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return LedgerObservation(error=f"worker task ledger not present at {self.path}")
        except (OSError, ValueError):
            return LedgerObservation(error="worker task ledger could not be read")
        if not isinstance(raw, list):
            return LedgerObservation(error="worker task ledger has an invalid shape", updated_at=stat.st_mtime)
        try:
            tasks = [TaskObservation.model_validate(row) for row in raw]
        except ValidationError:
            return LedgerObservation(error="worker task ledger has invalid task fields", updated_at=stat.st_mtime)
        if len({task.id for task in tasks}) != len(tasks):
            return LedgerObservation(error="worker task ledger has duplicate task IDs", updated_at=stat.st_mtime)
        stale = now - stat.st_mtime > self.stale_seconds or stat.st_mtime > now + 5
        return LedgerObservation(tasks=tasks, updated_at=stat.st_mtime, stale=stale,
                                 source="local-snapshot", error="worker task ledger is stale or clock-skewed" if stale else None)


class PostOfficeLedgerReader:
    """Rebuild from durable envelopes/events ourselves, even if the worker is dead.

    Reuses the existing row builder without invoking its snapshot writer. The
    imported module's concrete directories stay at this composition boundary.
    """
    def __init__(self, package_root: Path) -> None:
        self.package_root = package_root

    def read(self, now: float) -> LedgerObservation:
        if str(self.package_root) not in sys.path:
            sys.path.insert(0, str(self.package_root))
        try:
            source = importlib.import_module("agent_bridge_worker.activity_snapshot")
            if not source.MAILBOX_ROOT.is_dir():
                return LedgerObservation(error="local post office is not present")
            # build_rows normally truncates for the dashboard. This observer
            # must not silently lose queued tasks behind a display limit.
            rows = source.build_rows(root=source.MAILBOX_ROOT, workspaces_file=source.WORKSPACES_FILE, now=datetime.fromtimestamp(now, timezone.utc), limit=10001,
                                     notes_log=source.NOTES_LOG)
            truncated = len(rows) > 10000
            return LedgerObservation(
                tasks=[TaskObservation.model_validate(row.model_dump()) for row in rows[:10000]],
                source="local-post-office", updated_at=now, stale=False,
                error="local task limit (10000) reached; coverage truncated" if truncated else None,
            )
        except (ImportError, OSError, ValueError, TypeError):
            return LedgerObservation(error="local post office could not be read; check package path and environment")
