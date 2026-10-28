"""The WSLInterop Entry check: parsing is pure, and a failed SSH is yellow, not red."""
import subprocess

from monitoring import wsl_interop_entry as wi

WSL_KERNEL = '6.6.87.2-microsoft-standard-WSL2'


def _out(entry, service='inactive', kernel=WSL_KERNEL):
    return (f'===KERNEL===\n{kernel}\n===ENTRY===\n{entry}\n'
            f'===BINFMT===\n{service}\n')


def test_enabled_entry_is_enabled():
    parsed = wi.parse_collector_output(_out(
        'enabled\ninterpreter /init\nflags: PF'))
    assert parsed['state'] == 'enabled'
    assert parsed['binfmt_service'] == 'inactive'


def test_missing_entry_is_missing():
    assert wi.parse_collector_output(_out('__MISSING__'))['state'] == 'missing'


def test_disabled_entry_is_disabled():
    assert wi.parse_collector_output(_out('disabled\ninterpreter /init'))['state'] == 'disabled'


def test_non_wsl_box_has_nothing_to_register():
    parsed = wi.parse_collector_output(_out('__MISSING__', kernel='6.1.0-amd64'))
    assert parsed['state'] == 'not-wsl'


def _fake_run(stdout='', stderr='', exc=None):
    def run(*a, **k):
        if exc:
            raise exc
        return subprocess.CompletedProcess(a[0], 0, stdout, stderr)
    return run


def test_missing_entry_turns_the_payload_red(monkeypatch):
    wi._cache.clear()
    monkeypatch.setattr(wi.subprocess, 'run', _fake_run(_out('__MISSING__')))
    payload = wi.wsl_interop_payload()
    assert payload['level'] == 'crit'
    assert all(m['level'] == 'crit' for m in payload['machines'])
    assert 'binfmt_misc/register' in payload['register_command']


def test_unreachable_machine_is_yellow_not_red(monkeypatch):
    wi._cache.clear()
    monkeypatch.setattr(wi.subprocess, 'run', _fake_run(
        exc=subprocess.TimeoutExpired('ssh', 20)))
    payload = wi.wsl_interop_payload()
    assert payload['level'] == 'warn'
    assert {m['state'] for m in payload['machines']} == {'unreachable'}
