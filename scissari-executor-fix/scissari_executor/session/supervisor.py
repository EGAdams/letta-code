"""SessionSupervisor (Facade) — the only session object the bot/heartbeat call.

Replaces the blind 300_000ms timer + raw `session.send()`:
  - feed_event() : pump `[Stream]` events into the health state machine.
  - tick()       : periodic close-check (deadline-aware, not blind idle).
  - send()       : heartbeat/user sends go through ResilientTransport, so a dead
                   subprocess is transparently re-spawned (never 'Transport not
                   connected'). When it does close, it emits a StallReport with a
                   concrete reason — same Observer the executor layer uses.
"""
from __future__ import annotations

import time
from typing import Callable, Optional

from ..interfaces import IAlertSink
from ..models import StallReport, TurnState
from .health import SessionHealth
from .interfaces import IResilientTransport, ISessionSupervisor
from .keepalive import ToolCallKeepalive
from .models import CloseReason, SessionVerdict, StreamEventKind


class SessionSupervisor(ISessionSupervisor):
    def __init__(
        self,
        transport: IResilientTransport,
        alert_sink: IAlertSink,
        health: Optional[SessionHealth] = None,
        agent_id: str = "scissari",
        now: Callable[[], float] = time.monotonic,
    ):
        self._transport = transport
        self._alert = alert_sink
        self._health = health or SessionHealth(now=now)
        self._keepalive = ToolCallKeepalive(self._health)
        self._agent_id = agent_id
        self._now = now

    @property
    def health(self) -> SessionHealth:
        return self._health

    @property
    def keepalive(self) -> ToolCallKeepalive:
        return self._keepalive

    def feed_event(self, kind: StreamEventKind, at: Optional[float] = None) -> None:
        self._health.on_event(kind, at)

    async def tick(self, at: Optional[float] = None) -> SessionVerdict:
        verdict = self._health.should_close(at)
        if verdict.should_close:
            await self._alert.emit(
                StallReport(
                    agent_id=self._agent_id,
                    classification=None,
                    final_state=TurnState.TRIPPED,
                    message=self._explain(verdict),
                )
            )
        return verdict

    async def send(self, data: str) -> None:
        await self._transport.send(data)

    @staticmethod
    def _explain(verdict: SessionVerdict) -> str:
        if verdict.reason == CloseReason.TOOL_CALL_DEADLINE:
            return (
                f"closing session: tool call ran {verdict.seconds_in_tool_call:.0f}s, "
                f"past its deadline ({verdict.detail})"
            )
        if verdict.reason == CloseReason.STREAM_IDLE:
            return f"closing session: {verdict.detail}"
        return "closing session"
