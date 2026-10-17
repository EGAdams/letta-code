"""Context-window usage and the two-step conversation-flush flow.

Backs the Input Options page's Context bar, "Save to Memory" (Letta's
built-in POST /summarize compaction: writes a memory summary and shrinks
history) and "Clear Conversation" (PATCH /reset-messages: wipes ALL messages
for the agent -- there is no partial "keep last N" in the Letta API, which is
why the dashboard only offers Clear after a Save has just run; see
conversation-context-panel.js).

Self-contained on purpose: `_letta_id_for` and `_letta_get` below are the same
trivial, stateless checks server.py already has (agent-id shape validation, a
bare GET) -- duplicated rather than imported so this module never needs a
`server` import, which would cycle (server.py imports http_app, which would
import this). Nothing here is cached or slow enough to need the
Collaborators-per-call indirection agents/message_views.py uses.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from hosts import LETTA_BASE_URL


def _letta_id_for(agent_id: str) -> str | None:
    if not agent_id or agent_id == 'agent-claude':
        return None
    if agent_id.startswith('agent-') and len(agent_id) > 15:
        return agent_id
    return None


def _letta_get(path: str, timeout: float = 15):
    try:
        with urllib.request.urlopen(f'{LETTA_BASE_URL}{path}', timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def context_payload(agent_id: str) -> dict:
    """Current/max context-window token usage for one agent."""
    lid = _letta_id_for(agent_id)
    if not lid:
        return {'ok': False, 'error': 'not a Letta agent', 'current': 0, 'max': 0}
    data = _letta_get(f'/v1/agents/{lid}/context', timeout=15)
    if not data:
        return {'ok': False, 'error': 'could not reach Letta', 'current': 0, 'max': 0}
    return {
        'ok': True,
        'current': data.get('context_window_size_current', 0),
        'max': data.get('context_window_size_max', 0),
    }


def compact(agent_id: str) -> dict:
    """Trigger Letta's built-in summarize/compaction for one agent."""
    lid = _letta_id_for(agent_id)
    if not lid:
        return {'ok': False, 'error': 'not a Letta agent'}
    req = urllib.request.Request(
        f'{LETTA_BASE_URL}/v1/agents/{lid}/summarize',
        data=json.dumps({}).encode(),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            resp = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {'ok': False, 'error': f'letta {e.code}: {e.read().decode()[:200]}'}
    except Exception as e:
        return {'ok': False, 'error': str(e)}
    return {
        'ok': True,
        'summary': resp.get('summary', ''),
        'num_messages_before': resp.get('num_messages_before', 0),
        'num_messages_after': resp.get('num_messages_after', 0),
    }


def reset_messages(agent_id: str) -> dict:
    """Wipe ALL of an agent's message history. Irreversible; see module doc."""
    lid = _letta_id_for(agent_id)
    if not lid:
        return {'ok': False, 'error': 'not a Letta agent'}
    req = urllib.request.Request(
        f'{LETTA_BASE_URL}/v1/agents/{lid}/reset-messages',
        data=json.dumps({'add_default_initial_messages': False}).encode(),
        headers={'Content-Type': 'application/json'},
        method='PATCH',
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            r.read()
    except urllib.error.HTTPError as e:
        return {'ok': False, 'error': f'letta {e.code}: {e.read().decode()[:200]}'}
    except Exception as e:
        return {'ok': False, 'error': str(e)}
    return {'ok': True}
