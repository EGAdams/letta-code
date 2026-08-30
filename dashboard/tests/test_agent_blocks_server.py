import server
from servers.agent_blocks import AgentBlocksServer


class _Response:
    status = 200

    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def test_healthy_server_is_not_started_twice(tmp_path):
    launched = []
    service = AgentBlocksServer(
        start_script=tmp_path / 'start.sh',
        startup_log=tmp_path / 'startup.log',
        health_opener=lambda *_args, **_kwargs: _Response(),
        launcher=lambda *_args, **_kwargs: launched.append((_args, _kwargs)),
    )

    result = service.start()

    assert result.ok is True
    assert 'already running' in result.text
    assert launched == []


def test_down_server_launches_the_spa_once_and_marks_it_starting(tmp_path):
    script = tmp_path / 'start.sh'
    script.write_text('#!/usr/bin/env bash\n', encoding='utf-8')
    log = tmp_path / 'startup.log'
    launched = []
    marked = []

    def unavailable(*_args, **_kwargs):
        raise OSError('connection refused')

    service = AgentBlocksServer(
        start_script=script,
        startup_log=log,
        health_opener=unavailable,
        launcher=lambda *args, **kwargs: launched.append((args, kwargs)),
        mark_starting=marked.append,
    )

    result = service.start()

    assert result.ok is True
    assert launched[0][0] == (['bash', str(script)],)
    assert launched[0][1]['cwd'] == str(script.parent)
    assert launched[0][1]['start_new_session'] is True
    assert marked == ['agent-blocks']
    assert 'launch requested' in log.read_text(encoding='utf-8')


def test_unsuccessful_health_response_is_closed_and_treated_as_down(tmp_path):
    script = tmp_path / 'start.sh'
    script.write_text('#!/usr/bin/env bash\n', encoding='utf-8')
    response = _Response()
    response.status = 503
    launched = []
    service = AgentBlocksServer(
        start_script=script,
        startup_log=tmp_path / 'startup.log',
        health_opener=lambda *_args, **_kwargs: response,
        launcher=lambda *args, **kwargs: launched.append((args, kwargs)),
    )

    result = service.start()

    assert response.closed is True
    assert result.ok is True
    assert len(launched) == 1


def test_missing_start_script_fails_closed(tmp_path):
    service = AgentBlocksServer(
        start_script=tmp_path / 'missing.sh',
        startup_log=tmp_path / 'startup.log',
        health_opener=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            OSError('connection refused')),
    )

    result = service.start()

    assert result.ok is False
    assert 'Start script not found' in result.text


def test_launch_error_is_returned_instead_of_escaping(tmp_path):
    script = tmp_path / 'start.sh'
    script.write_text('#!/usr/bin/env bash\n', encoding='utf-8')

    def unavailable(*_args, **_kwargs):
        raise OSError('connection refused')

    def fail_launch(*_args, **_kwargs):
        raise OSError('cannot launch')

    service = AgentBlocksServer(
        start_script=script,
        startup_log=tmp_path / 'startup.log',
        health_opener=unavailable,
        launcher=fail_launch,
    )

    result = service.start()

    assert result.ok is False
    assert result.text == 'cannot launch'


def test_dashboard_declares_agent_blocks_as_a_startup_dependency():
    tasks = {task.label: task for task in server.startup_tasks()}

    assert 'agent-blocks-autostart' in tasks
    assert tasks['agent-blocks-autostart'].target == server.ensure_agent_blocks_server
