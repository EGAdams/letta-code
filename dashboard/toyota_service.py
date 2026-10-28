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

The mechanics all live in ``receptionist_sidecar.py``, shared with Mazda, who
has a sidecar of her own since she stopped being a package and became a
profile. This module is now only what is Toyota's: her URL, her unit, her
override, and the names the rest of the dashboard imports.
"""

from __future__ import annotations

import os
import urllib.error
import urllib.request  # noqa: F401  (tests monkeypatch urlopen through this name)
from collections.abc import Iterator
from typing import Any

from letta_code.streaming import ConversationStreamRecord
from receptionist_sidecar import (
    DEFAULT_TURN_TIMEOUT,
    MAX_TURN_CHARS as _MAX_TURN_CHARS,
    SidecarBridge,
    SidecarTurnRequest,
)

TOYOTA_SERVICE_URL = os.environ.get('TOYOTA_SERVICE_URL', 'http://127.0.0.1:8767')
TOYOTA_TURN_TIMEOUT = DEFAULT_TURN_TIMEOUT

BRIDGE = SidecarBridge(
    name='Toyota',
    base_url=TOYOTA_SERVICE_URL,
    unit='toyota-receptionist',
    backend_env='TOYOTA_CONVERSATION_BACKEND',
    turn_timeout=TOYOTA_TURN_TIMEOUT,
)


class ToyotaTurnRequest(SidecarTurnRequest):
    """One turn of Toyota's conversation. Shape and validation are shared."""


def health(timeout: float = 3) -> dict[str, Any]:
    """Liveness for the Server Management tab. Never raises."""
    return BRIDGE.health(timeout=timeout)


def preferred_backend(probe=health) -> dict[str, Any]:
    """Which brain Toyota's box should use on this page load.

    See ``SidecarBridge.preferred_backend``. ``TOYOTA_CONVERSATION_BACKEND=letta``
    pins the old brain without probing.
    """
    return BRIDGE.preferred_backend(probe=probe)


def stream_toyota_turn(
    request: ToyotaTurnRequest,
    *,
    timeout: float = TOYOTA_TURN_TIMEOUT,
    opener=urllib.request.urlopen,
) -> Iterator[ConversationStreamRecord]:
    """Yield one turn's records, proxied from the sidecar as they arrive."""
    return BRIDGE.stream(request, timeout=timeout, opener=opener)
