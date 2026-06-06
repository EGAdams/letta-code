"""Red-phase integration test for the Facade with fakes injected.

Asserts the alert finally carries a concrete reason — the old
"No specific tool error captured" lie must be gone.
"""
import pytest

from scissari_executor.service import ExecutorRunService
from scissari_executor.classifiers import build_default_chain
from scissari_executor.strategies import StrategyFactory
from scissari_executor.guard import LoopGuard
from scissari_executor.breaker import CircuitBreaker
from scissari_executor.models import ExecutorCommand, FailureKind
from tests.fakes import FakeExecutorClient, FakeAlertSink, FakeSnapshotStore


@pytest.mark.asyncio
async def test_dead_executor_aborts_and_alerts_with_reason():
    sink = FakeAlertSink()
    service = ExecutorRunService(
        client=FakeExecutorClient(always_fail="ECONNREFUSED"),
        alert_sink=sink,
        classifier=build_default_chain(),
        factory=StrategyFactory(),
        guard=LoopGuard(snapshot_store=FakeSnapshotStore()),
        breaker=CircuitBreaker(threshold=2),
        snapshot_store=FakeSnapshotStore(),
    )
    with pytest.raises(Exception):
        await service.execute(
            ExecutorCommand(cmd="ls"),
            agent_id="agent-5955b0c2-7922-4ffe-9e43-b116053b80fa",
        )
    assert sink.last is not None
    assert sink.last.classification.kind == FailureKind.EXECUTOR_DOWN
    assert "No specific tool error" not in sink.last.message  # the old lie is gone


@pytest.mark.asyncio
async def test_allowlist_block_aborts_without_retrying_14_times():
    client = FakeExecutorClient(fail_status=400, fail_detail="Command not in allowlist: /x")
    sink = FakeAlertSink()
    service = ExecutorRunService(
        client=client,
        alert_sink=sink,
        classifier=build_default_chain(),
        factory=StrategyFactory(),
        guard=LoopGuard(snapshot_store=FakeSnapshotStore()),
        breaker=CircuitBreaker(),
        snapshot_store=FakeSnapshotStore(),
    )
    with pytest.raises(Exception):
        await service.execute(ExecutorCommand(cmd="/x"), agent_id="agent-x")
    # F1 is non-retryable: the executor is hit exactly once, then aborts — never 14 times.
    assert len(client.calls) == 1
    assert sink.last is not None
    assert sink.last.classification.kind == FailureKind.ALLOWLIST_BLOCKED
