"""Domain models & enums (Command + value objects).

These are intentionally implementation-free where behavior is required:
ExecutorCommand.fingerprint() is a stub so its first test is red.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class FailureKind(str, Enum):
    """The structurally-distinct ways executor_run fails (F1-F7)."""

    ALLOWLIST_BLOCKED = "allowlist_blocked"      # F1  HTTP 400
    SERVER_RELOAD_500 = "server_reload_500"      # F2  HTTP 500 watchfiles loop
    REQUEST_TIMEOUT = "request_timeout"          # F3  HTTP 408
    EXECUTOR_DOWN = "executor_down"              # F4  ECONNREFUSED / no process
    END_TURN_NO_RETURN = "end_turn_no_return"    # F5  tool_call then end_turn, no tool_return
    PEER_TOOL_RULE_HANG = "peer_tool_rule_hang"  # F6  peer agent max_steps from bad tool_rule
    TOOL_RESPONSE_LOST = "tool_response_lost"    # F7  tool_return produced but lost in transit
    UNKNOWN = "unknown"                          # never silently retried — always aborts


class RecoveryAction(str, Enum):
    RETRY = "retry"                  # safe, after backoff
    NARROW = "narrow"                # retry only with a tightened command
    FALLBACK = "fallback"            # run client-side (F5)
    RESYNC = "resync"                # re-fetch the already-produced result, do NOT re-execute (F7)
    ABORT = "abort"                  # stop now; retrying cannot help
    CIRCUIT_OPEN = "circuit_open"    # service dead; stop and alert ops


class TurnState(str, Enum):
    RUNNING = "running"
    RECOVERING = "recovering"
    RESOLVED = "resolved"
    TRIPPED = "tripped"              # replaces the old "reset at 14"


class ExecutorCommand(BaseModel):
    """Command pattern — a reified executor_run invocation."""

    cmd: str
    cwd: Optional[str] = None
    timeout_s: float = 60.0
    allowlist_key: Optional[str] = None

    def fingerprint(self) -> str:
        """Stable hash for de-dup / repetition detection.

        Identical (cmd, cwd) pairs collapse to the same fingerprint so the
        LoopGuard can detect a command being retried verbatim — the exact
        pattern behind the 14-call spin.
        """
        import hashlib

        basis = f"{self.cmd}\0{self.cwd or ''}"
        return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]


class ExecutorResponse(BaseModel):
    ok: bool
    status: int
    stdout: str = ""
    stderr: str = ""
    duration_s: float = 0.0


class ExecutorFailure(BaseModel):
    """What IExecutorClient raises/returns on any non-success."""

    status: Optional[int] = None            # HTTP status if any
    transport_error: Optional[str] = None   # e.g. "ECONNREFUSED"
    detail: str = ""                        # server 'detail' body
    raw: dict[str, Any] = Field(default_factory=dict)


class FailureClassification(BaseModel):
    kind: FailureKind
    retryable: bool
    recommended_action: RecoveryAction
    evidence: str                           # human-readable WHY (fixes "no error captured")
    classifier_name: str


class RecoveryOutcome(BaseModel):
    action: RecoveryAction
    backoff_ms: int = 0
    next_command: Optional[ExecutorCommand] = None  # set when NARROW/FALLBACK
    reason: str = ""
    kind: Optional["FailureKind"] = None            # source classification (for budget + reporting)


class GuardVerdict(BaseModel):
    state: TurnState
    should_continue: bool
    calls_used: int
    budget_for_kind: int = 0
    snapshot_id: Optional[str] = None       # set when state == TRIPPED


class StallReport(BaseModel):
    """The Observer payload — finally carries a concrete reason."""

    agent_id: str
    classification: Optional[FailureClassification] = None
    calls_used: int = 0
    final_state: TurnState = TurnState.TRIPPED
    snapshot_id: Optional[str] = None
    message: str = ""


class ExecutorFailureError(Exception):
    """Raised by IExecutorClient.run() on any non-success, carrying the failure."""

    def __init__(self, failure: ExecutorFailure):
        self.failure = failure
        super().__init__(failure.detail or failure.transport_error or "executor failure")
