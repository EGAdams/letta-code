"""The Model Stats "Agent Assignments" tab: one row per Letta agent, plus the
read-only rows for token-bearing things that are not agents.

``weekly_percent_remaining`` is the OAuth usage prober only ``agents_payload``
calls -- it exists and travels with this module the same way
``intake.intake_folding``'s ``resolve_duplicate_expense_ids`` travels with
``fold_event_into_intake``. Its own cache (``server._weekly_remaining_cache``)
and ``agents_payload``'s cache (``server._model_stats_agents_cache``) both stay
behind in server.py -- tests rebind/mutate them by their `server.` name -- so
``agents_payload`` calls ``deps.weekly_percent_remaining`` (the server.py name)
rather than this module's own function, keeping
``monkeypatch.setattr(server, '_weekly_percent_remaining', ...)`` honoured.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable

from model_stats.assignments import build_claude_sdk_assignment, build_unassigned_account_rows
from model_stats.windows import _human_reset


@dataclass(frozen=True)
class WeeklyRemainingCollaborators:
    """What stays behind in server.py, handed over per call."""

    fetch_provider_oauth_creds: Callable
    cache: dict
    cache_lock: object
    cache_ttl: float


def weekly_percent_remaining(deps: WeeklyRemainingCollaborators, provider_name):
    """(remaining, rate_limited_until) -- 100 - the 7-day/weekly window's
    used_percent for a provider's live token, via the same zero-token usage
    probes as the health system (never an LLM call).

    `remaining` is None on any failure -- caller renders that as unknown, not
    0%. `rate_limited_until` is an absolute epoch, set only when the failure
    was specifically an HTTP 429 with a `Retry-After` header: this usage-*
    reporting* endpoint throttles independently of the account's real quota
    (see model_stats/reader.py's _fill_rate_limited for the same judgement
    call on the same endpoint), so the caller can render a live countdown to
    the real cause instead of a bare "unavailable"."""
    now = time.time()
    with deps.cache_lock:
        cached = deps.cache.get(provider_name)
        if cached:
            cached_remaining, cached_reset_at, cached_at = cached
            # Same backoff as model_stats/reader.py's model_stats(): once a
            # 429 tells us exactly when the reporting endpoint's cooldown
            # ends, keep serving that reading instead of re-probing every
            # cache_ttl seconds and extending the throttle.
            still_backing_off = cached_reset_at and now < cached_reset_at
            if still_backing_off or now - cached_at < deps.cache_ttl:
                return cached_remaining, cached_reset_at

    creds, provider_type = deps.fetch_provider_oauth_creds(provider_name)
    remaining = None
    rate_limited_until = None
    if creds:
        try:
            if provider_type in ('anthropic', 'anthropic_oauth'):
                token = creds.get('access_token') or (creds.get('claudeAiOauth') or {}).get('accessToken') or ''
                req = urllib.request.Request(
                    'https://api.anthropic.com/api/oauth/usage',
                    headers={'Authorization': 'Bearer ' + token,
                             'anthropic-beta': 'oauth-2025-04-20', 'User-Agent': 'claude-code/2.0.32'})
                with urllib.request.urlopen(req, timeout=15) as r:
                    usage = json.loads(r.read().decode())
                used = float((usage.get('seven_day') or {}).get('utilization') or 0)
                remaining = round(100 - used, 1)
            elif provider_type == 'chatgpt_oauth':
                req = urllib.request.Request(
                    'https://chatgpt.com/backend-api/wham/usage',
                    headers={'Authorization': 'Bearer ' + (creds.get('access_token') or ''),
                             'ChatGPT-Account-Id': creds.get('account_id', ''),
                             'OpenAI-Beta': 'codex-1', 'originator': 'codex_cli_rs', 'User-Agent': 'codex'})
                with urllib.request.urlopen(req, timeout=15) as r:
                    usage = json.loads(r.read().decode())
                rl = usage.get('rate_limit') or {}
                # The weekly window isn't reliably "secondary_window" -- its
                # position shifts (see monitoring/provider_usage.py's
                # codex_window_label and its 2026-08-19 note:
                # primary_window was the 7-day window with no secondary at
                # all). Pick whichever window's own limit_window_seconds is
                # actually ~7 days, not a fixed key.
                w = None
                for key in ('primary_window', 'secondary_window'):
                    candidate = rl.get(key)
                    if isinstance(candidate, dict) and abs((candidate.get('limit_window_seconds') or 0) - 604800) < 3600:
                        w = candidate
                        break
                used = float((w or {}).get('used_percent') or 0)
                remaining = round(100 - used, 1)
        except urllib.error.HTTPError as e:
            remaining = None
            if e.code == 429:
                retry_after = e.headers.get('Retry-After') if e.headers else None
                try:
                    if retry_after is not None:
                        rate_limited_until = now + int(retry_after)
                except ValueError:
                    pass
        except Exception:
            remaining = None

    with deps.cache_lock:
        deps.cache[provider_name] = (remaining, rate_limited_until, now)
    return remaining, rate_limited_until


@dataclass(frozen=True)
class Collaborators:
    """What stays behind in server.py, handed over per call."""

    letta_base_url: str
    letta_agents: list
    get_letta_id: Callable
    get_chatgpt_provider_account_status: Callable
    oauth_provider_accounts: dict
    chatgpt_plus_pro: str
    weekly_percent_remaining: Callable
    claude_sdk_account_payload: Callable
    claude_sdk_token_status: Callable
    claude_provider_for_account: Callable
    cache: dict
    cache_lock: object
    cache_ttl: float


def agents_payload(deps: Collaborators, force_refresh=False):
    """One row per LETTA_AGENTS entry for the Agent Assignments tab: current
    model, current OAuth account label, and that account's weekly-remaining %."""
    now = time.time()
    if not force_refresh:
        with deps.cache_lock:
            cached = deps.cache.get('value')
            if cached is not None and now - deps.cache.get('ts', 0.0) < deps.cache_ttl:
                return cached

    req = urllib.request.Request(f'{deps.letta_base_url}/v1/agents/?limit=200')
    with urllib.request.urlopen(req, timeout=20) as r:
        all_agents = json.loads(r.read().decode())
    by_id = {a['id']: a for a in all_agents}

    chatgpt_status = deps.get_chatgpt_provider_account_status()
    rows = []
    referenced_providers = set()
    for cfg in deps.letta_agents:
        real_id = deps.get_letta_id(cfg)
        agent_data = by_id.get(real_id) if real_id else None
        llm = (agent_data or {}).get('llm_config') or {}
        provider = llm.get('provider_name') or ''
        model_id = llm.get('model') or ''
        info = deps.oauth_provider_accounts.get(provider)
        if provider:
            referenced_providers.add(provider)
        provider_state = (chatgpt_status.provider_token_state
                          if provider == deps.chatgpt_plus_pro else None)
        remaining, rate_limited_until = (
            deps.weekly_percent_remaining(provider) if provider else (None, None))
        rows.append({
            'id': real_id or f'unknown-{cfg["name"].lower()}',
            'name': cfg['name'],
            'model': model_id,
            'account': info['account'] if info else '',
            'account_label': info['label'] if info else (provider or 'unknown'),
            'weekly_percent_remaining': remaining,
            'token_reset_at': rate_limited_until,
            'token_status': ('up' if provider_state == 'valid' else
                             'down' if provider_state in ('expired', 'stale') else None),
            'token_status_detail': (chatgpt_status.token_status_detail
                                    if provider_state else
                                    (f'Usage reporting rate limited — resets {_human_reset(rate_limited_until)}'
                                     if rate_limited_until else '')),
        })

    # Accounts (e.g. rbarnesrol@aol.com / chatgpt-plus-pro-mom) that exist in
    # OAUTH_PROVIDER_ACCOUNTS but back no current agent's provider would
    # otherwise never appear on this tab -- surface them read-only so an
    # unused token's expiry is still visible.
    rows.extend(build_unassigned_account_rows(
        deps.oauth_provider_accounts, referenced_providers, deps.weekly_percent_remaining))

    # Mazda's run_claude_code_sdk tool is not a Letta agent, but it runs the
    # work that makes her minions useful and authenticates with its own mounted
    # Claude OAuth credential. Keep it in this list so an expired executor
    # token cannot hide behind healthy Letta-agent rows. This probe is
    # read-only and does not submit a Claude job or trigger auto-repair.
    sdk_account = deps.claude_sdk_account_payload()
    sdk_option = next(
        (item for item in sdk_account.get('options', [])
         if item.get('account') == sdk_account.get('current')),
        {},
    )
    # The executor runs on a copy of one human's ordinary Claude OAuth token,
    # so it spends that account's weekly quota -- read it from the matching
    # provider row (cached alongside every other row's) rather than leaving
    # this the one row on the tab with no Weekly Remaining bar.
    sdk_provider = deps.claude_provider_for_account(sdk_account.get('current', ''))
    sdk_remaining, sdk_reset_at = (
        deps.weekly_percent_remaining(sdk_provider) if sdk_provider else (None, None))
    rows.append(build_claude_sdk_assignment(
        deps.claude_sdk_token_status(), now=time.time(),
        account=sdk_account.get('current', ''),
        account_label=sdk_option.get('label', 'Executor OAuth token'),
        weekly_percent_remaining=sdk_remaining,
        token_reset_at=sdk_reset_at))

    with deps.cache_lock:
        deps.cache['value'] = rows
        deps.cache['ts'] = now
    return rows
