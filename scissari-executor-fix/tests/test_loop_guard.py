"""Red-phase tests for the LoopGuard state machine.

The headline test encodes the actual bug: 14 identical failing calls. The fix
trips after the per-kind budget (e.g. 2) and captures a Memento before reset.
"""
from scissari_executor.guard import LoopGuard
from scissari_executor.models import (
    ExecutorCommand,
    RecoveryOutcome,
    RecoveryAction,
    TurnState,
)
from tests.fakes import FakeSnapshotStore


def test_identical_command_trips_fast_not_at_14():
    """The bug: 14 identical failing calls. Fix: trip at the per-kind budget (2)."""
    guard = LoopGuard(
        budget_per_kind={"server_reload_500": 2},
        snapshot_store=FakeSnapshotStore(),
    )
    cmd = ExecutorCommand(cmd="ls /huge")
    retry = RecoveryOutcome(action=RecoveryAction.RETRY)
    guard.register(cmd, retry)
    verdict = guard.register(cmd, retry)
    assert verdict.state == TurnState.TRIPPED
    assert verdict.calls_used == 2            # NOT 14
    assert verdict.snapshot_id is not None    # Memento captured before trip


def test_abort_outcome_trips_immediately():
    guard = LoopGuard()
    verdict = guard.register(
        ExecutorCommand(cmd="bad"),
        RecoveryOutcome(action=RecoveryAction.ABORT, reason="allowlist"),
    )
    assert verdict.should_continue is False
    assert verdict.state == TurnState.TRIPPED


def test_successful_recovery_resolves():
    guard = LoopGuard()
    verdict = guard.register(
        ExecutorCommand(cmd="ls"),
        RecoveryOutcome(action=RecoveryAction.RETRY),
    )
    assert verdict.state in (TurnState.RUNNING, TurnState.RECOVERING)
