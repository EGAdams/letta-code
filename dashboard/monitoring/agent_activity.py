"""Deriving each Letta agent's live activity dot ('active'|'error'|'idle')
from its most recent message.

Each agent's status requires a DERP-relayed round trip to the Letta API
(3-8s), fetched in parallel (not serially) and cached briefly so the
frontend's 5s poll doesn't pile up dozens of concurrent multi-agent sweeps.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable


@dataclass(frozen=True)
class Collaborators:
    """What stays behind in server.py, handed over per call."""

    letta_agents: list
    get_letta_id: Callable
    letta_messages: Callable
    cache: dict
    cache_lock: object
    cache_ttl: float


def msg_age_seconds(m, now):
    """Return how many seconds ago a message was created, or None on parse error."""
    raw = str(m.get('created_at') or m.get('date') or '').strip()
    if not raw:
        return None
    if raw.endswith('Z'):
        raw = raw[:-1] + '+00:00'
    elif len(raw) >= 19 and '+' not in raw and 'T' in raw:
        raw += '+00:00'
    try:
        ts = datetime.fromisoformat(raw[:32])
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return (now - ts).total_seconds()
    except Exception:
        return None


def agent_activity_one(deps: Collaborators, cfg, now):
    """Compute the activity status for a single agent config. Returns (dash_id, status)."""
    real_id = deps.get_letta_id(cfg)
    dash_id = real_id or f'unknown-{cfg["name"].lower()}'
    if not real_id:
        return dash_id, 'idle'
    msgs = deps.letta_messages(real_id, limit=5)
    if not msgs:
        return real_id, 'idle'
    # Sort ascending so last item is most recent message
    msgs_sorted = sorted(msgs, key=lambda m: str(m.get('created_at') or m.get('date') or ''))
    last = msgs_sorted[-1]
    age = msg_age_seconds(last, now)
    if age is None or age > 60:
        return real_id, 'idle'
    mt = last.get('message_type', '')
    if mt in ('user_message', 'tool_call_message', 'reasoning_message'):
        return real_id, 'active'
    if mt == 'tool_return_message':
        tr = last.get('tool_return', {})
        if isinstance(tr, dict) and tr.get('status') == 'error':
            return real_id, 'error'
        return real_id, 'active'
    # assistant_message or unknown — agent just finished responding
    return real_id, 'idle'


def agent_activity_status(deps: Collaborators):
    """Return {agent_id: 'active'|'error'|'idle'} for every configured Letta agent."""
    # Hold the lock for the whole get-or-compute so concurrent pollers share
    # one sweep instead of each starting their own.
    with deps.cache_lock:
        now_ts = time.time()
        cached = deps.cache.get('value')
        if cached is not None and now_ts - deps.cache.get('ts', 0.0) < deps.cache_ttl:
            return cached

        now = datetime.now(timezone.utc)
        results = {}
        with ThreadPoolExecutor(max_workers=max(1, len(deps.letta_agents))) as pool:
            for dash_id, status in pool.map(
                    lambda cfg: agent_activity_one(deps, cfg, now), deps.letta_agents):
                results[dash_id] = status

        deps.cache['value'] = results
        deps.cache['ts'] = time.time()
        return results
