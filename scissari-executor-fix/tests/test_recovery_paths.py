"""Green-phase tests proving the loop RECOVERS — not just aborts.

The original bug spun 14x and reset. The fix must (a) succeed immediately on a
healthy call, (b) retry a transient 500 exactly once and then succeed, and
(c) never alert when it recovers.
"""
import pytest

from scissari_executor.service import ExecutorRunService
from scissari_executor.models import ExecutorCommand
from tests.fakes import (
    FakeExecutorClient,
    ScriptedExecutorClient,
    FakeAlertSink,
    FakeSnapshotStore,
)


async def _no_sleep(_seconds):
    return None


def _service(client, sink):
    return ExecutorRunService(
        client=client,
        alert_sink=sink,
        snapshot_store=FakeSnapshotStore(),
        sleep=_no_sleep,  # skip real backoff so tests stay fast
    )


@pytest.mark.asyncio
async def test_healthy_call_returns_immediately_and_never_alerts():
    client = FakeExecutorClient()  # always succeeds
    sink = FakeAlertSink()
    resp = await _service(client, sink).execute(
        ExecutorCommand(cmd="ls"), agent_id="agent-x"
    )
    assert resp.ok is True
    assert len(client.calls) == 1
    assert sink.last is None  # no stall report on the happy path


@pytest.mark.asyncio
async def test_transient_500_retries_once_then_succeeds():
    client = ScriptedExecutorClient(fail_times=1, status=500, detail="watchfiles reload")
    sink = FakeAlertSink()
    resp = await _service(client, sink).execute(
        ExecutorCommand(cmd="grep -r foo ."), agent_id="agent-x"
    )
    assert resp.stdout == "recovered"
    assert len(client.calls) == 2   # one fail + one successful retry — NOT 14
    assert sink.last is None         # recovered cleanly, no alert
