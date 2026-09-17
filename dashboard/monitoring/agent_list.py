"""Building the /api/agents list: every Letta agent plus the synthetic Claude
Code entry.

Stale-while-revalidate: a cold rebuild can block >10s on the Letta roster
fetch (which trips the browser's fetch timeout), so once the cache goes
stale it is served immediately while a background thread refreshes it.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Collaborators:
    """What stays behind in server.py, handed over per call."""

    letta_agents: list
    get_letta_id: Callable
    cache: dict
    cache_lock: object
    cache_ttl: float
    build_agent_list: Callable


def refresh_agent_list_bg(deps: Collaborators):
    """Background stale-while-revalidate refresh for build_agent_list."""
    try:
        deps.build_agent_list(force_refresh=True)
    finally:
        with deps.cache_lock:
            deps.cache['refreshing'] = False


def build_agent_list(deps: Collaborators, force_refresh=False):
    """Return the agent list for /api/agents, combining Letta agents + Claude."""
    now = time.time()
    if not force_refresh:
        with deps.cache_lock:
            cached = deps.cache.get('value')
            if cached is not None:
                if now - deps.cache.get('ts', 0.0) < deps.cache_ttl:
                    return cached
                # Stale: serve it immediately and refresh in the background —
                # a cold rebuild can block >10s on the Letta roster fetch,
                # which trips the browser's fetch timeout.
                if not deps.cache.get('refreshing'):
                    deps.cache['refreshing'] = True
                    threading.Thread(
                        target=refresh_agent_list_bg, args=(deps,), daemon=True).start()
                return cached

    agents = []
    for cfg in deps.letta_agents:
        real_id = deps.get_letta_id(cfg)
        agents.append({
            'id': real_id or f'unknown-{cfg["name"].lower()}',
            'name': cfg['name'],
            'model': '',   # could fetch from Letta but keep it fast
            'letta': True,
        })
    agents.append({
        'id': 'agent-claude',
        'name': 'Claude',
        'model': 'claude-sonnet-4-6',
        'letta': False,
    })
    with deps.cache_lock:
        deps.cache['value'] = agents
        deps.cache['ts'] = now
    return agents
