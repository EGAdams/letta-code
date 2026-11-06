"""Shared fakes for the pause_control tests: a controllable clock and a Rig
that wires a real SqliteControlLedger (so persistence/restart-recovery tests
exercise the actual repository) behind an injected pausability policy."""

from __future__ import annotations

import time
from pathlib import Path

from pause_control.pausability import ConfiguredTaskPausability
from pause_control.repository import SqliteControlLedger
from pause_control.service import PauseControlService


class Clock:
    def __init__(self) -> None:
        self.now = time.time_ns()

    def __call__(self) -> int:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += int(seconds * 10**9)


class Rig:
    def __init__(self, tmp_path: Path, pausable=frozenset(), not_pausable=frozenset()):
        self.clock = Clock()
        self.db_path = tmp_path / 'pause_control.sqlite3'
        self.ledger = SqliteControlLedger(self.db_path, clock_ns=self.clock)
        self.pausability = ConfiguredTaskPausability(pausable=pausable, not_pausable=not_pausable)
        self.service = PauseControlService(self.ledger, self.pausability, clock_ns=self.clock)

    def restart(self) -> None:
        """Simulate a dashboard restart: a fresh repository/service over the same file."""
        self.ledger = SqliteControlLedger(self.db_path, clock_ns=self.clock)
        self.service = PauseControlService(self.ledger, self.pausability, clock_ns=self.clock)
