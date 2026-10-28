"""Sydney's receptionist_team sidecar: an address and an agent-list row.

Sydney is a clone of Toyota: the same ``receptionist_team`` engine in
``~/agent_blocks/lancedb_memory`` -- LanceDB conversation memory shared with
Toyota, Groq conversation, delegation through the Claude Agent SDK -- run as
``--agent sydney`` on her own loopback port. Toyota keeps the finance work;
Sydney has everything else (code, new agents, the mechanic, the browser and
web search, the ADWs).

Nothing here is a bridge. ``SYDNEY`` is an ``IReceptionistSidecar`` built from
the same ``HttpReceptionistSidecar`` Toyota's is, so both speak one wire format
through one translator; ``LISTING`` is the ``IListedAgent`` the Agent
Management tab shows. server.py hands both to the code that needs them.

Unlike Toyota's box, Sydney's has no Letta brain to fall back on. A dead
sidecar is an error in her box that names the unit to start, never a quietly
different agent answering in her name.
"""

from __future__ import annotations

import os

from receptionist_sidecar import (
    HttpReceptionistSidecar,
    IListedAgent,
    IReceptionistSidecar,
    SidecarAddress,
    SidecarAgentListing,
)

SYDNEY_SERVICE_URL = os.environ.get("SYDNEY_SERVICE_URL", "http://127.0.0.1:8769")

# Her id in /api/agents. Not a Letta id (letta_id_for() returns None for it),
# so the Thoughts/Messages/Tool Calls tabs show nothing rather than reaching
# Letta for an agent that isn't there. Keep in step with SYDNEY_AGENT_ID in
# js/implementation/agent-window-handoff.js.
SYDNEY_AGENT_ID = "agent-sydney"

SYDNEY: IReceptionistSidecar = HttpReceptionistSidecar(
    SidecarAddress(url=SYDNEY_SERVICE_URL, name="Sydney", unit="sydney-receptionist")
)

LISTING: IListedAgent = SidecarAgentListing(
    agent_id=SYDNEY_AGENT_ID, name="Sydney", model="openai/gpt-oss-120b"
)
