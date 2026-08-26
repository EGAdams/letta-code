"""Turning an agent's raw Letta messages into the rows the three tabs render.

The Thoughts, Messages and Tool Calls tabs are three readings of one stream.
They travel together because they share the parsing this module owns -- the
timestamp a row is stamped with, the age window a row has to fall inside, and
the message-type vocabulary each tab filters on -- and because the three tabs
are expected to agree about which messages exist. Split them and "Messages is
empty but Tool Calls has entries" becomes a shape mismatch rather than a fact
about the agent.

Two things make this cluster's failures quiet rather than loud:

  * Fetching is slow. The Letta box is reachable only over a Tailscale DERP
    relay, and a round trip regularly takes 10-25s -- close enough to the
    browser's 30s fetch abort to look like a hang. `cached_thoughts` therefore
    serves the last-known value from a `BackgroundResultProxy` while a refresh
    runs off-thread, which also means an exception raised in here surfaces as a
    line in the refresh log rather than a 500. That is the right trade for a
    tab, but it does mean a raise has to be worth reading.

  * One of the two fetch paths is untyped. Agent-wide history arrives through
    `ILettaGateway`, which normalises every message. An isolated scan
    conversation does not: it comes back from `letta_get` as whatever
    `json.loads` produced. `ConversationMessages` below is that seam.

`letta_messages`, `letta_get` and `_msg_age_seconds` stay in server.py -- other
callers there need them -- and arrive in a `Collaborators` bundle built fresh
per call, never imported. An import-time binding here would quietly detach this
module from a test that replaced any of them on `server` while still looking
exactly like it had been patched.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, field_validator

from agent_thoughts import message_text as _msg_text, select_thoughts
from background_result_proxy import BackgroundResultProxy

#: Only show conversation rows from the last 5 hours. Read by nothing else.
MESSAGES_MAX_AGE_SECONDS = 5 * 3600

#: How many messages a tab asks for. The tabs render a recent slice, not history.
AGENT_HISTORY_LIMIT = 200
CONVERSATION_LIMIT = 80


@dataclass(frozen=True)
class Collaborators:
    """server.py's half of this cluster, resolved per call."""

    letta_messages: Callable[..., list]
    letta_get: Callable[..., object]
    msg_age_seconds: Callable[..., Optional[float]]


class ConversationMessages(BaseModel):
    """What came back from `/v1/conversations/<id>/messages`.

    Every other message this module renders arrives through `ILettaGateway`,
    which pins the shape. This one endpoint bypasses it, and the hand-rolled
    unwrapping shrugged at everything: a bare list, a `{'messages': [...]}`
    envelope, a `{'results': [...]}` envelope, or anything else at all, which
    became `[]`. That last branch is the problem -- an empty list is also what a
    perfectly healthy agent that has not spoken yet returns, so "the payload
    changed shape" and "there is nothing to show" rendered as the same empty
    tab, and only one of them is a bug.

    `{'messages': None}` was worse than ambiguous. `.get('messages', fallback)`
    returns the stored None rather than the fallback, because the key is
    present -- so None, not a list, was handed to `select_thoughts`, and the
    failure landed several frames from its cause.

    Validated here instead, at the boundary, where the raise names the endpoint
    that changed. The proxy catches it, logs it, and keeps serving the last good
    value, so a shape change costs a log line rather than a blank tab.
    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    messages: list[dict]

    @field_validator('messages', mode='before')
    @classmethod
    def _unwrap(cls, payload: object) -> object:
        """Accept the three shapes the endpoint is known to return, and only those."""
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ('messages', 'results'):
                if key in payload:
                    return payload[key]
            raise ValueError(
                "conversation payload has neither 'messages' nor 'results': "
                f'{sorted(payload)[:8]}')
        raise ValueError(f'conversation payload is not a list or object: {type(payload).__name__}')


def _msg_date(m):
    """Return the best available timestamp string for a Letta message."""
    return str(m.get('created_at') or m.get('date') or '')[:19]


def _conversation_messages(conversation_id, deps: Collaborators, limit=CONVERSATION_LIMIT):
    """Fetch messages from an isolated intake conversation.

    A failed fetch (`letta_get` returns None on any error) still yields `[]`:
    that is a network fact, not a shape change, and the tab has always shown it
    as empty. Anything that did come back has to be one of the shapes
    `ConversationMessages` knows.
    """
    data = deps.letta_get(
        f'/v1/conversations/{quote(conversation_id, safe="")}/messages?limit={limit}',
        timeout=25,
    )
    if data is None:
        return []
    return ConversationMessages(messages=data).messages


def letta_thoughts(agent_id, conversation_id='', *, deps: Collaborators):
    """The Thoughts tab: reasoning entries, from a scan conversation if the
    agent has one, otherwise from its agent-wide history."""
    msgs = (
        _conversation_messages(conversation_id, deps)
        if conversation_id
        else deps.letta_messages(agent_id, limit=AGENT_HISTORY_LIMIT)
    )
    return select_thoughts(msgs, _msg_text, _msg_date)


def _load_thoughts(deps, agent_id, conversation_id):
    """Proxy loader. Deps lead so the proxy can pass all three positionally."""
    return letta_thoughts(agent_id, conversation_id, deps=deps)


_thoughts_proxy = BackgroundResultProxy(
    loader=_load_thoughts, refresh_seconds=3, name='thoughts')


def cached_thoughts(agent_id, conversation_id='', *, deps: Collaborators):
    """Non-blocking `letta_thoughts` -- serves the last-known value while a
    background refresh runs, rather than blocking the request thread on the
    live Letta call (which can take 10-25s over the Tailscale DERP relay,
    close enough to the browser's 30s fetch abort to look like a hang).
    Applies whether or not the agent has an isolated scan conversation,
    since a full agent-history fetch (conversation_id='') is exactly as
    slow as a conversation-scoped one.

    Keyed on both ids: keying on the conversation alone put every agent with no
    active scan into the same '' bucket, so two agents shared one answer.
    """
    return _thoughts_proxy.get(
        (agent_id, conversation_id), deps, agent_id, conversation_id, default=[])


def within_max_age(m, now, *, deps: Collaborators):
    """True if a message's timestamp is within MESSAGES_MAX_AGE_SECONDS.

    Deliberately fail-open: a timestamp we cannot parse is shown rather than
    hidden, because dropping a message is the less recoverable mistake.
    """
    age = deps.msg_age_seconds(m, now)
    return age is None or age <= MESSAGES_MAX_AGE_SECONDS


def letta_convo(agent_id, *, deps: Collaborators):
    """The Messages tab: the user/assistant exchange, recent entries only."""
    msgs = deps.letta_messages(agent_id, limit=AGENT_HISTORY_LIMIT)
    now = datetime.now(timezone.utc)
    rows = []
    for m in msgs:
        mt = m.get('message_type', '')
        if mt not in ('user_message', 'assistant_message'):
            continue
        if not within_max_age(m, now, deps=deps):
            continue
        text = _msg_text(m)
        if not text.strip():
            continue
        rows.append({
            'date': _msg_date(m),
            'type': mt,
            'text': text,
        })
    return rows


def letta_toolcalls(agent_id, *, deps: Collaborators):
    """The Tool Calls tab: each call named by its tool, each return by outcome.

    No age filter, unlike the Messages tab -- a tool call is evidence of what
    the agent did, and the tab is read after the fact.
    """
    msgs = deps.letta_messages(agent_id, limit=AGENT_HISTORY_LIMIT)
    rows = []
    for m in msgs:
        mt = m.get('message_type', '')
        if mt not in ('tool_call_message', 'tool_return_message'):
            continue
        text = _msg_text(m)
        if not text.strip():
            continue
        display_type = 'tool_call' if mt == 'tool_call_message' else 'tool_return'
        if mt == 'tool_call_message':
            tc = m.get('tool_call', {})
            display_type = tc.get('name', 'tool_call')
        rows.append({
            'date': _msg_date(m),
            'type': display_type,
            'text': text[:300],
        })
    return rows
