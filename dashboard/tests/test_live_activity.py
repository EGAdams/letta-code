import json
import subprocess

from monitoring import live_activity


def _runner(calls, stdout):
    def run(argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout, '')
    return run


def test_runs_the_adw_with_the_cursor_and_machine_and_caches(monkeypatch):
    monkeypatch.setattr(live_activity, '_cache', {})
    calls = []
    run = _runner(calls, json.dumps({'ok': True, 'cursor': 9}))
    for _ in range(2):
        assert live_activity.read(5, 'BATI', run=run, clock=lambda: 100.0)['cursor'] == 9
    assert len(calls) == 1 and calls[0][-4:] == ['--machine', 'BATI', '--after', '5']


def test_a_bad_name_never_reaches_a_command_line(monkeypatch):
    monkeypatch.setattr(live_activity, '_cache', {})
    calls = []
    answer = live_activity.read(None, '--after;rm', run=_runner(calls, '{}'))
    assert answer['ok'] is False and calls == []


def test_a_broken_adw_is_a_gap_not_an_empty_success(monkeypatch):
    monkeypatch.setattr(live_activity, '_cache', {})
    answer = live_activity.read(3, '', run=_runner([], 'Traceback'))
    assert answer['ok'] is False and answer['cursor'] == 3 and answer['gaps']
