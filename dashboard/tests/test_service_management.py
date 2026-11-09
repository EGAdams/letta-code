"""Service states, outage persistence, and the dashboard read-only endpoint."""
import json
from subprocess import CompletedProcess, TimeoutExpired

import pytest

from monitoring import service_management as services
from monitoring.service_catalog import configured_services
from monitoring.service_management_models import ServiceDefinition, ServiceObservation
from tests.http_app_harness import DashboardClient, ServiceRecorder, start_server

API = ServiceDefinition(key='api', label='API', unit='factory-ops-api.service')


def observation(status, now, since=None):
    return ServiceObservation(**API.model_dump(), status=status, active={
        'up': 'active', 'down': 'failed', 'unknown': 'unknown'}[status],
        checked_at=now, since=since)


def test_catalog_reads_configured_worker_and_both_lanes_without_exposing_secrets(tmp_path):
    config = tmp_path / 'env'
    config.write_text('FACTORY_OPS_TOKEN=private-secret\nFACTORY_OPS_WORKER_UNIT=custom.service\n'
                      'FACTORY_OPS_SYSTEMD_SCOPE=system\n')
    catalog, error = configured_services(config)
    assert not error
    assert {item.unit for item in catalog} == {
        'factory-ops-api.service', 'factory-ops-watch.service', 'custom.service',
        'agent-bridge-worker.service', 'agent-bridge-worker-express.service'}
    assert catalog[2].scope == 'system'
    assert 'private-secret' not in str(catalog)


@pytest.mark.parametrize('value', ['bad.service;touch /tmp/x', '--bad.service', '../bad.service'])
def test_catalog_rejects_command_injection_and_reports_invalid_config(tmp_path, value):
    config = tmp_path / 'env'
    config.write_text(f'FACTORY_OPS_WORKER_UNIT={value}\n')
    catalog, error = configured_services(config)
    assert error
    assert all(item.unit != value for item in catalog)


def test_configured_general_lane_is_not_duplicated(tmp_path):
    config = tmp_path / 'env'
    config.write_text('FACTORY_OPS_SYSTEMD_SCOPE=user\n')
    catalog, error = configured_services(config)
    assert not error
    assert len(catalog) == 4
    assert catalog[2].label == 'General Worker'


@pytest.mark.parametrize(('active', 'load', 'expected'), [
    ('active', 'loaded', 'up'), ('failed', 'loaded', 'down'),
    ('inactive', 'loaded', 'down'), ('activating', 'loaded', 'down'),
    ('inactive', 'not-found', 'concern'), ('unknown', 'loaded', 'unknown'),
])
def test_fixed_systemd_probe(monkeypatch, active, load, expected):
    calls = []
    def run(args, **kwargs):
        calls.append((args, kwargs))
        return CompletedProcess(args, 0, f'ActiveState={active}\nLoadState={load}\n'
                                'MainPID=123\nActiveEnterTimestamp=@50\nStateChangeTimestamp=@60\n', '')
    monkeypatch.setattr(services.subprocess, 'run', run)
    result = services.SystemdServiceProbe().observe(API, 100)
    assert result.status == expected
    assert calls[0][0][:4] == ['systemctl', '--user', 'show', API.unit]
    assert calls[0][1]['shell'] is False
    assert result.pid == 123


def test_unreachable_systemd_is_unknown_not_down(monkeypatch):
    def fail(*args, **kwargs):
        raise TimeoutExpired('systemctl', 4)
    monkeypatch.setattr(services.subprocess, 'run', fail)
    result = services.SystemdServiceProbe().observe(API, 100)
    assert result.status == 'unknown'
    assert result.down_for_seconds is None


def test_systemd_nonzero_exit_cannot_report_healthy(monkeypatch):
    monkeypatch.setattr(services.subprocess, 'run', lambda *a, **k:
                        CompletedProcess(a, 1, 'ActiveState=active\nLoadState=loaded\n', 'bus error'))
    assert services.SystemdServiceProbe().observe(API, 100).status == 'unknown'


def test_history_survives_restart_and_records_recovery(tmp_path):
    path = tmp_path / 'history.json'
    history = services.JsonServiceHistory(path)
    first = observation('down', 100, 80)
    assert history.record([first]) == ''
    assert first.down_for_seconds == 20
    resumed = observation('down', 160, 140)
    assert services.JsonServiceHistory(path).record([resumed]) == ''
    assert resumed.down_for_seconds == 80
    assert len(resumed.events) == 1
    recovered = observation('up', 200, 190)
    history.record([recovered])
    assert recovered.events[0]['outage_seconds'] == 110
    assert recovered.down_since is None
    assert path.stat().st_mode & 0o777 == 0o600


def test_unknown_check_does_not_end_an_outage(tmp_path):
    history = services.JsonServiceHistory(tmp_path / 'history.json')
    history.record([observation('down', 100)])
    unknown = observation('unknown', 130)
    history.record([unknown])
    assert unknown.down_for_seconds is None
    recovered = observation('up', 200, 190)
    history.record([recovered])
    assert recovered.events[0]['outage_seconds'] == 90


def test_corrupt_history_reports_error_but_preserves_live_state(tmp_path):
    path = tmp_path / 'history.json'
    path.write_text(json.dumps({'user:factory-ops-api.service': {'down_since': 'broken'}}))
    current = observation('up', 100)
    assert services.JsonServiceHistory(path).record([current])
    assert current.status == 'up'


def test_health_is_worst_service_and_cached(monkeypatch, tmp_path):
    monkeypatch.setattr(services, 'configured_services', lambda: ([API], ''))
    class Probe:
        calls = 0
        def observe(self, definition, now):
            self.calls += 1
            return observation('down', now)
    probe = Probe()
    monitor = services.ServiceMonitor(probe, services.JsonServiceHistory(tmp_path / 'history.json'))
    assert monitor.payload()['status'] == 'down'
    assert monitor.payload()['services'][0]['down_for_seconds'] == 0
    assert probe.calls == 1


def test_monitor_collects_without_a_browser_and_can_stop(monkeypatch, tmp_path):
    import threading
    monkeypatch.setattr(services, 'configured_services', lambda: ([API], ''))
    stop = threading.Event()
    class Probe:
        def observe(self, definition, now):
            stop.set()
            return observation('up', now)
    monitor = services.ServiceMonitor(Probe(), services.JsonServiceHistory(tmp_path / 'history.json'))
    monitor.run(stop)
    assert monitor.cached['services'][0]['status'] == 'up'
    assert (tmp_path / 'history.json').exists()


def test_runtime_starts_the_service_monitor_without_starting_real_threads(monkeypatch):
    from http_app import runtime
    started = []
    class SocketServer:
        def __init__(self, *args):
            pass
        def serve_forever(self):
            pass
    monkeypatch.setattr(runtime, 'ReusableHTTPServer', SocketServer)
    monkeypatch.setattr(runtime, 'start_background_tasks', started.extend)
    runtime.serve(object)
    assert [task.label for task in started] == ['service-management-monitor']
    assert started[0].target == services.MONITOR.run


def test_route_returns_service_payload_and_ignores_arbitrary_unit_query(monkeypatch):
    recorder = ServiceRecorder()
    recorder.install(monkeypatch, {'service_management_payload': lambda: {'status': 'up', 'services': []}})
    httpd, thread, port = start_server()
    try:
        response = DashboardClient(port).get('/api/service-management?unit=arbitrary.service')
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)
    assert response.status == 200
    assert response.json == {'status': 'up', 'services': []}


def test_live_dashboard_page_exposes_service_navigation(monkeypatch):
    """Test the served shell as well as the synthetic controller DOM."""
    from html.parser import HTMLParser
    class Page(HTMLParser):
        def __init__(self):
            super().__init__()
            self.elements = {}
            self.stylesheets = []
        def handle_starttag(self, tag, attributes):
            attributes = dict(attributes)
            if attributes.get('id'):
                self.elements[attributes['id']] = (tag, attributes)
            if tag == 'link' and attributes.get('rel') == 'stylesheet':
                self.stylesheets.append(attributes.get('href', '').split('?')[0])
    recorder = ServiceRecorder()
    recorder.install(monkeypatch)
    httpd, thread, port = start_server()
    try:
        response = DashboardClient(port).get('/')
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)
    assert response.status == 200
    page = Page()
    page.feed(response.text)
    assert 'btn-service-mgmt' in page.elements, 'Service Management is missing from the served dashboard'
    tag, attributes = page.elements['btn-service-mgmt']
    assert tag == 'button'
    assert attributes['data-nav'] == 'status'
    assert attributes['data-target'] == 'service-management'
    for element_id in ('nav-services', 'service-management-tabs', 'btn-back-services',
                       'service-management', 'service-management-body', 'service-management-refresh'):
        assert element_id in page.elements
    assert '/css/service-management.css' in page.stylesheets
