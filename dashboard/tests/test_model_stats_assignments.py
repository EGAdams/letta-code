"""Regression coverage for token-bearing non-agent assignments."""

import json

import server

from model_stats.assignments import (
    assignments_status, build_claude_sdk_assignment, build_unassigned_account_rows,
)


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


def test_sdk_tool_assignment_carries_the_weekly_bar_of_its_account():
    """The executor spends a human's own Claude quota, so its row shows the
    same Weekly Remaining bar every other row has -- it was the one row on the
    tab rendering a bare dash."""
    row = build_claude_sdk_assignment(
        {
            'ready': True,
            'creds_present': True,
            'creds_valid': True,
            'creds_expires_at': 1_800_000_000,
        },
        now=1_700_000_000,
        account='mom',
        weekly_percent_remaining=41.5,
    )

    assert row['weekly_percent_remaining'] == 41.5


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


def test_agent_assignments_payload_reads_the_sdk_row_quota_from_its_account(monkeypatch):
    """The SDK dropdown names an account ('eg'/'mom'); weekly quota is only
    readable per provider row. Assert the join, since a wrong one would show
    the other human's remaining percentage on this row."""
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps([]).encode()

    probed = []

    monkeypatch.setattr(server, 'LETTA_AGENTS', [])
    monkeypatch.setattr(server.urllib.request, 'urlopen', lambda *_args, **_kwargs: Response())
    monkeypatch.setattr(server, 'claude_sdk_token_status', lambda: {
        'ready': True, 'creds_present': True, 'creds_valid': True,
        'creds_expires_at': 1_800_000_000,
    })
    monkeypatch.setattr(server, 'claude_sdk_account_payload', lambda: {
        'ok': True, 'current': 'eg',
        'options': [{'account': 'eg', 'label': 'eg1972@gmail.com'}],
    })

    def fake_weekly(provider):
        probed.append(provider)
        return 73.0 if provider == 'claude-pro-max-eg' else 12.0

    monkeypatch.setattr(server, '_weekly_percent_remaining', fake_weekly)
    monkeypatch.setitem(server._model_stats_agents_cache, 'value', None)

    rows = server.model_stats_agents_payload(force_refresh=True)

    sdk_row = next(row for row in rows if row['assignment_kind'] == 'tool')
    assert sdk_row['weekly_percent_remaining'] == 73.0
    assert 'claude-pro-max-eg' in probed


def test_assignments_status_is_down_when_the_sdk_tool_row_is_down():
    sdk_row = build_claude_sdk_assignment(
        {'ready': True, 'creds_present': True, 'creds_valid': False,
         'creds_expires_at': 1_699_999_999},
        now=1_700_000_000,
    )

    status = assignments_status([{'name': 'Mazda', 'token_status': None}, sdk_row])

    assert status['status'] == 'down'
    assert 'run_claude_code_sdk' in status['detail']
    assert 'expired or rejected' in status['detail']


def test_assignments_status_is_up_when_no_row_reports_down():
    rows = [{'name': 'Mazda'}, {'name': 'Frita', 'token_status': 'up'}]

    status = assignments_status(rows)

    assert status['status'] == 'up'
    assert status['detail'] == ''


def test_unassigned_account_rows_surface_accounts_no_agent_uses():
    accounts = {
        'claude-pro-max-eg': {'account': 'eg', 'label': 'eg1972@gmail.com', 'family': 'claude'},
        'chatgpt-plus-pro-mom': {'account': 'mom', 'label': 'rbarnesrol@aol.com', 'family': 'chatgpt'},
    }

    rows = build_unassigned_account_rows(
        accounts, referenced_providers={'claude-pro-max-eg'},
        weekly_percent_remaining_fn=lambda provider: 87.5)

    assert len(rows) == 1
    assert rows[0]['id'] == 'oauth-account-chatgpt-plus-pro-mom'
    assert rows[0]['account_label'] == 'rbarnesrol@aol.com'
    assert rows[0]['assignment_kind'] == 'account'
    assert rows[0]['weekly_percent_remaining'] == 87.5
    # A chatgpt-family account must never be labeled "Anthropic" -- the
    # unassigned-row text names the account's own family.
    assert rows[0]['model'] == 'No ChatGPT Assigned'


def test_agent_assignments_payload_surfaces_the_aol_token_when_unused(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps([]).encode()

    monkeypatch.setattr(server, 'LETTA_AGENTS', [])
    monkeypatch.setattr(server.urllib.request, 'urlopen', lambda *_args, **_kwargs: Response())
    monkeypatch.setattr(server, 'claude_sdk_token_status', lambda: None)
    monkeypatch.setattr(server, '_weekly_percent_remaining', lambda _provider: None)
    monkeypatch.setitem(server._model_stats_agents_cache, 'value', None)

    rows = server.model_stats_agents_payload(force_refresh=True)

    aol_row = next(row for row in rows if row['id'] == 'oauth-account-chatgpt-plus-pro-mom')
    assert aol_row['account_label'] == 'rbarnesrol@aol.com'
    assert aol_row['assignment_kind'] == 'account'
