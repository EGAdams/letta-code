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
