"""The Poll Settings save route's module: shape checks and how it reads the ADW's answer."""
import subprocess

from monitoring import agent_bridge_poll_edit as edit

GOOD = {'idle_seconds': 45, 'burst_seconds': 5, 'burst_window_seconds': 300,
        'slow_down_seconds': 3600, 'error_base_seconds': 30, 'error_max_seconds': 900,
        'active_hours': {'start_hour': 7, 'end_hour': 24}}


class FakeRun:
    def __init__(self, stdout='', stderr='', returncode=0, raises=None):
        self.stdout, self.stderr, self.returncode, self.raises = stdout, stderr, returncode, raises
        self.calls = []

    def __call__(self, argv, **kw):
        self.calls.append((argv, kw))
        if self.raises:
            raise self.raises
        return subprocess.CompletedProcess(argv, self.returncode, self.stdout, self.stderr)


def test_wrong_shape_never_reaches_the_adw(monkeypatch):
    run = FakeRun()
    monkeypatch.setattr(edit.subprocess, 'run', run)
    result = edit.save_poll_settings({**GOOD, 'idle_seconds': 'soon', 'token': 'x'})
    assert result['ok'] is False
    assert {p['field'] for p in result['problems']} == {'idle_seconds', 'token'}
    assert run.calls == []


def test_runs_the_worker_adw_with_the_settings_on_stdin(monkeypatch):
    run = FakeRun(stdout='phase noise\n{"ok": true, "message": "Saved."}\n')
    monkeypatch.setattr(edit.subprocess, 'run', run)
    assert edit.save_poll_settings(GOOD) == {'ok': True, 'message': 'Saved.'}
    argv, kw = run.calls[0]
    assert argv == [str(edit.PYTHON), str(edit.ADW)]
    assert '"idle_seconds":45.0' in kw['input']
    assert kw['cwd'] == str(edit.AGENT_BLOCKS)


def test_passes_the_adw_refusal_through(monkeypatch):
    monkeypatch.setattr(edit.subprocess, 'run', FakeRun(
        stdout='{"ok": false, "message": "busy", "problems": []}', returncode=1))
    assert edit.save_poll_settings(GOOD)['message'] == 'busy'


def test_says_so_when_the_adw_says_nothing(monkeypatch):
    monkeypatch.setattr(edit.subprocess, 'run', FakeRun(stderr='Traceback\nBoom', returncode=2))
    result = edit.save_poll_settings(GOOD)
    assert result['ok'] is False and 'Boom' in result['message']


def test_a_timeout_is_an_answer_not_a_500(monkeypatch):
    monkeypatch.setattr(edit.subprocess, 'run', FakeRun(raises=subprocess.TimeoutExpired('x', 1)))
    assert edit.save_poll_settings(GOOD)['ok'] is False


def test_around_the_clock_is_allowed():
    assert edit.PollSettingsEdit.model_validate({**GOOD, 'active_hours': None}).active_hours is None
