"""Strict terminal-session targets built from untrusted browser values."""

from __future__ import annotations

from collections.abc import Callable

from pydantic import Field, ValidationError, model_validator

from contracts import StrictModel


_LETTA_ID_PATTERN = r'^[A-Za-z0-9_-]+$'


class TerminalTarget(StrictModel):
    """The one Letta Code session a terminal may open.

    Letta Code rejects ``--agent`` beside ``--conversation``. More importantly,
    silently falling back from a requested conversation to an agent would open
    the wrong context window, so malformed conversation IDs produce a plain
    shell instead of an agent fallback.
    """

    agent_id: str = Field(default='', pattern=_LETTA_ID_PATTERN)
    conversation_id: str = Field(default='', pattern=_LETTA_ID_PATTERN)

    @model_validator(mode='after')
    def _only_one_selector(self) -> 'TerminalTarget':
        if self.agent_id and self.conversation_id:
            raise ValueError('terminal target accepts one Letta selector')
        return self

    @classmethod
    def from_browser_values(
        cls,
        agent: str,
        conversation: str,
        resolve_agent: Callable[[str], str | None],
    ) -> 'TerminalTarget':
        """Resolve one fail-closed target from HTTP query-string values."""
        if conversation:
            try:
                return cls(conversation_id=conversation)
            except ValidationError:
                return cls()
        if not agent:
            return cls()
        resolved = resolve_agent(agent)
        if not resolved:
            return cls()
        try:
            return cls(agent_id=resolved)
        except ValidationError:
            return cls()

    @property
    def command_line(self) -> str:
        if self.conversation_id:
            return f'letta --conversation {self.conversation_id}'
        if self.agent_id:
            return f'letta --agent {self.agent_id}'
        return ''
