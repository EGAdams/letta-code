import json
import subprocess
import urllib.error
from pathlib import Path

import remediation_runner as rr


def test_unwired_runner_honestly_reports_nothing_executed():
    outcome = rr.UnwiredRemediationRunner().run('alert:1', 'claude-sonnet', 'prompt text')
    assert outcome.ok is False
    assert outcome.task_id is None
    assert outcome.status == 'unsupported'
    assert outcome.error == 'dispatch_unsupported'
    assert 'REMEDIATION_ADW_SCRIPT' in outcome.detail


def test_default_runner_is_unwired_when_no_script_is_configured(monkeypatch, tmp_path):
    monkeypatch.delenv('REMEDIATION_ADW_SCRIPT', raising=False)
    # Pinned away from the real ~/.config/agent_bridge/client_token so this test
    # doesn't flip to Bridge on a host that actually has one configured.
    monkeypatch.setattr(rr, 'BRIDGE_TOKEN_PATH', tmp_path / 'no_bridge_token_here')
    assert isinstance(rr.default_runner(), rr.UnwiredRemediationRunner)


def test_default_runner_is_unwired_when_the_configured_script_does_not_exist(monkeypatch, tmp_path):
    monkeypatch.setenv('REMEDIATION_ADW_SCRIPT', str(tmp_path / 'missing.py'))
    monkeypatch.setattr(rr, 'BRIDGE_TOKEN_PATH', tmp_path / 'no_bridge_token_here')
    assert isinstance(rr.default_runner(), rr.UnwiredRemediationRunner)


def test_default_runner_is_scoped_when_the_configured_script_exists(monkeypatch, tmp_path):
    script = tmp_path / 'run.py'
    script.write_text('# stub')
    monkeypatch.setenv('REMEDIATION_ADW_SCRIPT', str(script))
    runner = rr.default_runner()
    assert isinstance(runner, rr.ScopedAdwRemediationRunner)
    assert runner.script == script


def test_scoped_runner_defaults_its_cwd_to_the_scripts_own_checkout_not_the_dashboards(tmp_path):
    """`uv run` resolves a project's venv/deps from its cwd. A real remediation
    script lives in its own checkout (e.g. agent_blocks/adws/), so the default
    must follow the script there -- never this dashboard's REPO_ROOT, which
    would hand `uv run` the wrong project and fail even once the script exists."""
    script = tmp_path / 'adws' / 'adw_remediation_dispatch.py'
    script.parent.mkdir()
    script.write_text('# stub')
    runner = rr.ScopedAdwRemediationRunner(script)
    assert runner.root == script.parent


def test_scoped_runner_honors_an_explicit_root_override(tmp_path):
    script = tmp_path / 'scripts' / 'run.py'
    script.parent.mkdir()
    script.write_text('# stub')
    other_root = tmp_path / 'checkout'
    other_root.mkdir()
    runner = rr.ScopedAdwRemediationRunner(script, root=other_root)
    assert runner.root == other_root


def test_scoped_runner_writes_a_request_file_and_parses_a_successful_result(monkeypatch, tmp_path):
    script = tmp_path / 'run.py'
    script.write_text('# stub')
    captured = {}

    def fake_run(command, cwd, capture_output, text, timeout, env):
        captured['command'] = command
        request_path = Path(command[command.index('--request-file') + 1])
        result_path = Path(command[command.index('--result-file') + 1])
        captured['request'] = json.loads(request_path.read_text())
        result_path.write_text(json.dumps({'ok': True, 'task_id': 'remediate-xyz', 'status': 'queued'}))
        return subprocess.CompletedProcess(command, 0, stdout='', stderr='')

    monkeypatch.setattr(rr.subprocess, 'run', fake_run)
    runner = rr.ScopedAdwRemediationRunner(script, root=tmp_path)
    outcome = runner.run('alert:1', 'claude-sonnet', 'the prompt')

    assert outcome.ok is True
    assert outcome.task_id == 'remediate-xyz'  # the script's own id wins over the one proposed
    assert outcome.status == 'queued'
    proposed = captured['request'].pop('task_id')
    assert proposed.startswith('remediate-')
    assert captured['request'] == {'alert_key': 'alert:1', 'model_id': 'claude-sonnet', 'prompt': 'the prompt'}
    # exactly one named script invoked, never a shell string built from alert text
    assert captured['command'][1] == 'run'
    assert captured['command'][2] == str(script)


def test_scoped_runner_reports_failed_when_the_script_never_writes_a_result(monkeypatch, tmp_path):
    script = tmp_path / 'run.py'
    script.write_text('# stub')

    def fake_run(command, cwd, capture_output, text, timeout, env):
        return subprocess.CompletedProcess(command, 1, stdout='boom', stderr='')

    monkeypatch.setattr(rr.subprocess, 'run', fake_run)
    runner = rr.ScopedAdwRemediationRunner(script, root=tmp_path)
    outcome = runner.run('alert:1', 'claude-sonnet', 'the prompt')

    assert outcome.ok is False
    assert outcome.error == 'no_result'
    assert 'boom' in outcome.detail


def test_scoped_runner_reports_failed_when_the_result_file_is_not_valid_json(monkeypatch, tmp_path):
    script = tmp_path / 'run.py'
    script.write_text('# stub')

    def fake_run(command, cwd, capture_output, text, timeout, env):
        result_path = Path(command[command.index('--result-file') + 1])
        result_path.write_text('not json')
        return subprocess.CompletedProcess(command, 0, stdout='', stderr='')

    monkeypatch.setattr(rr.subprocess, 'run', fake_run)
    runner = rr.ScopedAdwRemediationRunner(script, root=tmp_path)
    outcome = runner.run('alert:1', 'claude-sonnet', 'the prompt')

    assert outcome.ok is False
    assert outcome.error == 'invalid_result'


def test_scoped_runner_reports_failed_on_timeout_or_a_missing_binary(monkeypatch, tmp_path):
    script = tmp_path / 'run.py'
    script.write_text('# stub')

    def fake_run(command, cwd, capture_output, text, timeout, env):
        raise subprocess.TimeoutExpired(cmd=command, timeout=timeout)

    monkeypatch.setattr(rr.subprocess, 'run', fake_run)
    runner = rr.ScopedAdwRemediationRunner(script, root=tmp_path, timeout=1)
    outcome = runner.run('alert:1', 'claude-sonnet', 'the prompt')

    assert outcome.ok is False
    assert outcome.status == 'failed'
    assert outcome.error == 'runner_failed'


class _FakeBridgeResponse:
    """Stand-in for the context manager urllib.request.urlopen() returns."""

    def __init__(self, body: bytes):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def read(self):
        return self._body


def _token_file(tmp_path, token='bridge-secret-token-xyz'):
    token_path = tmp_path / 'client_token'
    token_path.write_text(token)
    return token_path, token


def test_default_runner_is_bridge_rest_when_a_client_token_exists_and_no_script_is_configured(
        monkeypatch, tmp_path):
    monkeypatch.delenv('REMEDIATION_ADW_SCRIPT', raising=False)
    token_path, _ = _token_file(tmp_path)
    monkeypatch.setattr(rr, 'BRIDGE_TOKEN_PATH', token_path)
    runner = rr.default_runner()
    assert isinstance(runner, rr.BridgeRestRemediationRunner)
    assert runner.token_path == token_path


def test_default_runner_prefers_a_configured_adw_script_over_bridge_even_with_a_token(monkeypatch, tmp_path):
    script = tmp_path / 'run.py'
    script.write_text('# stub')
    monkeypatch.setenv('REMEDIATION_ADW_SCRIPT', str(script))
    token_path, _ = _token_file(tmp_path)
    monkeypatch.setattr(rr, 'BRIDGE_TOKEN_PATH', token_path)
    assert isinstance(rr.default_runner(), rr.ScopedAdwRemediationRunner)


def test_bridge_runner_posts_the_documented_payload_and_parses_a_queued_task(monkeypatch, tmp_path):
    token_path, token = _token_file(tmp_path)
    captured = {}

    def fake_urlopen(request, timeout=None):
        captured['url'] = request.full_url
        captured['method'] = request.get_method()
        captured['headers'] = dict(request.header_items())
        captured['body'] = json.loads(request.data)
        captured['timeout'] = timeout
        return _FakeBridgeResponse(json.dumps({'task_id': 't_' + 'a1b2c3' * 4, 'state': 'queued'}).encode())

    monkeypatch.setattr(rr.urllib.request, 'urlopen', fake_urlopen)
    runner = rr.BridgeRestRemediationRunner(token_path=token_path)
    outcome = runner.run('alert:1', 'claude-sonnet', 'the prompt')

    assert outcome.ok is True
    assert outcome.task_id == 't_' + 'a1b2c3' * 4
    assert outcome.status == 'queued'
    assert captured['url'] == 'https://bridge.americansjewelry.com/api/agent-bridge/v1/tasks'
    assert captured['method'] == 'POST'
    assert captured['headers']['Authorization'] == f'Bearer {token}'
    assert captured['headers']['Content-type'] == 'application/json'
    # HostGator answers 406 to urllib's default Python-urllib User-Agent.
    assert captured['headers']['User-agent'] == rr.BRIDGE_USER_AGENT
    assert 'python' not in rr.BRIDGE_USER_AGENT.lower()
    assert captured['body'] == {
        'schema_version': '1.0', 'task_type': 'agent_task', 'agent': 'claude-sonnet',
        'workspace': 'letta_code', 'operation': 'implement', 'approval_mode': 'workspace_write',
        'prompt': 'the prompt', 'idempotency_key': 'alert:1',
    }


def test_bridge_runner_never_prints_the_token(monkeypatch, tmp_path, capsys):
    token_path, token = _token_file(tmp_path)

    def fake_urlopen(request, timeout=None):
        return _FakeBridgeResponse(json.dumps({'task_id': 't_' + 'f' * 24, 'state': 'queued'}).encode())

    monkeypatch.setattr(rr.urllib.request, 'urlopen', fake_urlopen)
    runner = rr.BridgeRestRemediationRunner(token_path=token_path)
    outcome = runner.run('alert:1', 'claude-sonnet', 'the prompt')

    captured = capsys.readouterr()
    assert token not in captured.out
    assert token not in captured.err
    assert token not in (outcome.detail or '')


def test_bridge_runner_uses_a_stable_idempotency_key_across_repeated_calls(monkeypatch, tmp_path):
    token_path, _ = _token_file(tmp_path)
    bodies = []

    def fake_urlopen(request, timeout=None):
        bodies.append(json.loads(request.data))
        return _FakeBridgeResponse(json.dumps({'task_id': 't_' + '1' * 24, 'state': 'queued'}).encode())

    monkeypatch.setattr(rr.urllib.request, 'urlopen', fake_urlopen)
    runner = rr.BridgeRestRemediationRunner(token_path=token_path)
    runner.run('alert:1', 'claude-sonnet', 'first attempt')
    runner.run('alert:1', 'claude-sonnet', 'retry attempt')

    assert bodies[0]['idempotency_key'] == bodies[1]['idempotency_key'] == 'alert:1'


def test_bridge_runner_fails_closed_when_no_token_file_exists(tmp_path):
    runner = rr.BridgeRestRemediationRunner(token_path=tmp_path / 'missing_token')
    outcome = runner.run('alert:1', 'claude-sonnet', 'the prompt')
    assert outcome.ok is False
    assert outcome.task_id is None
    assert outcome.error == 'bridge_token_missing'


def test_bridge_runner_rejects_a_model_other_than_sonnet_without_calling_bridge(monkeypatch, tmp_path):
    token_path, _ = _token_file(tmp_path)
    calls = []
    monkeypatch.setattr(rr.urllib.request, 'urlopen', lambda *a, **k: calls.append(1))
    runner = rr.BridgeRestRemediationRunner(token_path=token_path)
    outcome = runner.run('alert:1', 'claude-opus', 'the prompt')
    assert outcome.ok is False
    assert outcome.error == 'model_not_supported'
    assert calls == []


def test_bridge_runner_rejects_a_prompt_over_the_length_limit_without_calling_bridge(monkeypatch, tmp_path):
    token_path, _ = _token_file(tmp_path)
    calls = []
    monkeypatch.setattr(rr.urllib.request, 'urlopen', lambda *a, **k: calls.append(1))
    runner = rr.BridgeRestRemediationRunner(token_path=token_path)
    outcome = runner.run('alert:1', 'claude-sonnet', 'x' * (rr.BRIDGE_PROMPT_MAX_LENGTH + 1))
    assert outcome.ok is False
    assert outcome.error == 'prompt_too_long'
    assert calls == []


def test_bridge_runner_reports_http_errors_without_leaking_the_token(monkeypatch, tmp_path):
    token_path, token = _token_file(tmp_path)
    for code in (401, 403, 404):
        def fake_urlopen(request, timeout=None, _code=code):
            raise urllib.error.HTTPError(request.full_url, _code, 'error', {}, None)

        monkeypatch.setattr(rr.urllib.request, 'urlopen', fake_urlopen)
        runner = rr.BridgeRestRemediationRunner(token_path=token_path)
        outcome = runner.run('alert:1', 'claude-sonnet', 'the prompt')
        assert outcome.ok is False
        assert outcome.error == 'bridge_http_error'
        assert str(code) in outcome.detail
        assert token not in outcome.detail


def test_bridge_runner_reports_network_errors_as_failed(monkeypatch, tmp_path):
    token_path, _ = _token_file(tmp_path)

    def fake_urlopen(request, timeout=None):
        raise urllib.error.URLError('connection refused')

    monkeypatch.setattr(rr.urllib.request, 'urlopen', fake_urlopen)
    runner = rr.BridgeRestRemediationRunner(token_path=token_path)
    outcome = runner.run('alert:1', 'claude-sonnet', 'the prompt')
    assert outcome.ok is False
    assert outcome.error == 'bridge_unreachable'


def test_bridge_runner_fails_closed_on_a_malformed_task_id_instead_of_claiming_success(monkeypatch, tmp_path):
    token_path, _ = _token_file(tmp_path)

    def fake_urlopen(request, timeout=None):
        return _FakeBridgeResponse(json.dumps({'task_id': 'not-the-right-shape', 'state': 'queued'}).encode())

    monkeypatch.setattr(rr.urllib.request, 'urlopen', fake_urlopen)
    runner = rr.BridgeRestRemediationRunner(token_path=token_path)
    outcome = runner.run('alert:1', 'claude-sonnet', 'the prompt')
    assert outcome.ok is False
    assert outcome.task_id is None
    assert outcome.error == 'invalid_bridge_response'


def test_bridge_runner_fails_closed_when_state_is_missing(monkeypatch, tmp_path):
    token_path, _ = _token_file(tmp_path)

    def fake_urlopen(request, timeout=None):
        return _FakeBridgeResponse(json.dumps({'task_id': 't_' + '2' * 24}).encode())

    monkeypatch.setattr(rr.urllib.request, 'urlopen', fake_urlopen)
    runner = rr.BridgeRestRemediationRunner(token_path=token_path)
    outcome = runner.run('alert:1', 'claude-sonnet', 'the prompt')
    assert outcome.ok is False
    assert outcome.error == 'invalid_bridge_response'


def test_bridge_runner_fails_closed_on_non_json_response_body(monkeypatch, tmp_path):
    token_path, _ = _token_file(tmp_path)

    def fake_urlopen(request, timeout=None):
        return _FakeBridgeResponse(b'not json')

    monkeypatch.setattr(rr.urllib.request, 'urlopen', fake_urlopen)
    runner = rr.BridgeRestRemediationRunner(token_path=token_path)
    outcome = runner.run('alert:1', 'claude-sonnet', 'the prompt')
    assert outcome.ok is False
    assert outcome.error == 'invalid_bridge_response'


# ---- status: progress of a dispatched task ---------------------------------

TASK = 't_' + 'abc123' * 4


def _routed_urlopen(monkeypatch, routes, seen):
    def fake_urlopen(request, timeout=None):
        seen.append((request.get_method(), request.full_url, dict(request.header_items())))
        path = request.full_url.split('/v1', 1)[1]
        body = routes[path]
        if isinstance(body, Exception):
            raise body
        return _FakeBridgeResponse(json.dumps(body).encode())
    monkeypatch.setattr(rr.urllib.request, 'urlopen', fake_urlopen)


def test_status_reports_a_running_task_without_asking_for_its_result(monkeypatch, tmp_path):
    token_path, token = _token_file(tmp_path)
    seen = []
    _routed_urlopen(monkeypatch, {f'/tasks/{TASK}': {'task_id': TASK, 'state': 'running'}}, seen)
    status = rr.BridgeRestRemediationRunner(token_path=token_path).status(TASK)
    assert (status.ok, status.state, status.terminal) == (True, 'running', False)
    assert [s[0] for s in seen] == ['GET']
    assert seen[0][2]['Authorization'] == f'Bearer {token}'
    assert seen[0][2]['User-agent'] == rr.BRIDGE_USER_AGENT


def test_status_reads_the_result_summary_once_the_task_succeeds(monkeypatch, tmp_path):
    token_path, _ = _token_file(tmp_path)
    _routed_urlopen(monkeypatch, {
        f'/tasks/{TASK}': {'task_id': TASK, 'state': 'succeeded'},
        f'/tasks/{TASK}/result': {'task_id': TASK, 'state': 'succeeded', 'ready': True, 'ok': True,
                                   'summary': 'fixed it'},
    }, [])
    status = rr.BridgeRestRemediationRunner(token_path=token_path).status(TASK)
    assert (status.ok, status.terminal, status.succeeded, status.summary) == (True, True, True, 'fixed it')


def test_status_reports_a_failed_task_with_its_last_error(monkeypatch, tmp_path):
    token_path, _ = _token_file(tmp_path)
    _routed_urlopen(monkeypatch, {
        f'/tasks/{TASK}': {'task_id': TASK, 'state': 'failed', 'last_error': 'worker timed out'},
        f'/tasks/{TASK}/result': {'task_id': TASK, 'state': 'failed', 'ready': False, 'last_error': None},
    }, [])
    status = rr.BridgeRestRemediationRunner(token_path=token_path).status(TASK)
    assert (status.terminal, status.succeeded, status.detail) == (True, False, 'worker timed out')


def test_status_fails_closed_on_an_unreachable_bridge_without_leaking_the_token(monkeypatch, tmp_path):
    token_path, token = _token_file(tmp_path)
    _routed_urlopen(monkeypatch, {f'/tasks/{TASK}': urllib.error.URLError('down')}, [])
    status = rr.BridgeRestRemediationRunner(token_path=token_path).status(TASK)
    assert (status.ok, status.error) == (False, 'bridge_status_unavailable')
    assert token not in status.detail


def test_status_refuses_anything_that_is_not_a_bridge_task_id(monkeypatch, tmp_path):
    token_path, _ = _token_file(tmp_path)
    seen = []
    _routed_urlopen(monkeypatch, {}, seen)
    status = rr.BridgeRestRemediationRunner(token_path=token_path).status('../agents')
    assert (status.ok, status.error) == (False, 'invalid_task_id')
    assert seen == []
