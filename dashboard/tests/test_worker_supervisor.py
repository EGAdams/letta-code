from monitoring import agent_bridge_poll, worker_supervisor


class Probe:
    def __init__(self, observation):
        self.observation = observation

    def inspect(self, pid):
        return self.observation


def service(pid=4242):
    return agent_bridge_poll.ServiceState(active='active', pid=pid)


def test_healthy_requires_process_heartbeat_and_nonstagnant_queue():
    result = worker_supervisor.diagnose(
        service=service(), state={'heartbeat_at': 1000},
        tasks=[{'status': 'queued', 'queue_age': 2}], now=1001,
        probe=Probe(worker_supervisor.ProcessObservation(4242, True, 'agent-bridge-worker')),
    )
    assert result['status'] == 'healthy'
    assert result['process']['present'] is True


def test_active_systemd_without_expected_process_is_offline():
    result = worker_supervisor.diagnose(
        service=service(), state={'heartbeat_at': 1000}, tasks=[], now=1001,
        probe=Probe(worker_supervisor.ProcessObservation(4242, False, reason='wrong process')),
    )
    assert result['status'] == 'offline'
    assert 'wrong process' in result['reasons']


def test_old_heartbeat_is_stalled():
    result = worker_supervisor.diagnose(
        service=service(), state={'heartbeat_at': 0}, tasks=[], now=1000,
        probe=Probe(worker_supervisor.ProcessObservation(4242, True)),
    )
    assert result['status'] == 'stalled'
    assert result['heartbeat']['fresh'] is False


def test_old_queued_task_is_stagnant(monkeypatch):
    monkeypatch.setenv('WORKER_STAGNATION_SECONDS', '10')
    result = worker_supervisor.diagnose(
        service=service(), state={'heartbeat_at': 1000},
        tasks=[{'status': 'queued', 'queue_age': 11}], now=1001,
        probe=Probe(worker_supervisor.ProcessObservation(4242, True)),
    )
    assert result['status'] == 'stalled'
    assert result['queue']['stagnant'] is True


def test_missing_ledger_is_explicitly_unavailable():
    result = worker_supervisor.diagnose(
        service=service(), state={'heartbeat_at': 1000}, tasks=None, now=1001,
        probe=Probe(worker_supervisor.ProcessObservation(4242, True)),
    )
    assert result['queue']['available'] is False


def test_the_real_worker_command_line_is_recognised(tmp_path, monkeypatch):
    import os
    observation = worker_supervisor.ProcWorkerProbe().inspect(os.getpid())
    assert observation.present is False  # pytest is not the worker
    monkeypatch.setattr(worker_supervisor.Path, 'read_bytes',
                        lambda self: b'/x/.venv/bin/python\0adws/adw_bridge_worker.py\0--watch\0')
    assert worker_supervisor.ProcWorkerProbe().inspect(4242).present is True


def test_poll_state_waiting_uses_next_check_at_and_working_allows_a_long_drain():
    alive = Probe(worker_supervisor.ProcessObservation(4242, True))
    waiting = {'phase': 'waiting', 'checked_at': 0, 'next_check_at': 1060}
    assert worker_supervisor.diagnose(service=service(), state=waiting, tasks=[], now=1000, probe=alive)['status'] == 'healthy'
    assert worker_supervisor.diagnose(service=service(), state=waiting, tasks=[], now=1300, probe=alive)['status'] == 'stalled'
    working = {'phase': 'working', 'checked_at': '1970-01-01T00:16:40+00:00'}
    assert worker_supervisor.diagnose(service=service(), state=working, tasks=[], now=1000 + 600, probe=alive)['status'] == 'healthy'
    assert worker_supervisor.diagnose(service=service(), state=working, tasks=[], now=1000 + 2000, probe=alive)['status'] == 'stalled'
