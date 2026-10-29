"""Cashy's sidecar: her address on the shared receptionist bridge.

Cashy is the banking navigation agent in ``~/agent_blocks/adws/cashy``. She
reads a bank page's DOM over the debug Chrome's DevTools port (no
screenshots, no Selenium or Playwright), waits for the person to sign in
themselves, and turns a guided route into a versioned playback. Her sidecar
(``adws/adw_cashy_service.py``, unit ``cashy-agent``, loopback :8770) speaks
the same NDJSON turn records receptionist_team's do, so this is a profile
module like ``sydney_service``: ``BRIDGE`` is an ``IReceptionistSidecar`` on
the same ``SidecarBridge``, ``LISTING`` the ``IListedAgent`` the Agent
Management tab shows.

No model sits in her navigation path, and she has no Letta brain to fall
back on: a dead sidecar is an error in her box that names the unit to start.
She must run on the machine whose Chrome she drives.
"""

from __future__ import annotations

import os
import urllib.request
from collections.abc import Iterator
from typing import Any

from letta_code.streaming import ConversationStreamRecord
from receptionist_sidecar import (
    DEFAULT_TURN_TIMEOUT,
    IListedAgent,
    IReceptionistSidecar,
    SidecarAgentListing,
    SidecarBridge,
    SidecarTurnRequest,
)

CASHY_SERVICE_URL = os.environ.get('CASHY_SERVICE_URL', 'http://127.0.0.1:8770')

# Her id in /api/agents. Not a Letta id. Keep in step with CASHY_AGENT_ID in
# js/implementation/agent-window-handoff.js.
CASHY_AGENT_ID = 'agent-cashy'

BRIDGE: IReceptionistSidecar = SidecarBridge(
    name='Cashy',
    base_url=CASHY_SERVICE_URL,
    unit='cashy-agent',
    # Never consulted -- she has no Letta brain -- but SidecarBridge names one.
    backend_env='CASHY_CONVERSATION_BACKEND',
    turn_timeout=DEFAULT_TURN_TIMEOUT,
)

LISTING: IListedAgent = SidecarAgentListing(
    agent_id=CASHY_AGENT_ID, name='Cashy', model='deterministic (DOM over CDP, no LLM)'
)


class CashyTurnRequest(SidecarTurnRequest):
    """One turn of Cashy's conversation."""


def health(timeout: float = 3) -> dict[str, Any]:
    """Liveness for the Server Management tab. Never raises."""
    return BRIDGE.health(timeout=timeout)


def compact() -> dict[str, Any]:
    """The Input Options "Compact Conversation" button. Never raises."""
    return BRIDGE.compact()


def stream_cashy_turn(
    request: SidecarTurnRequest,
    *,
    timeout: float = DEFAULT_TURN_TIMEOUT,
    opener=urllib.request.urlopen,
) -> Iterator[ConversationStreamRecord]:
    """Yield one of Cashy's turns, proxied from her sidecar as it arrives."""
    return BRIDGE.stream(request, timeout=timeout, opener=opener)
