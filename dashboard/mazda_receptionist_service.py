"""Bridge to Mazda's receptionist_team sidecar, and the choice of her brain.

Mazda's page can be driven by either of two brains, the same arrangement
Toyota has had:

  * her **Letta** agent, streamed by ``mazda_service.stream_mazda_turn`` --
    her original brain, with Toyota's sidecar composing shared LanceDB recall
    in front of each message
  * her **receptionist_team** sidecar (loopback :8768), a warm in-process
    agent with its own LanceDB memory, her document-verification prompt, and
    delegation to her own specialists -- this module

Mazda used to be a package of her own (``mazda_team``); she is now a profile
in ``receptionist_team``, so one codebase serves both receptionists and this
module is the thin dashboard half of hers. The mechanics are shared with
Toyota in ``receptionist_sidecar.py``; what is here is only Mazda's.

WHICH BRAIN ANSWERS, AND WHY THE BROWSER DOESN'T CHOOSE
``stream_turn`` prefers the sidecar whenever it answers ``/health``, and falls
back to the Letta stream when it doesn't. The decision is made here rather
than in the browser so that ``/api/mazda-turn`` stays one endpoint with one
request shape -- her page needs no change to gain the new brain, and loses
nothing if the sidecar is stopped. ``MAZDA_CONVERSATION_BACKEND=letta`` pins
the Letta brain without probing.

**The sidecar listens on 127.0.0.1 only, and that is load-bearing** -- see
``receptionist_sidecar.py`` for the reason.
"""

from __future__ import annotations

import os
import urllib.error
import urllib.request
from collections.abc import Iterator
from typing import Any

from letta_code.streaming import ConversationStreamRecord
from receptionist_sidecar import DEFAULT_TURN_TIMEOUT, SidecarBridge, SidecarTurnRequest

import mazda_service

MAZDA_SERVICE_URL = os.environ.get('MAZDA_SERVICE_URL', 'http://127.0.0.1:8768')
MAZDA_TURN_TIMEOUT = DEFAULT_TURN_TIMEOUT

BRIDGE = SidecarBridge(
    name='Mazda',
    base_url=MAZDA_SERVICE_URL,
    unit='mazda-receptionist',
    backend_env='MAZDA_CONVERSATION_BACKEND',
    turn_timeout=MAZDA_TURN_TIMEOUT,
)


class MazdaReceptionistTurnRequest(SidecarTurnRequest):
    """One turn of Mazda's conversation against the sidecar."""


def health(timeout: float = 3) -> dict[str, Any]:
    """Liveness for the Server Management tab. Never raises."""
    return BRIDGE.health(timeout=timeout)


def preferred_backend(probe=health) -> dict[str, Any]:
    """Which brain Mazda's page should use for this turn."""
    return BRIDGE.preferred_backend(probe=probe)


def stream_mazda_receptionist_turn(
    request: MazdaReceptionistTurnRequest,
    *,
    timeout: float = MAZDA_TURN_TIMEOUT,
    opener=urllib.request.urlopen,
) -> Iterator[ConversationStreamRecord]:
    """Yield one turn's records, proxied from the sidecar as they arrive."""
    return BRIDGE.stream(request, timeout=timeout, opener=opener)


def stream_turn(
    request: mazda_service.MazdaTurnRequest,
    *,
    choose=preferred_backend,
    sidecar=stream_mazda_receptionist_turn,
    letta=mazda_service.stream_mazda_turn,
) -> Iterator[ConversationStreamRecord]:
    """One Mazda turn, from whichever brain is available.

    The browser posts one body shape (``MazdaTurnRequest``, validated by the
    route) and gets one envelope back either way. Only the text and the
    request id cross to the sidecar: it serves exactly one session and reports
    which one answered, so ``agent`` and ``conversation_id`` -- which are
    Letta's ids -- are not forwarded.
    """
    if choose().get('backend') != 'receptionist-team':
        return letta(request)
    return sidecar(MazdaReceptionistTurnRequest(
        text=request.text, request_id=request.request_id))
