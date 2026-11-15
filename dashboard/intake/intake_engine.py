"""Which engine takes the next Automatic document.

``mazda_agent`` is the earlier path: the Mazda agent's eight-step turn.
``finance_workflow`` is the finance application's own workflow (see
``intake.finance_workflow_dispatch``). The default is the earlier engine, so
nothing changes on a box until someone chooses otherwise.
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Callable
from typing import Literal, Optional

MAZDA_AGENT = 'mazda_agent'
FINANCE_WORKFLOW = 'finance_workflow'
IntakeEngine = Literal['mazda_agent', 'finance_workflow']
ENGINES: frozenset[str] = frozenset({MAZDA_AGENT, FINANCE_WORKFLOW})


class InvalidIntakeEngine(ValueError):
    """FINANCE_INTAKE_ENGINE held something other than the two engine names."""


def resolve_intake_engine(raw: Optional[str] = None) -> str:
    """Unset -> the earlier engine. Anything else must be an exact name."""
    if raw is None:
        raw = os.environ.get('FINANCE_INTAKE_ENGINE')
    if raw is None or raw == '':
        return MAZDA_AGENT
    if raw not in ENGINES:
        raise InvalidIntakeEngine(
            "FINANCE_INTAKE_ENGINE must be 'mazda_agent' or 'finance_workflow', "
            f'got {raw!r}')
    return raw


class IntakeEngineService:
    """Answers "which engine takes the next document?".

    The file, when present and valid, wins over the default, so a cutover or
    a rollback is one small write and needs no restart. An unreadable or
    nonsense file means the default -- never the new engine by accident.
    """

    def __init__(self, path: str, default: Callable[[], str] = resolve_intake_engine):
        self._path = path
        self._default = default
        self._lock = threading.Lock()

    def current(self) -> str:
        try:
            with open(self._path, encoding='utf-8') as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            data = None
        engine = data.get('engine') if isinstance(data, dict) else None
        return engine if engine in ENGINES else self._default()

    def set(self, engine: str) -> str:
        if engine not in ENGINES:
            raise InvalidIntakeEngine(f'unknown intake engine: {engine!r}')
        with self._lock:
            directory = os.path.dirname(self._path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            tmp = f'{self._path}.tmp.{os.getpid()}'
            with open(tmp, 'w', encoding='utf-8') as fh:
                json.dump({'engine': engine}, fh)
            os.replace(tmp, self._path)
        return engine
