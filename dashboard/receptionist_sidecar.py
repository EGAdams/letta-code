"""One bridge to a ``receptionist_team`` sidecar, reused per receptionist.

``agent_blocks/lancedb_memory/receptionist_team/service.py`` serves Toyota and
Mazda from one codebase, each on her own loopback port. This module is the
dashboard's half of that: the request shape, the record translation, the
liveness probe and the backend choice -- everything that is identical for both
of them. ``toyota_service.py`` and ``mazda_receptionist_service.py`` are thin
profile modules over it.

It exists because the NDJSON record format is a **contract across two
repositories** (see ``receptionist_team/CLAUDE.md``). Two copies of
``_translate`` would be two things to keep in step with that contract, and the
second copy is the one that would quietly fall behind.

**Sidecars are spoken to over loopback only, and that is load-bearing.** A
delegated turn runs Claude with ``bypassPermissions`` and real Bash against the
live rol_finances MySQL database. This server is 0.0.0.0-bound and
Tailscale-served to a phone; the sidecars must stay unreachable from the
network and be reached only from here.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from collections.abc import Iterator
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from letta_code.streaming import ConversationStreamRecord
from monitoring.agent_list import IListedAgent  # noqa: F401  (re-exported for the profile modules)

MAX_TURN_CHARS = 8000
_FORBIDDEN_INPUT_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')

# A delegated role can grind for minutes. The acknowledgment arrives in the
# first second and then the socket is silent until the role finishes, so this is
# a read timeout across that whole gap, not a per-turn budget.
DEFAULT_TURN_TIMEOUT = 1770


class SidecarTurnRequest(BaseModel):
    """Untrusted browser request for one turn of a receptionist's conversation.

    ``agent`` and ``conversation_id`` are accepted but not forwarded: a sidecar
    serves exactly one session and reports which one answered. They exist so
    the browser can post the same body shape it posts to
    ``/api/letta-code-stream`` and keep using one adapter. ``request_id`` is
    forwarded unchanged for durable operation replay protection.
    """

    model_config = ConfigDict(extra='forbid')

    text: str = Field(min_length=1, max_length=MAX_TURN_CHARS)
    agent: str | None = None
    conversation_id: str | None = None
    request_id: str | None = Field(default=None, pattern=r'^[A-Za-z0-9_-]{8,100}$')

    @field_validator('text')
    @classmethod
    def safe_text(cls, value: str) -> str:
        value = value.replace('\r\n', '\n').replace('\r', '\n')
        if not value.strip():
            raise ValueError('message is empty')
        if _FORBIDDEN_INPUT_RE.search(value):
            raise ValueError('message contains unsupported control characters')
        return value


class ReceptionistCompactRequest(BaseModel):
    """The Input Options "Compact Conversation" button, for one receptionist."""

    model_config = ConfigDict(extra='forbid')

    agent: Literal['toyota', 'sydney', 'cashy']


class ReceptionistAlertAckRequest(BaseModel):
    """"Got it" on one failure alert: her sidecar marks it heard."""

    model_config = ConfigDict(extra='forbid')

    agent: Literal['toyota', 'sydney', 'cashy']
    ids: list[str] | None = Field(default=None, max_length=200)


class IReceptionistSidecar(Protocol):
    """What a profile module needs from one receptionist's sidecar.

    ``SidecarBridge`` is the implementation; ``toyota_service.BRIDGE``,
    ``mazda_receptionist_service.BRIDGE`` and ``sydney_service.BRIDGE`` are
    three addresses on it, typed against this rather than against the class.
    """

    name: str
    unit: str

    def health(self, timeout: float = 3) -> dict[str, Any]: ...

    def preferred_backend(self, probe=None) -> dict[str, Any]: ...

    def compact(self, timeout: float = 120, opener=urllib.request.urlopen) -> dict[str, Any]: ...

    def alerts(self, timeout: float = 5, opener=urllib.request.urlopen) -> dict[str, Any]: ...

    def acknowledge_alerts(self, ids: list[str] | None, timeout: float = 5,
                           opener=urllib.request.urlopen) -> dict[str, Any]: ...

    def stream(
        self,
        request: SidecarTurnRequest,
        *,
        timeout: float | None = None,
        opener=urllib.request.urlopen,
    ) -> Iterator[ConversationStreamRecord]: ...


class IReceptionistTurnStream(Protocol):
    """One receptionist's turn endpoint, as a route sees it: a request in,
    the browser's envelope out. Never raises; every failure is a record."""

    def __call__(self, request: SidecarTurnRequest) -> Iterator[ConversationStreamRecord]: ...


class SidecarAgentListing(BaseModel):
    """A sidecar receptionist's row in /api/agents. Not a Letta agent.

    Satisfies monitoring.agent_list.IListedAgent, the interface its consumer
    owns, so that module never learns what kind of agent produced the row.
    """

    model_config = ConfigDict(frozen=True)

    agent_id: str
    name: str
    model: str

    def as_agent_row(self) -> dict[str, Any]:
        return {'id': self.agent_id, 'name': self.name, 'model': self.model, 'letta': False}


def _assistant_event(text: str) -> ConversationStreamRecord:
    return ConversationStreamRecord.provider_event(
        {'message_type': 'assistant_message', 'content': text})


def translate(record: dict[str, Any], name: str) -> ConversationStreamRecord | None:
    """Map one sidecar record onto the browser's envelope.

    Unknown kinds are dropped rather than guessed at -- everything on the voice
    path stops safely rather than guessing, and a record we don't understand
    must not become speech.
    """
    kind = record.get('kind')
    text = record.get('text') or ''
    if kind == 'reply' and record.get('streamed'):
        return None  # Its text was already delivered as deltas, once.
    if kind in ('acknowledgment', 'delta', 'reply'):
        return _assistant_event(text) if text.strip() else None
    if kind == 'result':
        return ConversationStreamRecord.provider_event(
            {'type': 'result', 'conversation_id': record.get('session')})
    if kind == 'work' and isinstance(record.get('work'), dict):
        return ConversationStreamRecord.provider_event(
            {'type': 'tool_result', 'name': 'receptionist_work', 'work': record['work']})
    if kind == 'handoff' and isinstance(record.get('handoff'), dict):
        # She asked the browser to open another agent's window.
        return ConversationStreamRecord.provider_event(
            {'type': 'tool_result', 'name': 'agent_handoff', 'handoff': record['handoff']})
    if kind == 'error':
        return ConversationStreamRecord.failure(text[-1000:] or f'{name} failed')
    return None


class SidecarBridge:
    """One receptionist's sidecar, as the dashboard sees it.

    Holds only what differs between them: her name, her loopback URL, the
    systemd unit to name when she is down, and the environment variable that
    pins her box to the Letta brain instead.
    """

    def __init__(
        self,
        name: str,
        base_url: str,
        unit: str,
        backend_env: str,
        turn_timeout: float = DEFAULT_TURN_TIMEOUT,
    ) -> None:
        self.name = name
        self.base_url = base_url
        self.unit = unit
        self.backend_env = backend_env
        self.turn_timeout = turn_timeout

    def health(self, timeout: float = 3) -> dict[str, Any]:
        """Liveness for the Server Management tab. Never raises."""
        try:
            with urllib.request.urlopen(f'{self.base_url}/health', timeout=timeout) as response:
                if response.status != 200:
                    return {'ok': False, 'error': f'HTTP {response.status}'}
                payload = json.loads(response.read().decode('utf-8'))
        except urllib.error.URLError as exc:
            return {'ok': False, 'error': f'{exc.reason}'}
        except Exception as exc:
            return {'ok': False, 'error': f'{type(exc).__name__}: {exc}'}
        if not isinstance(payload, dict):
            return {'ok': False, 'error': 'malformed health payload'}
        return payload

    def compact(self, timeout: float = 120, opener=urllib.request.urlopen) -> dict[str, Any]:
        """Have her model summarize the conversation so the next turn starts
        from that summary instead of the full history. Never raises; a failure
        is ``{'ok': False}`` and her session is left as it was."""
        request = urllib.request.Request(
            f'{self.base_url}/compact', data=b'{}',
            headers={'Content-Type': 'application/json'}, method='POST')
        try:
            with opener(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode('utf-8'))
        except urllib.error.URLError as exc:
            return {'ok': False, 'error': f"{self.name}'s receptionist service isn't reachable "
                                          f'({exc.reason}). Start {self.unit} in Server Management.'}
        except Exception as exc:
            return {'ok': False, 'error': f'{type(exc).__name__}: {exc}'}
        if not isinstance(payload, dict):
            return {'ok': False, 'error': 'malformed compact reply'}
        return payload

    def alerts(self, timeout: float = 5, opener=urllib.request.urlopen) -> dict[str, Any]:
        """Tasks she sent through the post office that failed and nobody has
        heard about yet. Never raises; an unreachable sidecar is
        ``{'ok': False, 'reachable': False}`` so the caller can tell "down"
        (Server Management already shows that) from "cannot read its alerts"."""
        try:
            with opener(f'{self.base_url}/alerts', timeout=timeout) as response:
                payload = json.loads(response.read().decode('utf-8'))
        except urllib.error.URLError as exc:
            return {'ok': False, 'reachable': False, 'alerts': [], 'error': f'{exc.reason}'}
        except Exception as exc:
            return {'ok': False, 'reachable': True, 'alerts': [], 'error': f'{type(exc).__name__}: {exc}'}
        if not isinstance(payload, dict) or not isinstance(payload.get('alerts'), list):
            return {'ok': False, 'reachable': True, 'alerts': [], 'error': 'malformed alerts reply'}
        return {**payload, 'reachable': True}

    def acknowledge_alerts(self, ids: list[str] | None, timeout: float = 5,
                           opener=urllib.request.urlopen) -> dict[str, Any]:
        """Mark alerts heard. Never raises; a failure is ``{'ok': False}``."""
        request = urllib.request.Request(
            f'{self.base_url}/alerts/ack', data=json.dumps({'ids': ids}).encode('utf-8'),
            headers={'Content-Type': 'application/json'}, method='POST')
        try:
            with opener(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode('utf-8'))
        except urllib.error.URLError as exc:
            return {'ok': False, 'error': f"{self.name}'s receptionist service isn't reachable ({exc.reason})."}
        except Exception as exc:
            return {'ok': False, 'error': f'{type(exc).__name__}: {exc}'}
        return payload if isinstance(payload, dict) else {'ok': False, 'error': 'malformed ack reply'}

    def preferred_backend(self, probe=None) -> dict[str, Any]:
        """Which brain her box should use on this page load.

        The sidecar is preferred when it answers, so the memory receptionist is
        the default -- but a dead sidecar silently falls back to the Letta
        streaming brain instead of leaving her mute. Set her ``backend_env`` to
        ``letta`` to pin the old brain regardless.

        Probing is cheap: a refused loopback connection returns immediately.
        """
        probe = probe or self.health
        if os.environ.get(self.backend_env, '').strip().lower() == 'letta':
            return {'backend': 'letta', 'forced': True, 'service': None}

        status = probe(timeout=1.5)
        if status.get('ok'):
            return {'backend': 'receptionist-team', 'forced': False, 'service': status}
        return {'backend': 'letta', 'forced': False, 'service': status}

    def stream(
        self,
        request: SidecarTurnRequest,
        *,
        timeout: float | None = None,
        opener=urllib.request.urlopen,
    ) -> Iterator[ConversationStreamRecord]:
        """Yield one turn's records, proxied from the sidecar as they arrive."""
        body = json.dumps({
            'text': request.text,
            **({'request_id': request.request_id} if request.request_id else {}),
        }).encode('utf-8')
        http_request = urllib.request.Request(
            f'{self.base_url}/turn',
            data=body,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )

        try:
            response = opener(http_request, timeout=timeout or self.turn_timeout)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode('utf-8', 'replace')[:500]
            yield ConversationStreamRecord.failure(
                f"{self.name}'s receptionist service refused the turn: "
                f'{detail or exc.reason}')
            return
        except urllib.error.URLError as exc:
            yield ConversationStreamRecord.failure(
                f"{self.name}'s receptionist service isn't reachable "
                f'({exc.reason}). Start {self.unit} in Server Management.')
            return

        saw_terminal = False
        try:
            with response:
                for line in response:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(record, dict):
                        continue
                    translated = translate(record, self.name)
                    if translated is None:
                        continue
                    if translated.type == 'error' or record.get('kind') == 'result':
                        saw_terminal = True
                    yield translated
                    if saw_terminal:
                        return
        except TimeoutError:
            yield ConversationStreamRecord.failure(f'{self.name} took too long to answer')
            return
        except OSError as exc:
            yield ConversationStreamRecord.failure(f"{self.name}'s stream broke: {exc}")
            return

        if not saw_terminal:
            yield ConversationStreamRecord.failure(
                f"{self.name}'s stream ended without a result")
