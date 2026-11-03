"""The scan bridge as the dashboard serves it: real ladders, real handler, a live port."""

import hashlib
import json
import os

import pytest

import server
from hardware import scanner_invoke
from scan_jobs import composition
from scan_jobs.auth import SCOPES
from tests.http_app_harness import DashboardClient, ServiceRecorder, start_server

TOKEN = 'wiring-test-token-not-a-secret-42'
AUTH = {'Authorization': f'Bearer {TOKEN}'}


@pytest.fixture(scope='module')
def live():
    httpd, _thread, port = start_server()
    yield DashboardClient(port)
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture
def no_scans(monkeypatch):
    """Any scan reaching the hardware layer fails the test."""
    def refuse(*_a, **_k):
        pytest.fail('a route reached the scanner hardware')
    monkeypatch.setattr(server, 'run_scanner', refuse)
    monkeypatch.setattr(scanner_invoke, 'invoke_scanner', refuse)


@pytest.fixture
def client_file():
    path = composition.config_dir() / 'clients.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'clients': [{'name': 'agent-bridge-worker', 'scopes': list(SCOPES),
                                             'token_sha256': hashlib.sha256(TOKEN.encode()).hexdigest()}]}))
    os.chmod(path, 0o600)
    return path


def test_legacy_scanner_status_never_scans(live, monkeypatch):
    recorder = ServiceRecorder()
    recorder.install(monkeypatch)
    live.get('/api/scanner-status?scanner=window')
    live.get('/api/scanner-status?scanner=freezer')
    assert not recorder.called('run_scanner') and not recorder.called('invoke_scanner')


def test_the_bridge_answers_through_the_dashboard(live, no_scans, client_file):
    resp = live.get('/api/scan-bridge/v1/scans', headers=AUTH)
    assert (resp.status, resp.json['scans'], resp.json['next_cursor']) == (200, [], None)
    assert 'Access-Control-Allow-Origin' not in resp.headers


def test_no_token_and_browsers_are_refused(live, no_scans, client_file):
    assert live.get('/api/scan-bridge/v1/scans').status == 401
    assert live.get('/api/scan-bridge/v1/scans', headers={**AUTH, 'Origin': 'http://evil.example'}).status == 403
    assert live.post('/api/scan-bridge/v1/scans', {'scanner': 'window'}).status == 401


def test_a_bridge_start_is_refused_while_the_flag_is_off(live, no_scans, client_file):
    resp = live.post('/api/scan-bridge/v1/scans', {'scanner': 'window'}, headers=AUTH)
    assert (resp.status, resp.json['error']['code']) == (403, 'bridge_scans_disabled')


def test_the_dashboard_button_is_recorded_as_a_scan_job(live, monkeypatch, client_file):
    monkeypatch.setattr(server, 'run_scanner', lambda key: {'status': 'offline', 'error': 'Scanner not found'})
    resp = live.post('/api/scanner-scan', {'scanner': 'freezer'})
    scan_id = resp.json['scan_id']
    assert resp.json['status'] == 'offline'
    status = live.get(f'/api/scan-bridge/v1/scans/{scan_id}', headers=AUTH).json
    assert (status['source'], status['status'], status['error_code']) == ('dashboard', 'failed', 'device_offline')
