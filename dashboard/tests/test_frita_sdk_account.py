"""Keep the dashboard account choice compatible with the sync service."""

from types import SimpleNamespace

from health import frita


def test_account_payload_maps_persisted_sync_source_to_dashboard_key(
        monkeypatch, tmp_path):
    account_file = tmp_path / 'frita-sdk-account'
    account_file.write_text('rbarnesrol\n', encoding='utf-8')
    monkeypatch.setattr(frita, 'CLAUDE_SDK_ACCOUNT_FILE', str(account_file))

    assert frita.claude_sdk_account_payload()['current'] == 'mom'


def test_set_account_persists_the_source_name_consumed_by_timer(
        monkeypatch, tmp_path):
    account_file = tmp_path / 'config' / 'frita-sdk-account'
    calls = []
    monkeypatch.setattr(frita, 'CLAUDE_SDK_ACCOUNT_FILE', str(account_file))
    monkeypatch.setattr(
        frita.subprocess,
        'run',
        lambda args, **kwargs: calls.append((args, kwargs)) or SimpleNamespace(
            returncode=0),
    )

    result = frita.set_claude_sdk_account('eg')

    assert result['ok'] is True
    assert account_file.read_text(encoding='utf-8') == 'eg1972\n'
    assert calls[0][0] == [frita.FRITA_CREDS_SYNC_SCRIPT, 'eg1972']
