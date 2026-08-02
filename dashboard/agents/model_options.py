"""Application service for the agent model-options HTTP contract."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import ConfigDict, Field

from agents.letta_gateway import ILettaGateway, StrictBoundaryModel


class AgentModelOptionsResponse(StrictBoundaryModel):
    model_config = ConfigDict(strict=True, extra='forbid', frozen=True)

    ok: bool = True
    current: str = ''
    options: tuple[str, ...] = Field(default_factory=tuple)

    def to_http(self) -> dict[str, object]:
        return {
            'ok': self.ok,
            'current': self.current,
            'options': list(self.options),
        }


def select_model_options(
    current_handle: str,
    allowed_options: tuple[str, ...],
) -> tuple[str, ...]:
    if current_handle and current_handle not in allowed_options:
        return (current_handle, *allowed_options)
    return allowed_options


@dataclass(frozen=True)
class AgentModelOptionsService:
    gateway: ILettaGateway
    allowed_options: tuple[str, ...]

    def __init__(
        self,
        gateway: ILettaGateway,
        allowed_options: tuple[str, ...] | list[str],
    ) -> None:
        object.__setattr__(self, 'gateway', gateway)
        object.__setattr__(self, 'allowed_options', tuple(allowed_options))

    def get_options(self, agent_id: str) -> AgentModelOptionsResponse:
        snapshot = self.gateway.get_agent_model(agent_id, timeout=15)
        current = snapshot.current if snapshot is not None else ''
        return AgentModelOptionsResponse(
            current=current,
            options=select_model_options(current, self.allowed_options),
        )
