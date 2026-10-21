"""Mazda's voice turn: shared LanceDB recall in front, Letta in the middle.

Mazda's identity, conversation, memory blocks and tools all stay in Letta --
the turn itself is ``letta_code/streaming.py``'s CLI stream, unchanged. This
module only decorates it:

  * before the turn, Toyota's sidecar composes recalled context (from Mazda's
    own LanceDB session and Toyota's) in front of the user's words
  * after the turn, the finished exchange is handed back to the sidecar so
    Toyota can recall it too
  * a whole-reply ``OPEN_AGENT: toyota`` -- "put Toyota on the horn" -- becomes
    an ``agent_handoff`` tool result the browser acts on instead of speech

Shared memory is fail-open: a sidecar that is down or slow costs Mazda her
recall, never her turn. The sidecar is spoken to over loopback only, for the
reason given in ``toyota_service.py``.
"""

from __future__ import annotations

import json
import os
import re
import threading
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from letta_code.runner import _LETTA_CODE_FORBIDDEN_INPUT_RE, _LETTA_CODE_MAX_PROMPT_CHARS
from letta_code.streaming import (
    ConversationStreamRecord,
    ConversationStreamRequest,
    stream_letta_code_message,
)
from letta_ids import _TERMINAL_ID_RE
from toyota_service import TOYOTA_SERVICE_URL

MAZDA_AGENT_ID = os.environ.get(
    'MAZDA_AGENT_ID', 'agent-6b536cf4-ec88-4290-b595-fed21d14bd8e')

# The sidecar's MemorySession for Mazda's LanceDB turns.
MEMORY_SESSION = 'mazda'
MEMORY_TIMEOUT = 8
_MAX_TURN_CHARS = 8000

# Told to Mazda on every voice turn, because her Letta memory blocks are hers
# and this dashboard doesn't edit them.
HORN_NOTE = (
    '[Dashboard voice note: if the user asks to talk to Toyota, go back to the '
    'receptionist, or "put Toyota on the horn", reply with exactly '
    '"OPEN_AGENT: toyota" (optionally followed by " | <short sentence to say>") '
    'and nothing else.]'
)

_DIRECTIVE = 'OPEN_AGENT:'
_HORN_RE = re.compile(r'OPEN_AGENT:\s*toyota\s*(?:\|\s*(.*))?', re.IGNORECASE | re.DOTALL)


class MazdaTurnRequest(BaseModel):
    """Untrusted browser request: the same body the streaming adapter posts."""

    model_config = ConfigDict(extra='forbid')

    text: str = Field(min_length=1, max_length=_MAX_TURN_CHARS)
    agent: str | None = None
    conversation_id: str | None = None
    request_id: str | None = Field(default=None, pattern=r'^[A-Za-z0-9_-]{8,100}$')

    @field_validator('text')
    @classmethod
    def safe_text(cls, value: str) -> str:
        value = value.replace('\r\n', '\n').replace('\r', '\n')
        if not value.strip():
            raise ValueError('message is empty')
        if _LETTA_CODE_FORBIDDEN_INPUT_RE.search(value):
            raise ValueError('message contains unsupported control characters')
        return value

    @field_validator('agent')
    @classmethod
    def only_mazda(cls, value: str | None) -> str | None:
        if value is not None and value != MAZDA_AGENT_ID:
            raise ValueError('this route only talks to Mazda')
        return value

    @field_validator('conversation_id')
    @classmethod
    def safe_conversation_id(cls, value: str | None) -> str | None:
        if value is not None and not _TERMINAL_ID_RE.fullmatch(value):
            raise ValueError('invalid Letta conversation id')
        return value


def _post_memory(route: str, payload: dict[str, Any], opener=urllib.request.urlopen) -> dict[str, Any]:
    """POST to the sidecar's shared memory. Never raises."""
    request = urllib.request.Request(
        f'{TOYOTA_SERVICE_URL}{route}',
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with opener(request, timeout=MEMORY_TIMEOUT) as response:
            result = json.loads(response.read().decode('utf-8'))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return {'ok': False, 'error': f'{type(exc).__name__}: {exc}'}
    return result if isinstance(result, dict) else {'ok': False, 'error': 'malformed reply'}


def compose_prompt(text: str, post=_post_memory) -> str:
    """User text with shared recall in front, or the plain text if recall fails."""
    composed = post('/memory/compose', {'session': MEMORY_SESSION, 'text': text})
    prompt = composed.get('prompt') if composed.get('ok') else None
    if not isinstance(prompt, str) or not prompt.strip():
        prompt = text
    prompt = f'{HORN_NOTE}\n\n{prompt}'
    prompt = _LETTA_CODE_FORBIDDEN_INPUT_RE.sub('', prompt)
    if len(prompt) > _LETTA_CODE_MAX_PROMPT_CHARS:
        prompt = f'{HORN_NOTE}\n\n{text}'
    return prompt


def _record_in_background(user: str, agent: str, post) -> None:
    payload = {'session': MEMORY_SESSION, 'user': user[:_MAX_TURN_CHARS],
               'agent': agent[:_MAX_TURN_CHARS * 4]}
    threading.Thread(target=post, args=('/memory/record', payload), daemon=True).start()


def _assistant_delta(event: dict[str, Any] | None) -> str:
    """The same text the browser adapter speaks for this provider event."""
    if not isinstance(event, dict):
        return ''
    provider = event.get('event') if event.get('type') == 'stream_event' else event
    if not isinstance(provider, dict) or provider.get('message_type') != 'assistant_message':
        return ''
    content = provider.get('content')
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return ''.join(
            part if isinstance(part, str)
            else part.get('text', '') if isinstance(part, dict) and isinstance(part.get('text'), str)
            else ''
            for part in content
        )
    return ''


def _could_be_directive(text: str) -> bool:
    head = text.lstrip().upper()
    return _DIRECTIVE.startswith(head) or head.startswith(_DIRECTIVE)


def _handoff_records(spoken: str) -> list[ConversationStreamRecord]:
    return [
        ConversationStreamRecord.provider_event({
            'type': 'tool_result', 'name': 'agent_handoff',
            'handoff': {'agent': 'toyota', 'name': 'Toyota'},
        }),
        ConversationStreamRecord.provider_event({
            'message_type': 'assistant_message',
            'content': spoken or 'Putting Toyota on the horn.',
        }),
    ]


def stream_mazda_turn(
    request: MazdaTurnRequest,
    *,
    stream: Callable[[ConversationStreamRequest], Iterator[ConversationStreamRecord]] = stream_letta_code_message,
    post=_post_memory,
) -> Iterator[ConversationStreamRecord]:
    """Yield one Mazda turn in the /api/letta-code-stream envelope.

    Assistant text streams through untouched, except that text which might
    still turn out to be an OPEN_AGENT directive is held until it either
    diverges from one or the turn ends -- so the directive is never spoken.
    """
    letta_request = ConversationStreamRequest(
        agent=MAZDA_AGENT_ID,
        text=compose_prompt(request.text, post),
        conversation_id=request.conversation_id,
    )
    reply = ''
    held: list[ConversationStreamRecord] = []
    streaming = False
    for record in stream(letta_request):
        event = record.event if record.type == 'event' else None
        delta = _assistant_delta(event)
        if delta:
            reply += delta
            if streaming:
                yield record
            elif _could_be_directive(reply):
                held.append(record)
            else:
                streaming = True
                yield from held
                held = []
                yield record
            continue

        if isinstance(event, dict) and event.get('type') == 'result':
            spoken = reply
            match = None if streaming else _HORN_RE.fullmatch(reply.strip())
            if match:
                spoken = (match.group(1) or '').strip() or 'Putting Toyota on the horn.'
                yield from _handoff_records(spoken)
            else:
                yield from held
            held = []
            _record_in_background(request.text, spoken, post)
            yield record
            return

        if record.type == 'error':
            yield from held
            held = []
        yield record
    yield from held
