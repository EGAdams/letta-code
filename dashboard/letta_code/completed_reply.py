"""Read a settled Letta answer when the headless CLI keeps its pipe open.

This is a read-only recovery adapter. A resumed dashboard conversation has a
known ID, so its latest run and persisted messages can be checked without
guessing which other conversation belongs to the same agent.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Protocol
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from hosts import LETTA_BASE_URL


class CompletedReplyProbe(Protocol):
    def completed_reply(self, agent_id: str, conversation_id: str,
                        started_at: datetime) -> str | None:
        """Return a settled answer from this request, or None while it works."""


def _timestamp(raw: object) -> datetime | None:
    if not isinstance(raw, str):
        return None
    try:
        stamp = datetime.fromisoformat(raw.replace('Z', '+00:00'))
    except ValueError:
        return None
    return stamp.replace(tzinfo=timezone.utc) if stamp.tzinfo is None else stamp


def _assistant_text(content: object) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return '\n'.join(
            item['text'] for item in content
            if isinstance(item, dict) and isinstance(item.get('text'), str)
        ).strip()
    return ''


def _has_pending_tools(messages: list[dict]) -> bool:
    requested = set()
    returned = set()
    for message in messages:
        kind = message.get('message_type')
        if kind in ('approval_request_message', 'tool_call_message'):
            calls = message.get('tool_calls') or [message.get('tool_call')]
            requested.update(
                call['tool_call_id'] for call in calls
                if isinstance(call, dict) and isinstance(call.get('tool_call_id'), str)
            )
        if kind == 'approval_response_message':
            returned.update(
                item['tool_call_id'] for item in (message.get('approvals') or [])
                if isinstance(item, dict) and isinstance(item.get('tool_call_id'), str)
            )
        if kind == 'tool_return_message':
            if isinstance(message.get('tool_call_id'), str):
                returned.add(message['tool_call_id'])
            returned.update(
                item['tool_call_id'] for item in (message.get('tool_returns') or [])
                if isinstance(item, dict) and isinstance(item.get('tool_call_id'), str)
            )
    return bool(requested - returned)


class LettaCompletedReplyProbe:
    """HTTP adapter for the completed-run and conversation-message read APIs."""

    def __init__(self, base_url: str = LETTA_BASE_URL, *, grace_seconds: int = 30,
                 timeout: int = 5, now=None):
        self.base_url = base_url.rstrip('/')
        self.grace = timedelta(seconds=grace_seconds)
        self.timeout = timeout
        self.now = now or (lambda: datetime.now(timezone.utc))

    def _get(self, path: str):
        request = Request(self.base_url + path, headers={'Accept': 'application/json'})
        with urlopen(request, timeout=self.timeout) as response:
            return json.load(response)

    def completed_reply(self, agent_id: str, conversation_id: str,
                        started_at: datetime) -> str | None:
        query = urlencode({
            'conversation_id': conversation_id,
            'agent_id': agent_id,
            'limit': 1,
            'order': 'desc',
        })
        runs = self._get(f'/v1/runs/?{query}')
        if not isinstance(runs, list) or not runs or not isinstance(runs[0], dict):
            return None
        latest = runs[0]
        created = _timestamp(latest.get('created_at'))
        completed = _timestamp(latest.get('completed_at'))
        if (
            latest.get('agent_id') != agent_id
            or latest.get('conversation_id') != conversation_id
            or latest.get('status') != 'completed'
            or latest.get('stop_reason') != 'end_turn'
            or created is None or created < started_at
            or completed is None or self.now() - completed < self.grace
        ):
            return None

        messages = self._get(f'/v1/conversations/{conversation_id}/messages?limit=200')
        if not isinstance(messages, list):
            return None
        current = [
            message for message in messages
            if isinstance(message, dict)
            and (date := _timestamp(message.get('date'))) is not None
            and date >= started_at
        ]
        # A model can emit an answer while a background client tool is still
        # running. Wait for its matching return before stopping the CLI.
        if _has_pending_tools(current):
            return None
        answers = [
            _assistant_text(message.get('content'))
            for message in reversed(current)
            if message.get('message_type') == 'assistant_message'
        ]
        return '\n\n'.join(answer for answer in answers if answer) or None
