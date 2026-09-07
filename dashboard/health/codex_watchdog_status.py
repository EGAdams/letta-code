"""GET /api/codex-watchdog-status: a read-only view of this box's local Codex
CLI quota watchdog -- the live process table, each session's latest quota
reading, and the watchdog's own action history.

This reports on the box the *dashboard* is running on, which is not
necessarily the box `codex-watchdog.service` runs on (see dashboard/CLAUDE.md,
"Which machine is live") -- the tile is only meaningful when the two are the
same box, or when this endpoint is read directly against one known to run
the service.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import Field

from contracts import StrictModel
from health.codex_process_inspector import ProcProcessInspector
from health.codex_session_reader import RolloutFileSessionReader
from health.codex_watchdog_contracts import (
    KILL_PRIMARY_PERCENT,
    MAX_CONCURRENT_AUTONOMOUS,
    STOPPED_REAP_SECONDS,
    WARN_PRIMARY_PERCENT,
)
from health.codex_watchdog_store import default_store

#: How many recent actions the panel shows -- enough history to see a
#: pattern without the payload growing without bound.
_RECENT_ACTIONS_LIMIT = 20


class CodexWatchdogSessionView(StrictModel):
    pgid: int
    cmd: str
    cwd: str
    state: str
    elapsed_seconds: float
    autonomous: bool
    session_path: Optional[str] = None
    primary_used_percent: Optional[float] = None
    secondary_used_percent: Optional[float] = None


class CodexWatchdogActionView(StrictModel):
    timestamp: float
    action: str
    pgid: int
    cmd: str
    reason: str
    used_percent: Optional[float] = None


class CodexWatchdogThresholds(StrictModel):
    kill_percent: float = KILL_PRIMARY_PERCENT
    warn_percent: float = WARN_PRIMARY_PERCENT
    max_concurrent: int = MAX_CONCURRENT_AUTONOMOUS
    stopped_reap_seconds: float = STOPPED_REAP_SECONDS


class CodexWatchdogStatusPayload(StrictModel):
    ok: bool = True
    error: Optional[str] = None
    sessions: List[CodexWatchdogSessionView] = Field(default_factory=list)
    recent_actions: List[CodexWatchdogActionView] = Field(default_factory=list)
    thresholds: CodexWatchdogThresholds = Field(
        default_factory=CodexWatchdogThresholds)


def _session_views(inspector, reader) -> List[CodexWatchdogSessionView]:
    views = []
    for group in inspector.running_groups():
        usage = reader.usage_for(group.session_path) if group.session_path else None
        views.append(CodexWatchdogSessionView(
            pgid=group.pgid,
            cmd=group.cmd,
            cwd=group.cwd,
            state=group.state,
            elapsed_seconds=group.elapsed_seconds,
            autonomous=group.autonomous,
            session_path=group.session_path,
            primary_used_percent=usage.primary_used_percent if usage else None,
            secondary_used_percent=usage.secondary_used_percent if usage else None,
        ))
    return views


def status_payload() -> dict:
    """Fails soft: a bad read costs this panel, never the page around it."""
    try:
        sessions = _session_views(ProcProcessInspector(), RolloutFileSessionReader())
        actions = [CodexWatchdogActionView(**a.model_dump())
                   for a in default_store().recent(_RECENT_ACTIONS_LIMIT)]
        payload = CodexWatchdogStatusPayload(sessions=sessions,
                                              recent_actions=actions)
    except Exception as exc:
        payload = CodexWatchdogStatusPayload(ok=False, error=str(exc))
    return payload.model_dump(mode='json')
