import json

import pytest
from pydantic import ValidationError

import remediation_dispatch as rd
from remediation_runner import RemediationOutcome, RemediationStatus


class FakeRunner:
    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = []

    def run(self, alert_key, model_id, prompt):
        self.calls.append((alert_key, model_id, prompt))
        return self.outcome


def _registry(tmp_path):
    """A registry whose 'configured' state never depends on the host running the test."""
    cred = tmp_path / 'cred.json'
    cred.write_text('{}')
    registry_path = tmp_path / 'registry.json'
    registry_path.write_text(json.dumps([
        {'id': 'good-model', 'label': 'Good', 'task_capabilities': ['diagnose', 'write'], 'can_write': True,
         'cost_tier': 'low', 'dispatch_strategy': 'primary', 'verify_kind': 'credentials', 'verify_arg': str(cred)},
        {'id': 'review-only', 'label': 'Review only', 'task_capabilities': ['review'], 'can_write': False,
         'cost_tier': 'low', 'dispatch_strategy': 'secondary', 'verify_kind': 'credentials', 'verify_arg': str(cred)},
        {'id': 'unconfigured-model', 'label': 'Unconfigured', 'task_capabilities': ['diagnose', 'write'],
         'can_write': True, 'cost_tier': 'low', 'dispatch_strategy': 'primary', 'verify_kind': 'none',
         'verify_arg': 'not wired in this deployment'},
    ]))
    return registry_path


def _service(tmp_path, outcome):
    runner = FakeRunner(outcome)
    service = rd.RemediationDispatchService(
        tmp_path / 'state.json', runner, registry_path=_registry(tmp_path), clock=lambda: 1000.0)
    return service, runner


def test_dispatch_rejects_a_model_outside_the_registry(tmp_path):
    service, runner = _service(tmp_path, RemediationOutcome(ok=True, task_id='t', status='queued'))
    result = service.dispatch({'alert_key': 'a1', 'model_id': 'made-up-model', 'prompt': 'p'})
    assert result == {'ok': False, 'already_submitted': False, 'error': 'unknown_model',
                       'detail': '"made-up-model" is not a registered model'}
    assert runner.calls == []


def test_dispatch_rejects_a_registered_model_without_diagnose_or_write_capability(tmp_path):
    service, runner = _service(tmp_path, RemediationOutcome(ok=True, task_id='t', status='queued'))
    result = service.dispatch({'alert_key': 'a1', 'model_id': 'review-only', 'prompt': 'p'})
    assert result['ok'] is False
    assert result['error'] == 'model_not_capable'
    assert runner.calls == []


def test_dispatch_rejects_an_unconfigured_model_even_with_the_right_capabilities(tmp_path):
    service, runner = _service(tmp_path, RemediationOutcome(ok=True, task_id='t', status='queued'))
    result = service.dispatch({'alert_key': 'a1', 'model_id': 'unconfigured-model', 'prompt': 'p'})
    assert result['ok'] is False
    assert result['error'] == 'model_unavailable'
    assert runner.calls == []


def test_dispatch_runs_the_runner_for_a_capable_configured_model_and_persists_the_ledger(tmp_path):
    service, runner = _service(tmp_path, RemediationOutcome(ok=True, task_id='remediate-1', status='queued'))
    result = service.dispatch({'alert_key': 'a1', 'model_id': 'good-model', 'prompt': 'the prompt',
                                'title': 'T', 'agent': 'sydney', 'task_id': 'src-1'})
    assert result == {'ok': True, 'already_submitted': False, 'status': 'queued',
                       'task_id': 'remediate-1', 'model_id': 'good-model'}
    assert runner.calls == [('a1', 'good-model', 'the prompt')]
    state = json.loads((tmp_path / 'state.json').read_text())
    assert state['a1']['status'] == 'submitted'
    assert state['a1']['task_id'] == 'remediate-1'


def test_a_second_dispatch_for_the_same_alert_key_returns_the_first_result_without_rerunning(tmp_path):
    service, runner = _service(tmp_path, RemediationOutcome(ok=True, task_id='remediate-1', status='queued'))
    service.dispatch({'alert_key': 'a1', 'model_id': 'good-model', 'prompt': 'p1'})
    result = service.dispatch({'alert_key': 'a1', 'model_id': 'good-model', 'prompt': 'p2 (resubmit attempt)'})
    assert result == {'ok': True, 'already_submitted': True, 'status': 'queued',
                       'task_id': 'remediate-1', 'model_id': 'good-model'}
    assert len(runner.calls) == 1  # never rerun once an alert key is already submitted


def test_a_failed_runner_outcome_is_recorded_and_can_be_retried(tmp_path):
    service, runner = _service(tmp_path, RemediationOutcome(
        ok=False, task_id='t', status='failed', error='runner_failed', detail='boom'))
    result = service.dispatch({'alert_key': 'a1', 'model_id': 'good-model', 'prompt': 'p'})
    assert result['ok'] is False
    assert result['error'] == 'runner_failed'
    assert result['detail'] == 'boom'
    state = json.loads((tmp_path / 'state.json').read_text())
    assert state['a1']['status'] == 'failed'
    # a failure is not idempotent-locked; a retry is allowed to run the runner again
    service.dispatch({'alert_key': 'a1', 'model_id': 'good-model', 'prompt': 'p'})
    assert len(runner.calls) == 2


def test_malformed_request_bodies_are_rejected_before_touching_the_runner(tmp_path):
    service, runner = _service(tmp_path, RemediationOutcome(ok=True, task_id='t', status='queued'))
    with pytest.raises(ValidationError):
        service.dispatch({'alert_key': '', 'model_id': 'good-model', 'prompt': 'p'})
    with pytest.raises(ValidationError):
        service.dispatch({'alert_key': 'a1', 'model_id': 'good-model', 'prompt': 'p', 'extra': 'nope'})
    with pytest.raises(ValidationError):
        service.dispatch({'alert_key': 'a1', 'model_id': 'good-model'})  # missing prompt
    assert runner.calls == []


def test_from_environment_reads_the_configured_state_path(monkeypatch, tmp_path):
    custom = tmp_path / 'custom_state.json'
    monkeypatch.setenv('REMEDIATION_DISPATCH_STATE_PATH', str(custom))
    service = rd.from_environment()
    assert service._state_path == custom


class FakeStatusReader:
    def __init__(self, status):
        self._status = status
        self.calls = []

    def status(self, task_id):
        self.calls.append(task_id)
        return self._status


def _submitted(tmp_path, reader):
    runner = FakeRunner(RemediationOutcome(ok=True, task_id='t_1', status='queued'))
    service = rd.RemediationDispatchService(tmp_path / 'state.json', runner, registry_path=_registry(tmp_path),
                                            clock=lambda: 1000.0, status_reader=reader)
    service.dispatch({'alert_key': 'a1', 'model_id': 'good-model', 'prompt': 'p'})
    return service


def test_status_reports_the_live_task_state_and_remembers_it(tmp_path):
    reader = FakeStatusReader(RemediationStatus(ok=True, task_id='t_1', state='running', terminal=False))
    service = _submitted(tmp_path, reader)
    result = service.status('a1')
    assert result == {'ok': True, 'task_id': 't_1', 'state': 'running', 'terminal': False,
                       'succeeded': None, 'summary': '', 'detail': ''}
    assert reader.calls == ['t_1']
    assert json.loads((tmp_path / 'state.json').read_text())['a1']['task_state'] == 'running'
    # a duplicate click now reports the remembered live state
    again = service.dispatch({'alert_key': 'a1', 'model_id': 'good-model', 'prompt': 'p'})
    assert again['status'] == 'running'


def test_status_only_reports_alert_keys_this_ledger_dispatched(tmp_path):
    reader = FakeStatusReader(RemediationStatus(ok=True, task_id='x', state='running', terminal=False))
    service = _submitted(tmp_path, reader)
    assert service.status('someone-else')['error'] == 'not_submitted'
    assert reader.calls == []


def test_status_says_so_when_the_runner_cannot_report_progress(tmp_path):
    service = _submitted(tmp_path, None)
    result = service.status('a1')
    assert result['ok'] is False
    assert result['error'] == 'status_unsupported'
    assert result['state'] == 'queued'


def test_from_environment_wires_the_bridge_runner_as_its_status_reader(monkeypatch, tmp_path):
    import remediation_runner as rr
    monkeypatch.delenv('REMEDIATION_ADW_SCRIPT', raising=False)
    token = tmp_path / 'client_token'
    token.write_text('tok')
    monkeypatch.setattr(rr, 'BRIDGE_TOKEN_PATH', token)
    monkeypatch.setenv('REMEDIATION_DISPATCH_STATE_PATH', str(tmp_path / 's.json'))
    service = rd.from_environment()
    assert isinstance(service._status_reader, rr.BridgeRestRemediationRunner)
