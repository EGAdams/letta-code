"""Sydney's receptionist_team sidecar: her address on the shared bridge.

Sydney is a clone of Toyota: the same ``receptionist_team`` engine in
``~/agent_blocks/lancedb_memory`` -- LanceDB conversation memory shared with
Toyota, Groq conversation, delegation through the Claude Agent SDK -- run as
``--agent sydney`` on her own loopback port. Toyota keeps the finance work;
Sydney has everything else (code, new agents, the mechanic, the browser and
web search, the ADWs).

So this is a profile module, like ``toyota_service`` and
``mazda_receptionist_service``: ``BRIDGE`` is an ``IReceptionistSidecar`` on
the same ``SidecarBridge`` theirs are, and ``LISTING`` is the
``IListedAgent`` the Agent Management tab shows. server.py and the route
table hand both to the code that needs them.

Unlike Toyota's and Mazda's boxes, Sydney's has no Letta brain to fall back
on. A dead sidecar is an error in her box that names the unit to start, never
a quietly different agent answering in her name -- so there is no
``preferred_backend`` choice here.
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

SYDNEY_SERVICE_URL = os.environ.get('SYDNEY_SERVICE_URL', 'http://127.0.0.1:8769')

# Her id in /api/agents. Not a Letta id (letta_id_for() returns None for it),
# so the Thoughts/Messages/Tool Calls tabs show nothing rather than reaching
# Letta for an agent that isn't there. Keep in step with SYDNEY_AGENT_ID in
# js/implementation/agent-window-handoff.js.
SYDNEY_AGENT_ID = 'agent-sydney'

BRIDGE: IReceptionistSidecar = SidecarBridge(
    name='Sydney',
    base_url=SYDNEY_SERVICE_URL,
    unit='sydney-receptionist',
    # Never consulted -- she has no Letta brain -- but SidecarBridge names one.
    backend_env='SYDNEY_CONVERSATION_BACKEND',
    turn_timeout=DEFAULT_TURN_TIMEOUT,
)

LISTING: IListedAgent = SidecarAgentListing(
    agent_id=SYDNEY_AGENT_ID, name='Sydney', model='openai/gpt-oss-120b'
)


class SydneyTurnRequest(SidecarTurnRequest):
    """One turn of Sydney's conversation."""


def health(timeout: float = 3) -> dict[str, Any]:
    """Liveness for the Server Management tab. Never raises."""
    return BRIDGE.health(timeout=timeout)


def stream_sydney_turn(
    request: SidecarTurnRequest,
    *,
    timeout: float = DEFAULT_TURN_TIMEOUT,
    opener=urllib.request.urlopen,
) -> Iterator[ConversationStreamRecord]:
    """Yield one of Sydney's turns, proxied from her sidecar as it arrives."""
    return BRIDGE.stream(request, timeout=timeout, opener=opener)
