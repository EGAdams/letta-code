"""Domain contracts for reading Letta agent state."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict


class StrictBoundaryModel(BaseModel):
    """Base contract for data crossing the dashboard's Letta boundary."""

    model_config = ConfigDict(strict=True, extra='forbid', frozen=True)


class LettaAgentModel(StrictBoundaryModel):
    """The model identity needed by the dashboard, independent of API shape."""

    current: str = ''


class LettaAgentMessage(StrictBoundaryModel):
    """Normalized message data consumed by the dashboard activity views."""

    message_type: str = ''
    created_at: str = ''
    date: str = ''
    content: str = ''
    tool_call_name: str = ''
    tool_call_arguments: tuple[tuple[str, str], ...] = ()
    tool_return: str = ''
    approval_tool_names: tuple[str, ...] = ()
    reasoning: str = ''

    def to_legacy(self) -> dict[str, object]:
        """Adapt to the temporary dict contract used by server.py formatters."""
        payload: dict[str, object] = {'message_type': self.message_type}
        if self.created_at:
            payload['created_at'] = self.created_at
        if self.date:
            payload['date'] = self.date
        if self.content:
            payload['content'] = self.content
        if self.tool_call_name:
            payload['tool_call'] = {
                'name': self.tool_call_name,
                'arguments': dict(self.tool_call_arguments),
            }
        if self.tool_return:
            payload['tool_return'] = self.tool_return
        if self.approval_tool_names:
            payload['tool_calls'] = [
                {'name': name} for name in self.approval_tool_names
            ]
        if self.reasoning:
            payload['reasoning'] = self.reasoning
        return payload


class ILettaGateway(ABC):
    """Port consumed by agent application services."""

    @abstractmethod
    def get_agent_model(
        self,
        agent_id: str,
        *,
        timeout: float = 15,
    ) -> LettaAgentModel | None:
        """Return an agent's current model, failing closed on transport errors."""

    @abstractmethod
    def get_agent_messages(
        self,
        agent_id: str,
        *,
        limit: int = 200,
        timeout: float = 25,
    ) -> tuple[LettaAgentMessage, ...]:
        """Return normalized messages, failing closed on transport errors."""
