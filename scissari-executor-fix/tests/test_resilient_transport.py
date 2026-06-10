"""F7 — ResilientTransport re-spawns a dead subprocess instead of throwing
'Transport not connected' (bug b)."""
import pytest

from scissari_executor.session.transport import (
    ResilientTransport,
    TransportUnavailableError,
)
from tests.fakes import FakeSubprocessTransport


async def test_send_to_dead_pid_respawns_once_then_succeeds():
    inner = FakeSubprocessTransport(alive=False)      # pid=undefined
    rt = ResilientTransport(inner)
    await rt.send("heartbeat")
    assert inner.spawn_calls == 1
    assert inner.sent == ["heartbeat"]
    assert rt.respawns == 1


async def test_alive_transport_is_not_respawned():
    inner = FakeSubprocessTransport(alive=True)
    rt = ResilientTransport(inner)
    await rt.send("hi")
    assert inner.spawn_calls == 0
    assert inner.sent == ["hi"]


async def test_repeated_spawn_failure_opens_circuit_not_raw_error():
    inner = FakeSubprocessTransport(alive=False, spawn_fails=True)
    rt = ResilientTransport(inner)   # breaker threshold default 3
    for _ in range(3):
        with pytest.raises(TransportUnavailableError):
            await rt.send("x")
    spawns_after_open = inner.spawn_calls
    # circuit now open: a clean domain error, and it doesn't even try to spawn
    with pytest.raises(TransportUnavailableError):
        await rt.send("x")
    assert inner.spawn_calls == spawns_after_open


async def test_spawn_that_raises_is_wrapped_not_leaked():
    inner = FakeSubprocessTransport(alive=False, spawn_raises=True)
    rt = ResilientTransport(inner)
    with pytest.raises(TransportUnavailableError):
        await rt.send("x")
