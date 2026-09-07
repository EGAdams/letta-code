"""Shapes and ports for the local Codex CLI quota watchdog.

Built after the 2026-09-07 incident: an unattended `codex
--dangerously-bypass-approvals-and-sandbox` session burned 14.6M tokens in
one thread (9.26M of that in a single turn) building dashboard test fixtures,
driving its 5-hour Codex quota to 97% before anyone noticed. Nothing was
watching the quota, and nothing capped how many such sessions could run at
once. This module is the shape of that watcher; `codex_watchdog.py` holds the
policy.

Unlike the Claude SDK path (`health/claude_sdk_activity.py`), Codex CLI
sessions are raw local processes a human or an agent starts directly in a
terminal -- the dashboard's executor never owns their lifecycle. So this
watches the OS process table and each session's own rollout log, not an HTTP
endpoint the dashboard already proxies.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from contracts import StrictModel

#: Argument that marks a Codex CLI invocation as unattended/autonomous --
#: the only kind this watchdog is allowed to kill. A session a person is
#: actively approving prompts in does not carry this flag.
AUTONOMOUS_FLAG = '--dangerously-bypass-approvals-and-sandbox'

#: `--cd <trainer dir>` appears verbatim in the cmd of every Codex session
#: the Mazda Trainer (trainer/run_mazda_trainer.mjs) dispatches as its
#: Claude-failure fallback. Found 2026-09-07: two concurrent scanner intakes
#: each fell back to Codex at the same moment a third, unrelated autonomous
#: Codex session was already running; MAX_CONCURRENT_AUTONOMOUS=1 terminated
#: both Trainer sessions to make room for it, wiping both intakes with no
#: report. Trainer already time-boxes and retry-limits its own Codex calls
#: (MAX_ATTEMPTS, TRAINER_ATTEMPT_TIMEOUT_MS) and writes an emergency report
#: if every attempt fails -- it is a supervised, bounded use of Codex, not
#: the unattended-and-forgotten session this watchdog's concurrency cap
#: exists to catch, so it should never compete for that single slot. It is
#: still subject to the quota kill/warn checks below.
TRAINER_CWD_MARKER = '/dashboard/trainer'

#: Primary (5-hour) quota usage at which a session is killed outright.
KILL_PRIMARY_PERCENT = 90.0

#: Primary quota usage at which a session is only logged as a warning.
WARN_PRIMARY_PERCENT = 70.0

#: At most this many autonomous Codex sessions may run at once; the newest
#: over the limit is terminated. The incident ran three concurrently.
MAX_CONCURRENT_AUTONOMOUS = 1

#: An autonomous session left stopped (Ctrl-Z / job-control `T` state) this
#: long is reaped -- it still holds its slot and quota window open while
#: looking idle to anything that only checks CPU usage.
STOPPED_REAP_SECONDS = 600.0

#: How often the daemon re-checks the process table and quota files.
POLL_INTERVAL_SECONDS = 60.0


class CodexProcessGroup(StrictModel):
    """One running `codex` CLI invocation, as a process group.

    `session_path` is filled in only when the inspector can prove which
    rollout file this exact group has open (via /proc/<pid>/fd) -- quota
    decisions must never guess a session from something as weak as cwd.
    """

    pgid: int
    pids: List[int]
    cmd: str
    cwd: str
    state: str
    elapsed_seconds: float
    session_path: Optional[str] = None

    @property
    def autonomous(self) -> bool:
        return AUTONOMOUS_FLAG in self.cmd

    @property
    def stopped(self) -> bool:
        return self.state.startswith('T')

    @property
    def supervised(self) -> bool:
        """Dispatched by the Mazda Trainer, not a human or another agent."""
        return TRAINER_CWD_MARKER in self.cmd


class CodexUsageSample(StrictModel):
    """The most recent rate-limit reading found in one rollout log."""

    session_path: str
    observed_at: float
    primary_used_percent: float
    primary_window_minutes: int = 300
    secondary_used_percent: float = 0.0
    secondary_window_minutes: int = 10080
    resets_at: Optional[float] = None


class WatchdogAction(StrictModel):
    """One thing the watchdog did (or warned about), for the action history."""

    timestamp: float
    action: str
    pgid: int
    cmd: str
    reason: str
    used_percent: Optional[float] = None


class WatchdogDecision(StrictModel):
    """What the pure policy wants done about one group, before it is applied."""

    group: CodexProcessGroup
    action: str
    reason: str
    used_percent: Optional[float] = None


class ICodexProcessInspector(ABC):
    """The live OS process table, filtered to Codex CLI process groups."""

    @abstractmethod
    def running_groups(self) -> List[CodexProcessGroup]:
        """Every process group whose members are a `codex` CLI invocation."""


class ICodexSessionReader(ABC):
    """One rollout log's most recent quota reading."""

    @abstractmethod
    def usage_for(self, session_path: str) -> Optional[CodexUsageSample]:
        """The latest `token_count` event's rate limits, or None if absent."""


class ICodexProcessController(ABC):
    """Signals a process group, never a single pid -- the vendor binary and
    its `node` wrapper must die together or the wrapper respawns it."""

    @abstractmethod
    def terminate(self, pgid: int) -> None:
        """SIGTERM the group."""

    @abstractmethod
    def force_kill(self, pgid: int) -> None:
        """SIGKILL the group."""


class IWatchdogActionStore(ABC):
    """Where actions outlive the daemon process that took them."""

    @abstractmethod
    def record(self, action: WatchdogAction) -> None:
        """Append one action."""

    @abstractmethod
    def recent(self, limit: int = 50) -> List[WatchdogAction]:
        """The most recent actions, oldest first."""
