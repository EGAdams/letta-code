"""Loop guard (State machine + Memento).

Replaces the blind `count < 14` counter. For each command it:

  * trips IMMEDIATELY on a terminal outcome (ABORT / CIRCUIT_OPEN),
  * otherwise counts how many times the SAME command fingerprint has been
    registered with a retry-ish action and trips once that count reaches the
    per-kind budget (default 2 — never 14),
  * captures a Memento snapshot before any TRIPPED transition.
"""
from __future__ import annotations

from typing import Dict, Optional

from .interfaces import ILoopGuard, IConversationSnapshotStore
from .models import (
    ExecutorCommand,
    RecoveryOutcome,
    RecoveryAction,
    GuardVerdict,
    TurnState,
)


# Per-kind "strike count": the Nth identical retry-ish attempt trips the guard.
# The whole point: NONE of these is anywhere near 14.
DEFAULT_BUDGET_PER_KIND: Dict[str, int] = {
    "allowlist_blocked": 0,     # F1 — terminal (ABORT trips immediately anyway)
    "server_reload_500": 2,     # F2 — one backoff retry, then trip
    "request_timeout": 2,       # F3 — one narrowed retry, then trip
    "executor_down": 0,         # F4 — terminal (CIRCUIT_OPEN)
    "end_turn_no_return": 2,    # F5 — one client-side fallback, then trip
    "peer_tool_rule_hang": 0,   # F6 — terminal (ABORT)
    "unknown": 0,               # always abort
}

_TERMINAL_ACTIONS = (RecoveryAction.ABORT, RecoveryAction.CIRCUIT_OPEN)


class LoopGuard(ILoopGuard):
    def __init__(
        self,
        budget_per_kind: Optional[Dict[str, int]] = None,
        snapshot_store: Optional[IConversationSnapshotStore] = None,
        default_retry_budget: int = 2,
        agent_id: str = "loop-guard",
    ):
        self._budget = {**DEFAULT_BUDGET_PER_KIND, **(budget_per_kind or {})}
        self._snapshots = snapshot_store
        self._default_retry_budget = default_retry_budget
        self._agent_id = agent_id
        self._calls = 0
        self._fingerprints: Dict[str, int] = {}

    def _budget_for(self, outcome: RecoveryOutcome) -> int:
        if outcome.kind is not None:
            return self._budget.get(outcome.kind.value, self._default_retry_budget)
        return self._default_retry_budget

    def _snapshot(self) -> Optional[str]:
        if self._snapshots is None:
            return None
        return self._snapshots.capture(self._agent_id, [])

    def register(self, cmd: ExecutorCommand, outcome: RecoveryOutcome) -> GuardVerdict:
        self._calls += 1

        # Terminal outcome: trip now, snapshot for forensics.
        if outcome.action in _TERMINAL_ACTIONS:
            return GuardVerdict(
                state=TurnState.TRIPPED,
                should_continue=False,
                calls_used=self._calls,
                snapshot_id=self._snapshot(),
            )

        # Retry-ish outcome: count identical-command attempts against the budget.
        fp = cmd.fingerprint()
        repeats = self._fingerprints.get(fp, 0) + 1
        self._fingerprints[fp] = repeats
        budget = self._budget_for(outcome)

        if repeats >= budget:
            return GuardVerdict(
                state=TurnState.TRIPPED,
                should_continue=False,
                calls_used=self._calls,
                budget_for_kind=budget,
                snapshot_id=self._snapshot(),
            )

        return GuardVerdict(
            state=TurnState.RECOVERING,
            should_continue=True,
            calls_used=self._calls,
            budget_for_kind=budget,
        )

    def reset(self) -> None:
        self._calls = 0
        self._fingerprints.clear()
