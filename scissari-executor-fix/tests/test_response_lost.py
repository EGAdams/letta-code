"""F7 — TOOL_RESPONSE_LOST end-to-end.

The new (2026-06-06) Telegram symptom:

    "I ran into an issue completing that request — the response was lost
     during a tool workflow. Please try again."

This is NOT F5 (END_TURN_NO_RETURN): there the server never produced a
tool_return; here it did, but the stream/relay dropped it. The fix must:

  * classify it with a concrete reason (never the generic "Please try again"),
  * recover via RESYNC (re-fetch the result), not a blind re-run that could
    double a side-effect,
  * re-sync at most ONCE, then trip with a real reason — never spin to 14.
"""
import pytest

from scissari_executor.classifiers import build_default_chain
from scissari_executor.strategies import StrategyFactory
from scissari_executor.guard import LoopGuard
from scissari_executor.breaker import CircuitBreaker
from scissari_executor.service import ExecutorRunService
from scissari_executor.models import (
    ExecutorCommand,
    ExecutorFailure,
    FailureKind,
    RecoveryAction,
)
from tests.fakes import (
    FakeExecutorClient,
    ScriptedExecutorClient,
    FakeAlertSink,
    FakeSnapshotStore,
)


_LOST = "the response was lost during a tool workflow. Please try again."


async def _no_sleep(_seconds):
    return None


def _service(client, sink):
    return ExecutorRunService(
        client=client,
        alert_sink=sink,
        classifier=build_default_chain(),
        factory=StrategyFactory(),
        guard=LoopGuard(snapshot_store=FakeSnapshotStore()),
        breaker=CircuitBreaker(),
        snapshot_store=FakeSnapshotStore(),
        sleep=_no_sleep,
    )


def test_classifier_maps_verbatim_telegram_message():
    result = build_default_chain().classify(ExecutorFailure(detail=_LOST))
    assert result.kind == FailureKind.TOOL_RESPONSE_LOST
    assert result.recommended_action == RecoveryAction.RESYNC
    assert result.retryable is True
    assert result.evidence  # carries a concrete WHY


def test_strategy_resyncs_without_re_executing():
    factory = StrategyFactory()
    strategy = factory.for_kind(FailureKind.TOOL_RESPONSE_LOST)
    classification = build_default_chain().classify(ExecutorFailure(detail=_LOST))
    cmd = ExecutorCommand(cmd="deploy.sh")  # a side-effecting command

    import asyncio

    outcome = asyncio.run(strategy.recover(cmd, classification))
    assert outcome.action == RecoveryAction.RESYNC
    # RESYNC re-fetches the SAME run's result; it must not mutate the command
    # into a fresh execution.
    assert outcome.next_command == cmd


@pytest.mark.asyncio
async def test_resyncs_once_then_succeeds():
    # First call drops the response; the resync poll finds the result.
    client = ScriptedExecutorClient(fail_times=1, detail=_LOST)
    sink = FakeAlertSink()
    resp = await _service(client, sink).execute(
        ExecutorCommand(cmd="deploy.sh"), agent_id="agent-x"
    )
    assert resp.ok is True
    assert len(client.calls) == 2   # original + one resync — NOT 14
    assert sink.last is None         # recovered cleanly, no alert


@pytest.mark.asyncio
async def test_persistently_lost_response_trips_with_a_real_reason():
    client = FakeExecutorClient(fail_detail=_LOST)  # never recovers
    sink = FakeAlertSink()
    with pytest.raises(Exception):
        await _service(client, sink).execute(
            ExecutorCommand(cmd="deploy.sh"),
            agent_id="agent-5955b0c2-7922-4ffe-9e43-b116053b80fa",
        )
    assert len(client.calls) == 2   # tripped at the per-kind budget, NOT 14
    assert sink.last is not None
    assert sink.last.classification.kind == FailureKind.TOOL_RESPONSE_LOST
    # The alert must explain itself with a CLASSIFIED reason — not the old
    # "no error captured" lie, and not merely echoing the generic user-facing
    # "Please try again" (the raw detail may still be quoted for forensics).
    msg = sink.last.message
    assert "No specific tool error" not in msg
    assert "lost in transit" in msg          # the concrete, classified WHY
    assert sink.last.snapshot_id is not None  # Memento captured before trip
