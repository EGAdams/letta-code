"""Which agents' voice uploads may take the Pipecat media path.

The pilot started as one agent (``config.PIPECAT_PILOT_AGENT_ID``, Toyota). A
receptionist cloned from her -- Sydney -- shares her mechanics end to end, so
her uploads have to be admitted on the same terms, or her Start button falls
back to a slower transcriber Toyota never uses.

Callers ask an ``IVoiceMediaAdmission``; the route modules never compare ids
themselves. The pilot id is read on every call, not captured, so a test
monkeypatching ``config`` (or an env change on restart) is always seen.
"""
from __future__ import annotations

from typing import Protocol

from . import config

PIPECAT = 'pipecat'
WHISPER = 'whisper'


class IVoiceMediaAdmission(Protocol):
    def admits(self, agent_id: str | None) -> bool:
        """True when this agent's uploads may use the Pipecat media path."""
        ...

    def backend_for(self, agent_id: str | None) -> str:
        """``'pipecat'`` when admitted, else ``'whisper'``."""
        ...


class PilotAgentAdmission:
    """The configured pilot agent, plus agents that share its voice.

    Sharing agents ride on the pilot: with no pilot configured, nobody is
    admitted, so turning the pilot off turns it off for the clones too.
    """

    def __init__(self, sharing_agent_ids: tuple[str, ...] = ()) -> None:
        self._sharing = frozenset(sharing_agent_ids)

    def admits(self, agent_id: str | None) -> bool:
        pilot = config.PIPECAT_PILOT_AGENT_ID
        if not pilot or not agent_id:
            return False
        return agent_id == pilot or agent_id in self._sharing

    def backend_for(self, agent_id: str | None) -> str:
        return PIPECAT if self.admits(agent_id) else WHISPER
