"""Checking whether a Letta agent is structurally and functionally healthy.

Structural: ID resolvable + required tools attached. Functional: no send
error recorded by a recent /api/test, and (for Claude-SDK agents) the
/claude_sdk work endpoint isn't 404ing or unreachable.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable


def uses_claude_sdk(cfg):
    """True for agents whose tool calls hit the /claude_sdk WORK endpoint — either
    flagged explicitly (Frita, who has no required_tools) or via run_claude_code_sdk
    in required_tools (the Mazda minions)."""
    return bool(cfg.get('uses_claude_sdk')) or 'run_claude_code_sdk' in cfg.get('required_tools', [])


@dataclass(frozen=True)
class Collaborators:
    """What stays behind in server.py, handed over per call."""

    letta_agents: list
    get_letta_id: Callable
    letta_get: Callable
    agent_send_errors: dict
    agent_send_errors_lock: object
    probe_claude_sdk_endpoint: Callable
    frita_exec_work_url: str
    cache: dict
    cache_lock: object
    cache_ttl: float


def agent_health_check(deps: Collaborators, cfg, timeout=15, sdk_status=None):
    """Check if an agent is structurally healthy: ID resolvable + required tools attached.
    Also checks agent_send_errors for functional failures recorded by /api/test, and
    (for Claude-SDK agents) that the /claude_sdk work endpoint isn't 404ing.

    Returns {ok, text, name} — ok=False turns the agent's tab red in the dashboard.
    Uses a longer timeout than letta_get's default (6s) because the /tools endpoint
    returns verbose JSON for agents with many tools over the DERP relay.

    sdk_status, when provided, is a pre-computed probe_claude_sdk_endpoint() result
    shared across a health sweep so the work endpoint is probed once, not per-agent."""
    name = cfg.get('name', '?')
    real_id = deps.get_letta_id(cfg)
    if not real_id:
        return {'ok': False, 'text': f'{name}: agent not found in Letta', 'name': name}

    # Functional failure recorded by a recent /api/test call?
    with deps.agent_send_errors_lock:
        send_err = deps.agent_send_errors.get(real_id)
    if send_err:
        return {'ok': False,
                'text': f'{name}: last send failed — {send_err["text"][:80]}',
                'name': name}

    # Claude-SDK work endpoint reachable? The dashboard's Frita-Executor LED only
    # watches /claude_sdk_status; this catches a 404 on /claude_sdk itself — the
    # route the tool actually POSTs to (Frita's "HTTP Error 404: Not Found").
    if uses_claude_sdk(cfg):
        st = sdk_status if sdk_status is not None else deps.probe_claude_sdk_endpoint(
            deps.frita_exec_work_url, timeout)
        if st == 'not_found':
            return {'ok': False,
                    'text': f'{name}: Claude SDK endpoint /claude_sdk returns 404 — '
                            f'run_claude_code_sdk tool calls will fail',
                    'name': name}
        if st == 'unreachable':
            return {'ok': False,
                    'text': f'{name}: Claude SDK executor unreachable on :8799 — '
                            f'run_claude_code_sdk tool calls will fail',
                    'name': name}

    required = cfg.get('required_tools', [])
    if not required:
        return {'ok': True, 'text': f'{name}: agent found', 'name': name}

    # Letta paginates this endpoint at 10 by default; agents with more tools
    # would falsely report required tools as missing without an explicit limit.
    tools_data = deps.letta_get(f'/v1/agents/{real_id}/tools?limit=100', timeout=timeout)
    if tools_data is None:
        return {'ok': False, 'text': f'{name}: could not fetch tool list from Letta', 'name': name}

    tool_names = {t.get('name') for t in (tools_data if isinstance(tools_data, list) else [])}
    missing = [t for t in required if t not in tool_names]
    if missing:
        return {'ok': False,
                'text': f'{name}: missing required tools: {", ".join(missing)}',
                'name': name}
    return {'ok': True,
            'text': f'{name}: {", ".join(required)} present',
            'name': name}


def agent_health_status(deps: Collaborators):
    """Return {agent_id: {ok, text, name}} for every agent that declares required_tools.

    Fetches tool lists via the Letta API (one request per agent with required_tools);
    results cached for `deps.cache_ttl` seconds."""
    with deps.cache_lock:
        now_ts = time.time()
        cached = deps.cache.get('value')
        if cached is not None and now_ts - deps.cache.get('ts', 0.0) < deps.cache_ttl:
            return cached

        checked = [cfg for cfg in deps.letta_agents
                   if cfg.get('required_tools') or uses_claude_sdk(cfg)]
        # Probe the shared /claude_sdk work endpoint ONCE for the whole sweep — a
        # 404/outage there is infrastructure-wide, so every SDK agent reflects the
        # same result (mirrors the chatgpt-provider canary turning the fleet red).
        sdk_status = (deps.probe_claude_sdk_endpoint(deps.frita_exec_work_url, 6)
                      if any(uses_claude_sdk(c) for c in checked) else None)
        results = {}
        with ThreadPoolExecutor(max_workers=max(1, len(checked))) as pool:
            for result in pool.map(
                    lambda c: agent_health_check(deps, c, timeout=15, sdk_status=sdk_status),
                    checked):
                name = result['name']
                # Find the agent's real ID to use as the map key
                cfg = next((c for c in checked if c['name'] == name), None)
                if cfg:
                    real_id = deps.get_letta_id(cfg) or f'unknown-{name.lower()}'
                    results[real_id] = result

        deps.cache['value'] = results
        deps.cache['ts'] = time.time()
        return results
