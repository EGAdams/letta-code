"""The interfaces the feed depends on. Implementations live beside this file."""
from __future__ import annotations

from typing import Protocol

from .models import DebuggerSettings, RawEvent, RunRow


class IAdwEventRepository(Protocol):
    """Read-only access to recorded ADW runs and events, in recorded order."""

    def head_cursor(self) -> int: ...

    def recent_runs(self, adw_names: list[str], limit: int) -> list[RunRow]: ...

    def events_for_runs(self, run_ids: list[str]) -> list[RawEvent]: ...

    def events_after(self, cursor: int, adw_names: list[str], limit: int) -> list[RawEvent]: ...


class IProcessProbe(Protocol):
    """Is the process that was running this ADW still there?"""

    def alive(self, pid: int, command: str) -> bool: ...


class ISettingsSource(Protocol):
    def load(self) -> DebuggerSettings: ...
