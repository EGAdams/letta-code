"""The one place pause_control names concretes. Built lazily, once per
process; `reset()` exists for tests."""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Optional

from pause_control.auth import EnvBearerAuthorizer
from pause_control.pausability import ConfiguredTaskPausability
from pause_control.repository import SqliteControlLedger
from pause_control.service import PauseControlService

_lock = threading.Lock()
_built: Optional[tuple[PauseControlService, EnvBearerAuthorizer]] = None


def data_dir() -> Path:
    return Path(os.environ.get('PAUSE_CONTROL_DIR') or Path.home() / '.local/share/pause_control')


def _allowlist(name: str) -> frozenset[str]:
    raw = os.environ.get(name, '')
    return frozenset(v.strip() for v in raw.split(',') if v.strip())


def _build() -> tuple[PauseControlService, EnvBearerAuthorizer]:
    ledger = SqliteControlLedger(data_dir() / 'pause_control.sqlite3')
    pausability = ConfiguredTaskPausability(
        pausable=_allowlist('PAUSE_CONTROL_PAUSABLE_TASK_IDS'),
        not_pausable=_allowlist('PAUSE_CONTROL_NOT_PAUSABLE_TASK_IDS'))
    return PauseControlService(ledger, pausability), EnvBearerAuthorizer()


def _get() -> tuple[PauseControlService, EnvBearerAuthorizer]:
    global _built
    with _lock:
        if _built is None:
            _built = _build()
        return _built


def service() -> PauseControlService:
    return _get()[0]


def authorizer() -> EnvBearerAuthorizer:
    return _get()[1]


def reset() -> None:
    global _built
    with _lock:
        _built = None
