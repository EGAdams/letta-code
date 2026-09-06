from pathlib import Path

from servers.browser_server import (
    BrowserServerStartResult,
    IBrowserServerLifecycle,
    SshBrowserServerLifecycle,
)


class _Response:
    status = 200

    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class _Completed:
    def __init__(self, returncode=0, stdout='', stderr=''):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class FakeBrowserServerLifecycle(IBrowserServerLifecycle):
    def restart(self) -> BrowserServerStartResult:
        return BrowserServerStartResult(ok=True, text='fake restarted')


def test_lifecycle_port_has_a_minimal_fake():
    assert FakeBrowserServerLifecycle().restart().ok is True


def test_healthy_browser_server_is_not_restarted():
    commands = []
    response = _Response()
    service = SshBrowserServerLifecycle(
        remote_host='adamsl@example',
        health_url='http://example:5001/health',
        health_opener=lambda *_args, **_kwargs: response,
        command_runner=lambda *args, **kwargs: commands.append((args, kwargs)),
    )

    result = service.restart()

    assert result.ok is True
    assert 'already running' in result.text
    assert response.closed is True
    assert commands == []


def test_down_browser_server_restarts_enabled_remote_unit_and_verifies_health():
    health_attempts = []
    commands = []
    marked = []
    logged = []

    def health(*_args, **_kwargs):
        health_attempts.append(True)
        if len(health_attempts) == 1:
            raise OSError('connection refused')
        return _Response()

    def run(*args, **kwargs):
        commands.append((args, kwargs))
        return _Completed()

    service = SshBrowserServerLifecycle(
        remote_host='adamsl@example',
        health_url='http://example:5001/health',
        health_opener=health,
        command_runner=run,
        sleeper=lambda _seconds: None,
        mark_starting=marked.append,
        log_restart=logged.append,
    )

    result = service.restart()

    assert result.ok is True
    assert commands[0][0][0] == [
        'ssh', '-o', 'ConnectTimeout=10', '-o', 'BatchMode=yes',
        'adamsl@example', 'systemctl', '--user', 'restart',
        'browser-server.service',
    ]
    assert commands[0][1]['timeout'] == 20
    assert len(health_attempts) == 2
    assert marked == ['browser-server']
    assert logged == [
        'browser-server: restarting browser-server.service on adamsl@example']


def test_remote_systemd_failure_is_returned_without_false_success():
    service = SshBrowserServerLifecycle(
        remote_host='adamsl@example',
        health_url='http://example:5001/health',
        health_opener=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            OSError('connection refused')),
        command_runner=lambda *_args, **_kwargs: _Completed(
            returncode=5, stderr='Unit browser-server.service not found.'),
        sleeper=lambda _seconds: None,
    )

    result = service.restart()

    assert result.ok is False
    assert 'Unit browser-server.service not found' in result.text


def test_remote_command_exception_is_returned_without_escaping():
    def unavailable(*_args, **_kwargs):
        raise OSError('connection refused')

    def fail_command(*_args, **_kwargs):
        raise OSError('ssh unavailable')

    service = SshBrowserServerLifecycle(
        remote_host='adamsl@example',
        health_url='http://example:5001/health',
        health_opener=unavailable,
        command_runner=fail_command,
        sleeper=lambda _seconds: None,
    )

    result = service.restart()

    assert result.ok is False
    assert 'ssh unavailable' in result.text


def test_restart_fails_if_health_never_recovers():
    response = _Response()
    response.status = 503
    service = SshBrowserServerLifecycle(
        remote_host='adamsl@example',
        health_url='http://example:5001/health',
        health_opener=lambda *_args, **_kwargs: response,
        command_runner=lambda *_args, **_kwargs: _Completed(),
        sleeper=lambda _seconds: None,
        verify_attempts=2,
    )

    result = service.restart()

    assert result.ok is False
    assert 'did not become healthy' in result.text


def test_unit_must_be_enabled_and_restart_on_failure():
    unit = Path(__file__).parents[2] / 'browser_tools/systemd/browser-server.service'
    text = unit.read_text(encoding='utf-8')

    assert 'Restart=on-failure' in text
    assert 'WantedBy=default.target' in text
    assert 'BROWSER_SERVER_HOST=0.0.0.0' in text
