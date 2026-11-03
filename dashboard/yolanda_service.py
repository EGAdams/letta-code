"""Yolanda: Toyota's receptionist engine, dedicated to external email."""

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

YOLANDA_SERVICE_URL = os.environ.get('YOLANDA_SERVICE_URL', 'http://127.0.0.1:8771')

# Her id in /api/agents. Not a Letta id (letta_id_for() returns None for it),
# so the Thoughts/Messages/Tool Calls tabs show nothing rather than reaching
# Letta for an agent that isn't there. Keep in step with YOLANDA_AGENT_ID in
# js/implementation/agent-window-handoff.js.
YOLANDA_AGENT_ID = 'agent-yolanda'

BRIDGE: IReceptionistSidecar = SidecarBridge(
    name='Yolanda',
    base_url=YOLANDA_SERVICE_URL,
    unit='yolanda-receptionist',
    # Never consulted -- she has no Letta brain -- but SidecarBridge names one.
    backend_env='YOLANDA_CONVERSATION_BACKEND',
    turn_timeout=DEFAULT_TURN_TIMEOUT,
)

LISTING: IListedAgent = SidecarAgentListing(
    agent_id=YOLANDA_AGENT_ID, name='Yolanda', model='openai/gpt-oss-120b'
)


class YolandaTurnRequest(SidecarTurnRequest):
    """One turn of Yolanda's conversation."""


def health(timeout: float = 3) -> dict[str, Any]:
    """Liveness for the Server Management tab. Never raises."""
    return BRIDGE.health(timeout=timeout)


def compact() -> dict[str, Any]:
    """The Input Options "Compact Conversation" button. Never raises."""
    return BRIDGE.compact()


def stream_yolanda_turn(
    request: SidecarTurnRequest,
    *,
    timeout: float = DEFAULT_TURN_TIMEOUT,
    opener=urllib.request.urlopen,
) -> Iterator[ConversationStreamRecord]:
    """Yield one of Yolanda's turns, proxied from her sidecar as it arrives."""
    return BRIDGE.stream(request, timeout=timeout, opener=opener)
