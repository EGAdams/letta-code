"""SessionHealth — State machine that decides whether to close the session.

The F7 fix (bug a): a tool call may legitimately run far longer than the
stream-idle window while emitting no stream events. So while a tool call is in
flight we IGNORE the stream-idle timer and only trip on the tool call's OWN
deadline. A slow success is no longer mistaken for a hang.
"""
from __future__ import annotations

import time
from typing import Callable, Optional

from .interfaces import ISessionHealth
from .models import CloseReason, SessionState, SessionVerdict, StreamEventKind

# lettabot's current single coarse timer (the bug): 300_000 ms.
DEFAULT_STREAM_IDLE_S = 300.0
# A big executor_run can legitimately take much longer; give it its own budget.
DEFAULT_TOOL_CALL_DEADLINE_S = 900.0


class SessionHealth(ISessionHealth):
    def __init__(
        self,
        stream_idle_timeout_s: float = DEFAULT_STREAM_IDLE_S,
        tool_call_deadline_s: float = DEFAULT_TOOL_CALL_DEADLINE_S,
        now: Callable[[], float] = time.monotonic,
    ):
        self._stream_idle = stream_idle_timeout_s
        self._tool_deadline = tool_call_deadline_s
        self._now = now
        self.reset()

    # --- public accessors (so the Keepalive observer needn't reach inside) ---
    @property
    def state(self) -> SessionState:
        return self._state

    @property
    def in_tool_call(self) -> bool:
        return self._state == SessionState.TOOL_CALL

    @property
    def tool_call_started_at(self) -> Optional[float]:
        return self._tool_call_started_at

    @property
    def last_event_at(self) -> float:
        return self._last_event_at

    @property
    def stream_idle_s(self) -> float:
        return self._stream_idle

    @property
    def tool_deadline_s(self) -> float:
        return self._tool_deadline

    # --- state machine ---
    def reset(self, at: Optional[float] = None) -> None:
        t = at if at is not None else self._now()
        self._state = SessionState.IDLE
        self._last_event_at = t
        self._tool_call_started_at: Optional[float] = None

    def on_event(self, kind: StreamEventKind, at: Optional[float] = None) -> None:
        t = at if at is not None else self._now()
        self._last_event_at = t
        if kind == StreamEventKind.TOOL_CALL_START:
            self._state = SessionState.TOOL_CALL
            self._tool_call_started_at = t
        elif kind == StreamEventKind.TOOL_RETURN:
            self._state = SessionState.STREAMING
            self._tool_call_started_at = None
        elif kind == StreamEventKind.TURN_END:
            self._state = SessionState.IDLE
            self._tool_call_started_at = None
        else:  # REASONING / TEXT — don't clobber an in-flight tool call
            if self._state != SessionState.TOOL_CALL:
                self._state = SessionState.STREAMING

    def should_close(self, at: Optional[float] = None) -> SessionVerdict:
        t = at if at is not None else self._now()
        since_event = t - self._last_event_at

        if self._state == SessionState.TOOL_CALL and self._tool_call_started_at is not None:
            in_tool = t - self._tool_call_started_at
            if in_tool >= self._tool_deadline:
                return SessionVerdict(
                    should_close=True,
                    state=self._state,
                    reason=CloseReason.TOOL_CALL_DEADLINE,
                    seconds_since_last_event=since_event,
                    seconds_in_tool_call=in_tool,
                    detail=f"tool call exceeded its {self._tool_deadline:.0f}s budget",
                )
            return SessionVerdict(
                should_close=False,
                state=self._state,
                reason=CloseReason.NONE,
                seconds_since_last_event=since_event,
                seconds_in_tool_call=in_tool,
                detail="tool call in flight — stream silence is expected",
            )

        if since_event >= self._stream_idle:
            return SessionVerdict(
                should_close=True,
                state=self._state,
                reason=CloseReason.STREAM_IDLE,
                seconds_since_last_event=since_event,
                detail=f"no stream activity for {since_event:.0f}s",
            )
        return SessionVerdict(
            should_close=False,
            state=self._state,
            reason=CloseReason.NONE,
            seconds_since_last_event=since_event,
        )
