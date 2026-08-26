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
