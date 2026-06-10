"""Domain models & enums for the session/transport layer (F7)."""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel


class StreamEventKind(str, Enum):
    """The stream events lettabot already logs (`[Stream] type=...`)."""

    REASONING = "reasoning"
    TEXT = "text"
    TOOL_CALL_START = "tool_call_start"   # a tool call begins — stream goes quiet, legitimately
    TOOL_RETURN = "tool_return"           # tool finished — resume normal idle timing
    TURN_END = "turn_end"                 # end_turn


class SessionState(str, Enum):
    IDLE = "idle"
    STREAMING = "streaming"
    TOOL_CALL = "tool_call"   # tool in flight — stream silence is EXPECTED, not a hang
    CLOSED = "closed"
    DEAD = "dead"


class CloseReason(str, Enum):
    NONE = "none"
    STREAM_IDLE = "stream_idle"                 # genuine: no activity at all
    TOOL_CALL_DEADLINE = "tool_call_deadline"   # tool call blew its OWN budget
    TRANSPORT_DEAD = "transport_dead"


class SessionVerdict(BaseModel):
    should_close: bool
    state: SessionState
    reason: CloseReason = CloseReason.NONE
    seconds_since_last_event: float = 0.0
    seconds_in_tool_call: float = 0.0
    detail: str = ""


class TransportInfo(BaseModel):
    """Mirror of the SDK transport state (closed/pid/stdin)."""

    pid: Optional[int] = None
    closed: bool = True

    @property
    def alive(self) -> bool:
        return self.pid is not None and not self.closed
