"""Deterministic test adapter for the Letta gateway port."""

from __future__ import annotations

from dataclasses import dataclass, field

from agents.letta_gateway import ILettaGateway, LettaAgentMessage, LettaAgentModel


@dataclass
class FakeLettaGateway(ILettaGateway):
    models: dict[str, LettaAgentModel | None] = field(
        default_factory=dict[str, LettaAgentModel | None])
    calls: list[tuple[str, float]] = field(
        default_factory=list[tuple[str, float]])
    messages: dict[str, tuple[LettaAgentMessage, ...]] = field(
        default_factory=dict[str, tuple[LettaAgentMessage, ...]])
    message_calls: list[tuple[str, int, float]] = field(
        default_factory=list[tuple[str, int, float]])

    def get_agent_model(
        self,
        agent_id: str,
        *,
        timeout: float = 15,
    ) -> LettaAgentModel | None:
        self.calls.append((agent_id, timeout))
        return self.models.get(agent_id)

    def get_agent_messages(
        self,
        agent_id: str,
        *,
        limit: int = 200,
        timeout: float = 25,
    ) -> tuple[LettaAgentMessage, ...]:
        self.message_calls.append((agent_id, limit, timeout))
        return self.messages.get(agent_id, ())
