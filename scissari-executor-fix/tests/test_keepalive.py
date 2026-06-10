"""F7 — ToolCallKeepalive suppresses the inactivity timer while a tool call runs
and re-arms the stream-idle timer after tool_return."""
from scissari_executor.session.health import SessionHealth
from scissari_executor.session.keepalive import ToolCallKeepalive
from scissari_executor.session.models import StreamEventKind


def _setup():
    h = SessionHealth(stream_idle_timeout_s=300, tool_call_deadline_s=900, now=lambda: 0)
    return h, ToolCallKeepalive(h)


def test_suppressed_during_tool_call():
    h, k = _setup()   
    assert k.is_suppressed() is False
    h.on_event(StreamEventKind.TOOL_CALL_START, at=0)
    assert k.is_suppressed() is True
    # next close-check is the tool-call deadline, not the 300s idle window
    assert k.next_deadline() == 900


def test_rearmed_after_tool_return():
    h, k = _setup()
    h.on_event(StreamEventKind.TOOL_CALL_START, at=0)
    h.on_event(StreamEventKind.TOOL_RETURN, at=10)
    assert k.is_suppressed() is False
    assert k.next_deadline() == 10 + 300
