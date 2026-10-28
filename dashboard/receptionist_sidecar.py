"""IReceptionistSidecar -- one receptionist_team sidecar, as the dashboard sees it.

Toyota and Sydney are the same ``receptionist_team`` engine in
``~/agent_blocks/lancedb_memory``, run as two sidecars on two loopback ports
(``--agent toyota`` on :8767, ``--agent sydney`` on :8769). The dashboard's
side of either one is identical: probe ``/health``, POST ``/turn``, translate
the NDJSON records into the envelope ``/api/letta-code-stream`` emits. Only the
address differs.

So the routes depend on ``IReceptionistSidecar`` and the agent list on
``monitoring.agent_list.IListedAgent``; ``HttpReceptionistSidecar`` is the one implementation, and
``toyota_service.py`` / ``sydney_service.py`` are each just an address handed
to it. A third receptionist is a third address, not a third copy of this code.

**Loopback only, and that is load-bearing.** A delegated turn runs Claude with
``bypassPermissions`` and real Bash against live data. This server is
0.0.0.0-bound and Tailscale-served to a phone; a sidecar must stay
unreachable from the network and be spoken to only from here.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from letta_code.streaming import ConversationStreamRecord
from monitoring.agent_list import IListedAgent  # noqa: F401  (re-exported for the sidecar modules)

# A delegated role can grind for minutes. The acknowledgment arrives in the
# first second and then the socket is silent until the role finishes, so this
# is a read timeout across that whole gap, not a per-turn budget.
TURN_TIMEOUT = 1770

_MAX_TURN_CHARS = 8000
_FORBIDDEN_INPUT_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class ReceptionistTurnRequest(BaseModel):
    """Untrusted browser request for one turn of a receptionist's conversation.

    ``agent`` and ``conversation_id`` are accepted but not forwarded: a sidecar
    serves exactly one session and reports which one answered. They exist so
    the browser can post the same body shape it posts to
    ``/api/letta-code-stream`` and keep using one adapter.
    ``request_id`` is forwarded unchanged for durable operation replay protection.
    """

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=_MAX_TURN_CHARS)
    agent: str | None = None
    conversation_id: str | None = None
    request_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{8,100}$")

    @field_validator("text")
    @classmethod
    def safe_text(cls, value: str) -> str:
        value = value.replace("\r\n", "\n").replace("\r", "\n")
        if not value.strip():
            raise ValueError("message is empty")
        if _FORBIDDEN_INPUT_RE.search(value):
            raise ValueError("message contains unsupported control characters")
        return value


class SidecarAddress(BaseModel):
    """Where one receptionist's sidecar lives, and how errors name it."""

    model_config = ConfigDict(frozen=True)

    url: str        # loopback base URL, e.g. http://127.0.0.1:8767
    name: str       # "Toyota" -- what an error in her box calls her
    unit: str       # "toyota-receptionist" -- what to start in Server Management


Opener = Callable[..., Any]


class IReceptionistSidecar(Protocol):
    """What a route needs from a receptionist's sidecar, and nothing more."""

    @property
    def address(self) -> SidecarAddress: ...

    def health(self, timeout: float = 3) -> dict[str, Any]:
        """Liveness for Server Management and backend choice. Never raises."""
        ...

    def stream_turn(
        self,
        request: ReceptionistTurnRequest,
        *,
        timeout: float = TURN_TIMEOUT,
        opener: Opener | None = None,
    ) -> Iterator[ConversationStreamRecord]:
        """One turn's records in the browser's envelope. Fails closed, never raises."""
        ...


class SidecarAgentListing(BaseModel):
    """A sidecar receptionist's row in /api/agents. Not a Letta agent.

    Satisfies monitoring.agent_list.IListedAgent, the interface its consumer owns.
    """

    model_config = ConfigDict(frozen=True)

    agent_id: str
    name: str
    model: str

    def as_agent_row(self) -> dict[str, Any]:
        return {"id": self.agent_id, "name": self.name, "model": self.model, "letta": False}


def _assistant_event(text: str) -> ConversationStreamRecord:
    return ConversationStreamRecord.provider_event(
        {"message_type": "assistant_message", "content": text}
    )


def _result_event(session: str | None) -> ConversationStreamRecord:
    return ConversationStreamRecord.provider_event(
        {"type": "result", "conversation_id": session}
    )


def translate(record: dict[str, Any], name: str) -> ConversationStreamRecord | None:
    """Map one sidecar record onto the browser's envelope.

    Unknown kinds are dropped rather than guessed at -- everything on the
    voice path fails closed, and a record we don't understand must not become
    speech.
    """
    kind = record.get("kind")
    text = record.get("text") or ""
    if kind in ("acknowledgment", "reply"):
        return _assistant_event(text) if text.strip() else None
    if kind == "result":
        return _result_event(record.get("session"))
    if kind == "work" and isinstance(record.get("work"), dict):
        return ConversationStreamRecord.provider_event({"type": "tool_result", "name": "receptionist_work", "work": record["work"]})
    if kind == "handoff" and isinstance(record.get("handoff"), dict):
        # The receptionist asked the browser to open another agent's window.
        return ConversationStreamRecord.provider_event({"type": "tool_result", "name": "agent_handoff", "handoff": record["handoff"]})
    if kind == "error":
        return ConversationStreamRecord.failure(text[-1000:] or f"{name} failed")
    return None


class HttpReceptionistSidecar:
    """IReceptionistSidecar over loopback HTTP. One instance per receptionist."""

    def __init__(self, address: SidecarAddress) -> None:
        self._address = address

    @property
    def address(self) -> SidecarAddress:
        return self._address

    def health(self, timeout: float = 3) -> dict[str, Any]:
        try:
            # Looked up at call time, so a test can monkeypatch urlopen.
            with urllib.request.urlopen(
                f"{self._address.url}/health", timeout=timeout
            ) as response:
                if response.status != 200:
                    return {"ok": False, "error": f"HTTP {response.status}"}
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            return {"ok": False, "error": f"{exc.reason}"}
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        if not isinstance(payload, dict):
            return {"ok": False, "error": "malformed health payload"}
        return payload

    def stream_turn(
        self,
        request: ReceptionistTurnRequest,
        *,
        timeout: float = TURN_TIMEOUT,
        opener: Opener | None = None,
    ) -> Iterator[ConversationStreamRecord]:
        name, unit = self._address.name, self._address.unit
        open_url = opener or urllib.request.urlopen
        body = json.dumps({"text": request.text, **({"request_id": request.request_id} if request.request_id else {})}).encode("utf-8")
        http_request = urllib.request.Request(
            f"{self._address.url}/turn",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            response = open_url(http_request, timeout=timeout)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:500]
            yield ConversationStreamRecord.failure(
                f"{name}'s receptionist service refused the turn: {detail or exc.reason}"
            )
            return
        except urllib.error.URLError as exc:
            yield ConversationStreamRecord.failure(
                f"{name}'s receptionist service isn't reachable "
                f"({exc.reason}). Start {unit} in Server Management."
            )
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
                    translated = translate(record, name)
                    if translated is None:
                        continue
                    if translated.type == "error" or record.get("kind") == "result":
                        saw_terminal = True
                    yield translated
                    if saw_terminal:
                        return
        except TimeoutError:
            yield ConversationStreamRecord.failure(f"{name} took too long to answer")
            return
        except OSError as exc:
            yield ConversationStreamRecord.failure(f"{name}'s stream broke: {exc}")
            return

        if not saw_terminal:
            yield ConversationStreamRecord.failure(
                f"{name}'s stream ended without a result"
            )
