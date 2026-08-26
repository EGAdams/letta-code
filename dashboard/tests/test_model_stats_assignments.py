"""Regression coverage for token-bearing non-agent assignments."""

import json

import server

from model_stats.assignments import build_claude_sdk_assignment


def test_sdk_tool_assignment_is_green_when_executor_reports_live_token():
    row = build_claude_sdk_assignment(
        {
            'ready': True,
            'creds_present': True,
            'creds_valid': True,
            'creds_expires_at': 1_800_000_000,
        },
        now=1_700_000_000,
    )

    assert row['assignment_kind'] == 'tool'
    assert row['name'] == 'run_claude_code_sdk'
    assert row['token_status'] == 'up'
    assert row['token_status_detail'] == ''


def test_sdk_tool_assignment_is_red_when_token_expired():
    row = build_claude_sdk_assignment(
        {
            'ready': True,
            'creds_present': True,
            'creds_valid': False,
            'creds_expires_at': 1_699_999_999,
        },
        now=1_700_000_000,
    )

    assert row['token_status'] == 'down'
    assert 'expired or rejected' in row['token_status_detail']


def test_sdk_tool_assignment_is_red_when_executor_status_is_unavailable():
    row = build_claude_sdk_assignment(None, now=1_700_000_000)

    assert row['token_status'] == 'down'
    assert 'unreachable' in row['token_status_detail']


def test_agent_assignments_payload_includes_the_sdk_tool_row(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps([]).encode()

    monkeypatch.setattr(server, 'LETTA_AGENTS', [])
    monkeypatch.setattr(server.urllib.request, 'urlopen', lambda *_args, **_kwargs: Response())
    monkeypatch.setattr(server, 'claude_sdk_token_status', lambda: {
        'ready': True,
        'creds_present': True,
        'creds_valid': True,
        'creds_expires_at': 1_800_000_000,
    })
    monkeypatch.setitem(server._model_stats_agents_cache, 'value', None)

    rows = server.model_stats_agents_payload(force_refresh=True)

    sdk_row = next(row for row in rows if row['assignment_kind'] == 'tool')
    assert sdk_row['id'] == 'tool-run-claude-code-sdk'
    assert sdk_row['token_status'] == 'up'
