from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class IIntakeEventStore(Protocol):
    def read(self) -> dict[str, Any]:
        raise NotImplementedError

    def write(self, payload: dict[str, Any]) -> str:
        raise NotImplementedError

    def snapshot(self) -> str:
        raise NotImplementedError


class JsonIntakeEventStore(IIntakeEventStore):
    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._lock = threading.Lock()

    def _read_raw(self) -> dict[str, Any]:
        try:
            with self._path.open(encoding='utf-8') as handle:
                data = json.load(handle)
        except (OSError, ValueError, TypeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _atomic_write(self, payload: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(self._path.suffix + '.tmp')
        with temporary.open('w', encoding='utf-8') as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write('\n')
        os.replace(temporary, self._path)

    def _stable_state(self, payload: dict[str, Any]) -> str:
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(',', ':'),
            ensure_ascii=True,
        )

    def read(self) -> dict[str, Any]:
        with self._lock:
            return self._read_raw()

    def write(self, payload: dict[str, Any]) -> str:
        if not isinstance(payload, dict):
            raise TypeError('payload must be a dict')
        with self._lock:
            persisted = dict(payload)
            self._atomic_write(persisted)
            digest = hashlib.sha256(
                self._stable_state(persisted).encode('utf-8')
            ).hexdigest()
        return f'intake:{digest}'

    def snapshot(self) -> str:
        with self._lock:
            data = self._read_raw()
        digest = hashlib.sha256(self._stable_state(data).encode('utf-8')).hexdigest()
        return f'intake:{digest}'
