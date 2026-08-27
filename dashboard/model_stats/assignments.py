"""Rows that consume tokens without being Letta agents."""

from __future__ import annotations

from typing import Any


CLAUDE_SDK_TOOL_ASSIGNMENT_ID = 'tool-run-claude-code-sdk'


def _expiry_detail(expires_at: Any, now: float) -> tuple[str, str, float | None]:
    """Return ``(status, detail, epoch)`` for an executor expiry reading."""
    try:
        expiry = float(expires_at)
    except (TypeError, ValueError):
        expiry = None

    if expiry is not None and expiry <= now:
        return 'down', 'OAuth token expired — run_claude_code_sdk will fail', expiry

    if expiry is None:
        return 'up', 'OAuth token valid (expiry not reported)', None

    return 'up', '', expiry


def build_claude_sdk_assignment(
    status: dict[str, Any] | None,
    now: float,
    account: str = '',
    account_label: str = 'Executor OAuth token',
) -> dict[str, Any]:
    """Build the read-only Agent Assignments row for the shared SDK tool.

    ``status`` is the executor's no-job ``/claude_sdk_status`` response. A
    missing executor response is deliberately red: the tool cannot be trusted
    when the endpoint that proves its credential is unavailable.
    """
    if not isinstance(status, dict):
        token_status = 'down'
        detail = 'SDK executor unreachable — run_claude_code_sdk will fail'
        expiry = None
    elif not status.get('creds_present'):
        token_status = 'down'
        detail = 'OAuth credentials missing — run_claude_code_sdk will fail'
        expiry = None
    elif status.get('creds_valid') is False:
        token_status = 'down'
        detail = 'OAuth token expired or rejected — run_claude_code_sdk will fail'
        expiry = status.get('creds_expires_at')
    elif not status.get('ready', status.get('ok', False)):
        token_status = 'down'
        detail = 'SDK executor not ready — run_claude_code_sdk will fail'
        expiry = status.get('creds_expires_at')
    else:
        token_status, detail, expiry = _expiry_detail(
            status.get('creds_expires_at'), now)

    return {
        'id': CLAUDE_SDK_TOOL_ASSIGNMENT_ID,
        'name': 'run_claude_code_sdk',
        'model': 'Claude Code SDK',
        'account': account,
        'account_label': account_label,
        'weekly_percent_remaining': None,
        'assignment_kind': 'tool',
        'token_status': token_status,
        'token_status_detail': detail,
        'token_expires_at': expiry,
    }


def build_unassigned_account_rows(
    oauth_provider_accounts: dict[str, dict[str, str]],
    referenced_providers: set[str],
    weekly_percent_remaining_fn,
) -> list[dict[str, Any]]:
    """Read-only Agent Assignments rows for OAuth accounts that exist in
    ``OAUTH_PROVIDER_ACCOUNTS`` but back no current Letta agent's provider --
    e.g. a human's second token for a family, held in reserve for failover.
    Without this a token can silently expire unnoticed because nothing on the
    tab ever polls it (see rbarnesrol@aol.com / chatgpt-plus-pro-mom, added
    2026-08-21 but only surfaced when an agent is actually pointed at it)."""
    rows = []
    for provider, meta in oauth_provider_accounts.items():
        if provider in referenced_providers:
            continue
        rows.append({
            'id': f'oauth-account-{provider}',
            'name': meta['label'],
            'model': 'Not assigned',
            'account': meta['account'],
            'account_label': meta['label'],
            'weekly_percent_remaining': weekly_percent_remaining_fn(provider),
            'assignment_kind': 'account',
        })
    return rows
