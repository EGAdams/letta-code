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

The bridge itself is ``receptionist_sidecar.HttpReceptionistSidecar``, an
``IReceptionistSidecar``; this module is Toyota's address on it plus the one
thing only she has, a Letta brain to fall back on (``preferred_backend``).
Sydney is the same sidecar at another address -- see ``sydney_service.py``.
"""

from __future__ import annotations

import os
import urllib.request
from collections.abc import Iterator
from typing import Any

from letta_code.streaming import ConversationStreamRecord

from receptionist_sidecar import (
    TURN_TIMEOUT,
    HttpReceptionistSidecar,
    IReceptionistSidecar,
    ReceptionistTurnRequest,
    SidecarAddress,
    translate,
)

TOYOTA_SERVICE_URL = os.environ.get("TOYOTA_SERVICE_URL", "http://127.0.0.1:8767")

TOYOTA_TURN_TIMEOUT = TURN_TIMEOUT

# Historical name; the request shape is the same for every receptionist.
ToyotaTurnRequest = ReceptionistTurnRequest

TOYOTA: IReceptionistSidecar = HttpReceptionistSidecar(
    SidecarAddress(url=TOYOTA_SERVICE_URL, name="Toyota", unit="toyota-receptionist")
)


def _translate(record: dict[str, Any]) -> ConversationStreamRecord | None:
    return translate(record, TOYOTA.address.name)


def health(timeout: float = 3) -> dict[str, Any]:
    """Liveness for the Server Management tab. Never raises."""
    return TOYOTA.health(timeout)


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
    request: ReceptionistTurnRequest,
    *,
    timeout: float = TOYOTA_TURN_TIMEOUT,
    opener=urllib.request.urlopen,
) -> Iterator[ConversationStreamRecord]:
    """Yield one turn's records, proxied from the sidecar as they arrive."""
    return TOYOTA.stream_turn(request, timeout=timeout, opener=opener)
