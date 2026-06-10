"""F7 — SessionHealth: a long-but-healthy tool call must NOT be killed by the
coarse stream-idle timer (bug a). The old 300_000ms timer killed sessions that
were about to succeed."""
from scissari_executor.session.health import SessionHealth
from scissari_executor.session.models import CloseReason, SessionState, StreamEventKind


def _health():
    return SessionHealth(stream_idle_timeout_s=300, tool_call_deadline_s=900, now=lambda: 0)


def test_long_tool_call_within_deadline_is_not_closed():
    h = _health()
    h.on_event(StreamEventKind.TOOL_CALL_START, at=0)
    # 400s of stream silence — PAST the 300s idle window, but a tool call is in flight.
    v = h.should_close(at=400)
    assert v.should_close is False           # the old timer would have killed it here
    assert v.state == SessionState.TOOL_CALL


def test_tool_call_past_its_own_deadline_is_closed():
    h = _health()
    h.on_event(StreamEventKind.TOOL_CALL_START, at=0)
    v = h.should_close(at=950)
    assert v.should_close is True
    assert v.reason == CloseReason.TOOL_CALL_DEADLINE
    assert v.seconds_in_tool_call >= 900


def test_genuine_idle_still_trips_stream_idle():
    h = _health()
    h.on_event(StreamEventKind.REASONING, at=0)
    v = h.should_close(at=301)
    assert v.should_close is True
    assert v.reason == CloseReason.STREAM_IDLE


def test_tool_return_rearms_stream_idle():
    h = _health()
    h.on_event(StreamEventKind.TOOL_CALL_START, at=0)
    h.on_event(StreamEventKind.TOOL_RETURN, at=10)
    # back to streaming; idle now measured from the tool_return at t=10
    assert h.should_close(at=300).should_close is False
    assert h.should_close(at=311).should_close is True
