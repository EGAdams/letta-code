"""Liz: Toyota's receptionist engine, dedicated to the Grand Rapids city income tax return."""

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

LIZ_SERVICE_URL = os.environ.get('LIZ_SERVICE_URL', 'http://127.0.0.1:8772')

# Her id in /api/agents. Not a Letta id (letta_id_for() returns None for it),
# so the Thoughts/Messages/Tool Calls tabs show nothing rather than reaching
# Letta for an agent that isn't there. Keep in step with LIZ_AGENT_ID in
# js/implementation/agent-window-handoff.js.
LIZ_AGENT_ID = 'agent-liz'

# Preparing the return from a cold start runs OCR over two PDFs; her desk ADW
# can take minutes, so her turns get more room than the default.
LIZ_TURN_TIMEOUT = max(DEFAULT_TURN_TIMEOUT, 1600)

BRIDGE: IReceptionistSidecar = SidecarBridge(
    name='Liz',
    base_url=LIZ_SERVICE_URL,
    unit='liz-receptionist',
    # Never consulted -- she has no Letta brain -- but SidecarBridge names one.
    backend_env='LIZ_CONVERSATION_BACKEND',
    turn_timeout=LIZ_TURN_TIMEOUT,
)

LISTING: IListedAgent = SidecarAgentListing(
    agent_id=LIZ_AGENT_ID, name='Liz', model='openai/gpt-oss-120b'
)


class LizTurnRequest(SidecarTurnRequest):
    """One turn of Liz's conversation."""


def health(timeout: float = 3) -> dict[str, Any]:
    """Liveness for the Server Management tab. Never raises."""
    return BRIDGE.health(timeout=timeout)


def compact() -> dict[str, Any]:
    """The Input Options "Compact Conversation" button. Never raises."""
    return BRIDGE.compact()


def stream_liz_turn(
    request: SidecarTurnRequest,
    *,
    timeout: float = LIZ_TURN_TIMEOUT,
    opener=urllib.request.urlopen,
) -> Iterator[ConversationStreamRecord]:
    """Yield one of Liz's turns, proxied from her sidecar as it arrives."""
    return BRIDGE.stream(request, timeout=timeout, opener=opener)
