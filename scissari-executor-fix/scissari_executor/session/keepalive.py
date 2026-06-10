"""ToolCallKeepalive — Observer over SessionHealth.

Keeps the session warm (bug a): while a tool call is in flight the bot's
inactivity timer is suppressed and the next close-check is pushed out to the
tool call's own deadline. After tool_return the stream-idle timer is re-armed.
"""
from __future__ import annotations

from typing import Optional

from .health import SessionHealth
from .interfaces import IKeepalive


class ToolCallKeepalive(IKeepalive):
    def __init__(self, health: SessionHealth):
        self._health = health

    def is_suppressed(self) -> bool:
        return self._health.in_tool_call

    def next_deadline(self, at: Optional[float] = None) -> float:
        if self._health.in_tool_call and self._health.tool_call_started_at is not None:
            return self._health.tool_call_started_at + self._health.tool_deadline_s
        return self._health.last_event_at + self._health.stream_idle_s
