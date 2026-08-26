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

    def get_options(
        self,
        agent_id: str,
        *,
        family_prefix: str = '',
    ) -> AgentModelOptionsResponse:
        snapshot = self.gateway.get_agent_model(agent_id, timeout=15)
        current = snapshot.current if snapshot is not None else ''

        prefix = family_prefix
        inferred = not prefix
        if inferred and current:
            # No explicit override -- infer the family from the agent's own
            # live provider so the dropdown never mixes claude and chatgpt
            # models. Provider names can carry a per-human suffix
            # ('chatgpt-plus-pro-mom'), so match by prefix rather than
            # equality against the catalog's bare provider names.
            known_prefixes = {h.partition('/')[0] for h in self.allowed_options}
            current_provider = current.partition('/')[0]
            prefix = next(
                (p for p in known_prefixes if current_provider.startswith(p)), '')

        allowed = self.allowed_options
        if prefix:
            allowed = tuple(h for h in allowed if h.startswith(prefix + '/'))
            # The agent's real provider (e.g. '...-mom') won't equal the
            # catalog's bare provider, but the same model id may still be in
            # the filtered list -- treat that as "current" instead of
            # prepending a look-alike duplicate entry.
            current_model_id = current.partition('/')[2] if current else ''
            matching = next(
                (h for h in allowed if h.partition('/')[2] == current_model_id), '') \
                if current_model_id else ''
            if matching:
                current = matching
            elif not inferred:
                # An explicit family override (a pending Token switch not yet
                # saved) whose family differs from the agent's live provider --
                # the live model has no home in the requested family, so drop
                # it rather than let it force its way into the list.
                current = ''

        return AgentModelOptionsResponse(
            current=current,
            options=select_model_options(current, allowed),
        )
