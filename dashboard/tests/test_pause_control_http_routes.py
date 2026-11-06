"""/api/pause-control/v1: auth gate, request/list/acknowledge shapes.

This dispatch function is written and tested, but nothing in http_app/ calls
it yet -- see the module docstring in pause_control/http_routes.py for why,
and docs/bridge-pause-resume.md for the full picture. These tests prove the
façade works in isolation; they do not prove a browser or ChatGPT can reach
it today.
"""

from __future__ import annotations

import json

import pytest

from pause_control import composition
from pause_control.http_routes import PREFIX, ControlHttpRequest, pause_control_dispatch
from tests.pause_control_fakes import Rig

TOKEN = 'test-pause-control-token-not-a-secret'


class _Authorizer:
    def __init__(self, token):
        self._token = token

    def configured(self):
        return bool(self._token)

    def authorize(self, header):
        return bool(self._token) and header == f'Bearer {self._token}'


@pytest.fixture
def rig(tmp_path, monkeypatch):
    built = Rig(tmp_path, pausable=frozenset({'queued-task-1'}))
    monkeypatch.setattr(composition, '_built', (built.service, _Authorizer(TOKEN)))
    yield built
    composition.reset()


def call(method, path, body=None, token=TOKEN, **headers):
    path, _, query = path.partition('?')
    hdrs = {k.replace('_', '-'): v for k, v in headers.items()}
    if token:
        hdrs['authorization'] = f'Bearer {token}'
    raw = json.dumps(body).encode() if body is not None else b''
    response = pause_control_dispatch(ControlHttpRequest(method=method, path=PREFIX + path, query=query,
                                                         headers=hdrs, body=raw))
    data = json.loads(response.body)
    return response.code, data


# -- authorization ------------------------------------------------------------------
def test_missing_token_is_unauthorized(rig):
    code, data = call('GET', '/requests', token=None)
    assert code == 401
    assert data['error']['code'] == 'unauthorized'


def test_wrong_token_is_unauthorized(rig):
    code, data = call('GET', '/requests', token='wrong')
    assert code == 401


def test_unconfigured_token_is_service_unavailable(tmp_path, monkeypatch):
    built = Rig(tmp_path)
    monkeypatch.setattr(composition, '_built', (built.service, _Authorizer('')))
    code, data = call('GET', '/requests', token='anything')
    assert (code, data['error']['code']) == (503, 'not_configured')
    composition.reset()


# -- creating -------------------------------------------------------------------------
def test_create_a_pause_request(rig):
    code, data = call('POST', '/requests', {'task_id': 'queued-task-1', 'action': 'pause', 'requested_by': 'eg'})
    assert code == 201
    assert data['status'] == 'pause_requested'
    assert data['replayed'] is False


def test_a_replayed_create_is_200_not_201(rig):
    first = call('POST', '/requests', {'task_id': 'queued-task-1', 'action': 'pause'})
    second = call('POST', '/requests', {'task_id': 'queued-task-1', 'action': 'pause'})
    assert (first[0], second[0]) == (201, 200)
    assert first[1]['request_id'] == second[1]['request_id']


def test_an_unknown_task_pause_is_a_409_not_a_500(rig):
    code, data = call('POST', '/requests', {'task_id': 'mystery-task', 'action': 'pause'})
    assert (code, data['error']['code']) == (409, 'pausability_unknown')


def test_bad_action_is_a_400(rig):
    code, data = call('POST', '/requests', {'task_id': 'x', 'action': 'cancel'})
    assert (code, data['error']['code']) == (400, 'bad_request')


def test_unknown_body_field_is_a_400(rig):
    code, data = call('POST', '/requests', {'task_id': 'x', 'action': 'pause', 'extra': 1})
    assert (code, data['error']['code']) == (400, 'bad_request')


def test_malformed_json_body_is_a_400(rig):
    response = pause_control_dispatch(ControlHttpRequest(
        method='POST', path=PREFIX + '/requests', headers={'authorization': f'Bearer {TOKEN}'},
        body=b'{not json'))
    assert response.code == 400
    assert json.loads(response.body)['error']['code'] == 'bad_request'


# -- listing / reading ----------------------------------------------------------------
def test_list_by_task_id(rig):
    call('POST', '/requests', {'task_id': 'queued-task-1', 'action': 'pause'})
    code, data = call('GET', '/requests?task_id=queued-task-1')
    assert code == 200
    assert len(data['requests']) == 1


def test_get_unknown_request_id_is_404(rig):
    code, data = call('GET', '/requests/pc_doesnotexist000000000')
    assert (code, data['error']['code']) == (404, 'request_not_found')


def test_unknown_route_is_404(rig):
    code, _ = call('GET', '/not-a-route')
    assert code == 404


def test_wrong_method_is_405(rig):
    code, data = call('DELETE', '/requests')
    assert (code, data['error']['code']) == (405, 'method_not_allowed')


# -- acknowledging (the worker-side callback nothing calls yet) ------------------------
def test_acknowledge_transitions_the_record(rig):
    _, created = call('POST', '/requests', {'task_id': 'queued-task-1', 'action': 'pause'})
    request_id = created['request_id']
    code, data = call('POST', f'/requests/{request_id}/acknowledge',
                      {'status': 'paused', 'actor': 'agent-bridge-worker'})
    assert (code, data['status']) == (200, 'paused')


def test_acknowledge_with_an_invalid_transition_is_409(rig):
    _, created = call('POST', '/requests', {'task_id': 'queued-task-1', 'action': 'pause'})
    request_id = created['request_id']
    code, data = call('POST', f'/requests/{request_id}/acknowledge', {'status': 'resumed'})
    assert (code, data['error']['code']) == (409, 'invalid_transition')
