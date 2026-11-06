from monitoring import worker_restart


def test_restart_requires_auth_and_never_runs_without_it(monkeypatch):
    monkeypatch.setenv('WORKER_RESTART_TOKEN', 'secret')
    called = []
    monkeypatch.setattr(worker_restart.subprocess, 'run', lambda *a, **k: called.append(a))
    result = worker_restart.restart('Bearer wrong')
    assert result == {'ok': False, 'configured': True, 'text': 'Worker restart is not authorized.'}
    assert called == []


def test_authorized_restart_uses_only_fixed_systemd_unit(monkeypatch):
    monkeypatch.setenv('WORKER_RESTART_TOKEN', 'secret')
    seen = {}
    class Completed:
        returncode = 0
        stdout = stderr = ''
    monkeypatch.setattr(worker_restart.subprocess, 'run', lambda args, **kwargs: seen.update(args=args, kwargs=kwargs) or Completed())
    assert worker_restart.restart('Bearer secret')['ok'] is True
    assert seen['args'] == ['systemctl', '--user', 'restart', worker_restart.SERVICE]


def test_unconfigured_restart_is_a_safe_no_op(monkeypatch):
    monkeypatch.delenv('WORKER_RESTART_TOKEN', raising=False)
    assert worker_restart.restart('Bearer anything')['configured'] is False
