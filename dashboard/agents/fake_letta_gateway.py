"""Deterministic test adapter for the Letta gateway port."""

from __future__ import annotations

from dataclasses import dataclass, field

from agents.letta_gateway import ILettaGateway, LettaAgentModel


@dataclass
class FakeLettaGateway(ILettaGateway):
    models: dict[str, LettaAgentModel | None] = field(default_factory=dict)
    calls: list[tuple[str, float]] = field(default_factory=list)

    def get_agent_model(
        self,
        agent_id: str,
        *,
        timeout: float = 15,
    ) -> LettaAgentModel | None:
        self.calls.append((agent_id, timeout))
        return self.models.get(agent_id)
