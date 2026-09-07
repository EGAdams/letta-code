"""Persistence for watchdog actions -- so Server Management can show what was
killed and why, even though the killed process obviously cannot report on
itself. Same shape as `claude_sdk_usage_store.py`: one small JSON file,
atomically rewritten, corrupt-or-missing means empty rather than an
exception, because losing this history must never take down a page.
"""

from __future__ import annotations

import json
import os
import threading
from typing import List, Optional

from pydantic import ValidationError

from health.codex_watchdog_contracts import IWatchdogActionStore, WatchdogAction

_MAX_RETAINED = 200


class JsonFileWatchdogActionStore(IWatchdogActionStore):
    def __init__(self, path: str) -> None:
        self._path = path
        self._lock = threading.Lock()

    def record(self, action: WatchdogAction) -> None:
        with self._lock:
            existing = self._read_unlocked()
            existing.append(action)
            self._write_unlocked(existing[-_MAX_RETAINED:])

    def recent(self, limit: int = 50) -> List[WatchdogAction]:
        with self._lock:
            return self._read_unlocked()[-limit:]

    def _read_unlocked(self) -> List[WatchdogAction]:
        try:
            with open(self._path, encoding='utf-8') as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return []
        rows = data.get('actions') if isinstance(data, dict) else None
        if not isinstance(rows, list):
            return []
        actions = []
        for row in rows:
            try:
                actions.append(WatchdogAction.model_validate(row))
            except ValidationError:
                continue
        return actions

    def _write_unlocked(self, actions: List[WatchdogAction]) -> None:
        directory = os.path.dirname(self._path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        payload = {'actions': [a.model_dump(mode='json') for a in actions]}
        tmp = f'{self._path}.tmp.{os.getpid()}'
        try:
            with open(tmp, 'w', encoding='utf-8') as handle:
                json.dump(payload, handle)
            os.replace(tmp, self._path)
        except OSError:
            pass


class InMemoryWatchdogActionStore(IWatchdogActionStore):
    """For tests, and for a box that would rather not keep the history."""

    def __init__(self) -> None:
        self._actions: List[WatchdogAction] = []
        self._lock = threading.Lock()

    def record(self, action: WatchdogAction) -> None:
        with self._lock:
            self._actions.append(action)

    def recent(self, limit: int = 50) -> List[WatchdogAction]:
        with self._lock:
            return list(self._actions[-limit:])


def default_store(path: Optional[str] = None) -> IWatchdogActionStore:
    """The live wiring: ~/.mazda, beside the other small watchdog state."""
    return JsonFileWatchdogActionStore(
        path or os.path.expanduser('~/.mazda/codex_watchdog_actions.json'))
