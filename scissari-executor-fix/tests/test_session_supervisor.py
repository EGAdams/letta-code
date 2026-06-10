"""F7 — SessionSupervisor (Facade): the integration the bot/heartbeat call."""
from scissari_executor.session.models import CloseReason, StreamEventKind
from scissari_executor.session.supervisor import SessionSupervisor
from scissari_executor.session.transport import ResilientTransport
from tests.fakes import FakeAlertSink, FakeSubprocessTransport


def _sup(transport=None):
    sink = FakeAlertSink()
    t = transport or ResilientTransport(FakeSubprocessTransport(alive=True))
    return SessionSupervisor(transport=t, alert_sink=sink, agent_id="scissari"), sink


async def test_long_tool_call_does_not_trip_or_alert():
    sup, sink = _sup()
    sup.feed_event(StreamEventKind.TOOL_CALL_START, at=0)
    v = await sup.tick(at=400)             # past 300s idle, within the deadline
    assert v.should_close is False
    assert sink.reports == []


async def test_tool_call_deadline_trips_with_a_real_reason():
    sup, sink = _sup()
    sup.feed_event(StreamEventKind.TOOL_CALL_START, at=0)
    v = await sup.tick(at=950)
    assert v.should_close is True
    assert v.reason == CloseReason.TOOL_CALL_DEADLINE
    assert sink.last is not None
    assert "tool call" in sink.last.message       # not "No specific tool error captured"


async def test_heartbeat_send_respawns_dead_session():
    inner = FakeSubprocessTransport(alive=False)  # session was closed → pid undefined
    sup, _ = _sup(transport=ResilientTransport(inner))
    await sup.send("[heartbeat]")
    assert inner.sent == ["[heartbeat]"]          # not 'Transport not connected'
    assert inner.spawn_calls == 1
