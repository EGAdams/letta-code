"""Bridge to Toyota's receptionist_team sidecar.

Toyota's home-screen box can be driven by either of two brains:

  * the Letta Code CLI, streamed by ``letta_code/streaming.py`` (the original)
  * ``receptionist_team``, a separate process in ``~/agent_blocks`` that has
    LanceDB conversation memory and can delegate a request to one of the
    ``finance_team`` roles -- this module

The sidecar is a different Python (``lancedb_memory/.venv``, 3.14, with torch
and lancedb) than this stdlib-only server, so the boundary is HTTP rather than
an import. It keeps one warm agent so the embedding model loads once instead of
per turn; see ``receptionist_team/service.py`` for why.

**It listens on 127.0.0.1 only, and that is load-bearing.** A delegated turn
runs Claude with ``bypassPermissions`` and real Bash against the live
rol_finances MySQL database. This server is 0.0.0.0-bound and Tailscale-served
to a phone; the sidecar must stay unreachable from the network and be spoken
to only over loopback, from here.

Records are translated into the same NDJSON envelope
``/api/letta-code-stream`` emits, so the browser reuses its existing streaming
adapter and parses one wire format rather than two.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from collections.abc import Iterator
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from letta_code.streaming import ConversationStreamRecord

TOYOTA_SERVICE_URL = os.environ.get("TOYOTA_SERVICE_URL", "http://127.0.0.1:8767")

# A delegated finance role can grind for minutes. The acknowledgment arrives in
# the first second and then the socket is silent until the role finishes, so
# this is a read timeout across that whole gap, not a per-turn budget.
TOYOTA_TURN_TIMEOUT = 1770

_MAX_TURN_CHARS = 8000
_FORBIDDEN_INPUT_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class ToyotaTurnRequest(BaseModel):
    """Untrusted browser request for one turn of Toyota's conversation.

    ``agent`` and ``conversation_id`` are accepted but not forwarded: the
    sidecar serves exactly one session and reports which one answered. They
    exist so the browser can post the same body shape it posts to
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


def _assistant_event(text: str) -> ConversationStreamRecord:
    return ConversationStreamRecord.provider_event(
        {"message_type": "assistant_message", "content": text}
    )


def _result_event(session: str | None) -> ConversationStreamRecord:
    return ConversationStreamRecord.provider_event(
        {"type": "result", "conversation_id": session}
    )


def _translate(record: dict[str, Any]) -> ConversationStreamRecord | None:
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
        # Toyota asked the browser to open another agent's window.
        return ConversationStreamRecord.provider_event({"type": "tool_result", "name": "agent_handoff", "handoff": record["handoff"]})
    if kind == "error":
        return ConversationStreamRecord.failure(text[-1000:] or "Toyota failed")
    return None


def health(timeout: float = 3) -> dict[str, Any]:
    """Liveness for the Server Management tab. Never raises."""
    try:
        with urllib.request.urlopen(
            f"{TOYOTA_SERVICE_URL}/health", timeout=timeout
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


def preferred_backend(probe=health) -> dict[str, Any]:
    """Which brain Toyota's box should use on this page load.

    The sidecar is preferred when it answers, so the memory/finance Toyota is
    the default -- but a dead sidecar silently falls back to the Letta
    streaming brain instead of leaving Toyota mute. Set
    ``TOYOTA_CONVERSATION_BACKEND=letta`` to pin the old brain regardless.

    Probing is cheap: a refused loopback connection returns immediately.
    """
    forced = os.environ.get("TOYOTA_CONVERSATION_BACKEND", "").strip().lower()
    if forced == "letta":
        return {"backend": "letta", "forced": True, "service": None}

    status = probe(timeout=1.5)
    if status.get("ok"):
        return {"backend": "receptionist-team", "forced": False, "service": status}
    return {"backend": "letta", "forced": False, "service": status}


def stream_toyota_turn(
    request: ToyotaTurnRequest,
    *,
    timeout: float = TOYOTA_TURN_TIMEOUT,
    opener=urllib.request.urlopen,
) -> Iterator[ConversationStreamRecord]:
    """Yield one turn's records, proxied from the sidecar as they arrive."""

    body = json.dumps({"text": request.text, **({"request_id": request.request_id} if request.request_id else {})}).encode("utf-8")
    http_request = urllib.request.Request(
        f"{TOYOTA_SERVICE_URL}/turn",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        response = opener(http_request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        yield ConversationStreamRecord.failure(
            f"Toyota's receptionist service refused the turn: {detail or exc.reason}"
        )
        return
    except urllib.error.URLError as exc:
        yield ConversationStreamRecord.failure(
            "Toyota's receptionist service isn't reachable "
            f"({exc.reason}). Start toyota-receptionist in Server Management."
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
                translated = _translate(record)
                if translated is None:
                    continue
                if translated.type == "error" or record.get("kind") == "result":
                    saw_terminal = True
                yield translated
                if saw_terminal:
                    return
    except TimeoutError:
        yield ConversationStreamRecord.failure("Toyota took too long to answer")
        return
    except OSError as exc:
        yield ConversationStreamRecord.failure(f"Toyota's stream broke: {exc}")
        return

    if not saw_terminal:
        yield ConversationStreamRecord.failure(
            "Toyota's stream ended without a result"
        )
