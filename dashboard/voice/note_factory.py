"""Composition root for the note-command channel (Factory).

The only place the concrete Letta client, the concrete strategies, and the
filesystem repository are constructed. Both strategies share one LettaClient and
one already-resolved agent id, so a single browser request never re-resolves the
agent roster twice.
"""
from . import config
from .letta_client import LettaClient
from .note_completeness import LettaCommandCompletenessStrategy
from .note_interpreter import LettaNoteCommandInterpreter
from .note_repository import build_note_repository
from .note_service import NoteCommandService

_CACHED = None


def resolve_note_command_agent(client) -> str:
    """The worker agent's id, or "" when Letta can't be reached.

    Both strategies already treat a missing agent id as "fail closed", so an
    unreachable Letta makes the command channel wait for a working connection
    rather than raising out of the request handler.
    """
    if config.NOTE_COMMAND_AGENT_ID:
        return config.NOTE_COMMAND_AGENT_ID
    try:
        return client.resolve_agent_id(config.NOTE_COMMAND_AGENT_NAME) or ""
    except Exception:
        return ""


def build_note_command_service(client=None, agent_id=None):
    """Returns (service, agent_id) — the id is what tells the caller whether
    this service was built against a reachable Letta."""
    client = client or LettaClient(config.LETTA_BASE_URL)
    agent_id = agent_id if agent_id is not None else resolve_note_command_agent(client)
    service = NoteCommandService(
        completeness=LettaCommandCompletenessStrategy(client, agent_id),
        interpreter=LettaNoteCommandInterpreter(client, agent_id),
        repository=build_note_repository(),
    )
    return service, agent_id


def note_command_service() -> NoteCommandService:
    """Process-wide instance.

    The completeness detector runs on every finalized speech fragment, so
    resolving the agent id per request would put a `GET /v1/agents` in front of
    each one. A service built while Letta was down is deliberately *not* cached,
    or the process would keep an unresolved agent id for its whole life.
    """
    global _CACHED
    if _CACHED is not None:
        return _CACHED
    service, agent_id = build_note_command_service()
    if agent_id:
        _CACHED = service
    return service
