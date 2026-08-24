"""Behavioural contracts for the routes, asserted through a real socket.

These complement test_http_app_route_inventory.py: that file proves every route
still *dispatches*, this one proves the ones with real contracts still mean the
same thing. Both only ever look at what a browser sees, so both survive the
route-registry refactor.
"""
import json
import socket

import pytest

import server
from http_app import post_routes
from tests.http_app_harness import (
    DashboardClient,
    FakeUrllib,
    ServiceRecorder,
    start_server,
)


@pytest.fixture(scope='module')
def live():
    httpd, thread, port = start_server()
    yield DashboardClient(port)
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture
def svc(monkeypatch):
    recorder = ServiceRecorder()
    recorder.install(monkeypatch)
    monkeypatch.setattr(post_routes, 'urllib', FakeUrllib())
    return recorder


@pytest.fixture
def stub(monkeypatch):
    """Replace one service for the duration of a test."""
    def _stub(name, value):
        monkeypatch.setattr(server, name, value, raising=False)
    return _stub


# ==========================================================================
# Response envelope — every JSON route, every time
# ==========================================================================
class TestResponseEnvelope:
    @pytest.mark.parametrize('path', [
        '/api/code-status', '/api/agents', '/api/pc-monitors',
        '/api/model-stats-sources', '/api/vendor-keys', '/api/servers',
    ])
    def test_json_routes_declare_json(self, live, svc, path):
        assert live.get(path).headers['Content-Type'] == 'application/json'

    @pytest.mark.parametrize('path', ['/api/code-status', '/api/agents'])
    def test_json_routes_are_uncacheable(self, live, svc, path):
        headers = live.get(path).headers
        assert headers['Cache-Control'] == 'no-store, no-cache, must-revalidate, max-age=0'
        assert headers['Pragma'] == 'no-cache'
        assert headers['Expires'] == '0'

    def test_content_length_matches_the_body(self, live, svc):
        resp = live.get('/api/code-status')
        assert int(resp.headers['Content-Length']) == len(resp.body)

    def test_cors_is_advertised_on_success(self, live, svc):
        assert live.get('/api/code-status').headers['Access-Control-Allow-Origin'] == '*'

    def test_a_body_is_valid_json(self, live, svc, stub):
        stub('get_code_status', lambda: {'changed': False, 'files': []})
        assert live.get('/api/code-status').json == {'changed': False, 'files': []}

    def test_unicode_is_not_mangled_in_transit(self, live, svc, stub):
        stub('get_code_status', lambda: {'note': 'Rosemary ≥ 46 — ⚠ ok'})
        assert live.get('/api/code-status').json['note'] == 'Rosemary ≥ 46 — ⚠ ok'


# ==========================================================================
# /api/agents — documented to be a bare array
# ==========================================================================
class TestAgentsContract:
    def test_returns_a_bare_array_not_an_object(self, live, svc, stub):
        """CLAUDE.md: '/api/agents must return a bare array'. The frontend
        iterates the response directly, so wrapping it breaks the agent list."""
        stub('build_agent_list', lambda force_refresh=False: [{'id': 'a', 'name': 'Mazda'}])
        body = live.get('/api/agents').json
        assert isinstance(body, list)
        assert body[0]['name'] == 'Mazda'

    def test_an_empty_roster_is_an_empty_array(self, live, svc, stub):
        stub('build_agent_list', lambda force_refresh=False: [])
        assert live.get('/api/agents').json == []

    def test_refresh_1_forces_a_roster_refresh(self, live, svc):
        live.get('/api/agents?refresh=1')
        assert svc.kwargs_for('build_agent_list') == {'force_refresh': True}

    @pytest.mark.parametrize('query', ['', '?refresh=0', '?refresh=', '?refresh=yes',
                                       '?refresh=true', '?refresh=2'])
    def test_only_the_literal_1_forces_a_refresh(self, live, svc, query):
        """The cache is a 12-30s Letta roster fetch; anything but ?refresh=1
        must use the cached copy."""
        live.get('/api/agents' + query)
        assert svc.kwargs_for('build_agent_list') == {'force_refresh': False}


# ==========================================================================
# Claude Code has no Letta agent — the 'agent-claude' branch
# ==========================================================================
class TestClaudeAgentSpecialCase:
    def test_thoughts_are_empty_for_claude(self, live, svc):
        """Claude Code has no reasoning stream; the route short-circuits."""
        assert live.get('/api/thoughts?agent=agent-claude').json == []

    def test_claude_thoughts_never_touch_letta(self, live, svc):
        live.get('/api/thoughts?agent=agent-claude')
        assert not svc.called('cached_thoughts')

    def test_thoughts_for_an_unknown_agent_are_empty(self, live, svc, stub):
        stub('letta_id_for', lambda a: None)
        assert live.get('/api/thoughts?agent=nobody').json == []

    def test_thoughts_for_a_letta_agent_are_fetched(self, live, svc, stub):
        stub('letta_id_for', lambda a: 'agent-123')
        stub('cached_thoughts', lambda lid, conv='': [{'text': 'thinking'}])
        assert live.get('/api/thoughts?agent=Mazda').json == [{'text': 'thinking'}]

    def test_messages_for_claude_come_from_the_local_log(self, live, svc, stub):
        stub('_load_json', lambda path: [{'date': 'now', 'text': 'hi'}])
        stub('_within_max_age', lambda row, now: True)
        assert live.get('/api/messages?agent=agent-claude').json == [
            {'date': 'now', 'text': 'hi'}]

    def test_claude_messages_are_age_filtered(self, live, svc, stub):
        stub('_load_json', lambda path: [{'id': 1}, {'id': 2}, {'id': 3}])
        stub('_within_max_age', lambda row, now: row['id'] != 2)
        assert [r['id'] for r in live.get('/api/messages?agent=agent-claude').json] == [1, 3]

    def test_messages_for_an_unknown_agent_are_empty(self, live, svc, stub):
        stub('letta_id_for', lambda a: None)
        assert live.get('/api/messages?agent=ghost').json == []


# ==========================================================================
# Query-parameter handling
# ==========================================================================
class TestQueryParameters:
    def test_a_missing_agent_param_becomes_empty_string(self, live, svc, stub):
        seen = []
        stub('letta_id_for', lambda a: seen.append(a) or None)
        live.get('/api/messages')
        assert seen == ['']

    def test_percent_encoding_is_decoded(self, live, svc, stub):
        seen = []
        stub('letta_id_for', lambda a: seen.append(a) or None)
        live.get('/api/messages?agent=Mazda%20Trainer')
        assert seen == ['Mazda Trainer']

    def test_a_plus_is_decoded_as_a_space(self, live, svc, stub):
        seen = []
        stub('letta_id_for', lambda a: seen.append(a) or None)
        live.get('/api/messages?agent=a+b')
        assert seen == ['a b']

    def test_the_model_stats_source_is_passed_through(self, live, svc):
        live.get('/api/model-stats?source=claude')
        assert svc.args_for('model_stats') == ('claude',)

    def test_a_missing_source_is_an_empty_string_not_a_crash(self, live, svc):
        assert live.get('/api/model-stats').status == 200
        assert svc.args_for('model_stats') == ('',)


# ==========================================================================
# POST bodies — malformed input is the interesting case
# ==========================================================================
class TestPostBodyHandling:
    @pytest.mark.parametrize('path', [
        '/api/note-command-complete', '/api/receptionist-intent',
        '/api/letta-code-message', '/api/route-detect',
    ])
    def test_malformed_json_is_a_400_not_a_500(self, live, svc, path):
        resp = live.post(path, body='{not json')
        assert resp.status == 400
        assert 'error' in resp.json

    @pytest.mark.parametrize('path', [
        '/api/note-command-complete', '/api/receptionist-intent',
    ])
    def test_an_empty_body_is_a_400_not_a_500(self, live, svc, path):
        assert live.post(path, body='').status == 400

    def test_a_wrong_typed_field_is_refused_with_a_reason(self, live, svc):
        resp = live.post('/api/receptionist-intent', {'text': 12345})
        assert resp.status == 400
        assert 'text must be a string' in resp.json['error']

    def test_a_null_field_is_refused(self, live, svc):
        assert live.post('/api/note-command-complete', {'text': None}).status == 400

    def test_a_json_array_body_drops_only_that_connection(self, live, svc):
        """Known gap, pinned deliberately.

        Routes do `json.loads(body)` then `data.get(...)`, so a body that is
        valid JSON but not an object raises AttributeError and the connection
        is dropped. It is contained — ThreadingHTTPServer kills that thread
        only — but the honest fix is one shared body-parser, which belongs with
        the route-registry refactor rather than in 40 hand-edited routes.
        What must stay true meanwhile is that the *server* survives.
        """
        with pytest.raises(Exception):
            live.post('/api/note-command-complete', body='[1,2,3]')
        assert live.get('/api/code-status').status == 200

    def test_a_valid_body_reaches_the_service(self, live, svc):
        live.post('/api/receptionist-intent', {'text': 'hello there'})
        assert svc.called('build_receptionist_strategy')

    def test_a_large_body_is_read_completely(self, live, svc, stub):
        seen = []
        stub('record_stored_expense', lambda d: seen.append(d) or {'ok': True})
        big = 'x' * 200_000
        live.post('/api/expense-stored', {'note': big})
        assert seen and len(seen[0]['note']) == 200_000

    def test_a_utf8_body_survives(self, live, svc, stub):
        seen = []
        stub('record_stored_expense', lambda d: seen.append(d) or {'ok': True})
        live.post('/api/expense-stored', {'vendor': 'Café ⚠ Ñ'})
        assert seen[0]['vendor'] == 'Café ⚠ Ñ'


# ==========================================================================
# /api/server-action — the route that restarts real infrastructure
# ==========================================================================
class TestServerAction:
    def test_deploy_calls_deploy_and_nothing_else_destructive(self, live, svc):
        live.post('/api/server-action', {'action': 'deploy', 'server': 'dashboard'})
        assert svc.called('deploy_dashboard')
        assert not svc.called('restart_server')

    def test_deploy_without_the_dashboard_target_does_not_deploy(self, live, svc):
        """Both keys are required; 'action' alone must not trigger a deploy."""
        live.post('/api/server-action', {'action': 'deploy'})
        assert not svc.called('deploy_dashboard')

    def test_restart_targets_the_dashboard_unit(self, live, svc):
        live.post('/api/server-action', {'action': 'restart', 'server': 'dashboard'})
        assert svc.called('restart_dashboard_server')

    def test_an_unknown_action_does_not_restart_anything(self, live, svc):
        live.post('/api/server-action', {'action': 'not-a-real-action'})
        for destructive in ('deploy_dashboard', 'restart_dashboard_server',
                            'restart_server', 'start_executor_server'):
            assert not svc.called(destructive), f'{destructive} ran for an unknown action'

    def test_an_empty_action_does_nothing_destructive(self, live, svc):
        live.post('/api/server-action', {})
        for destructive in ('deploy_dashboard', 'restart_dashboard_server',
                            'restart_server'):
            assert not svc.called(destructive)

    @pytest.mark.parametrize('target,expected', [
        ('executor', 'start_executor_server'),
        ('logger-api', 'start_logger_api'),
        ('frita-executor', 'start_frita_executor'),
    ])
    def test_a_start_action_starts_only_the_named_server(self, live, svc, target, expected):
        live.post('/api/server-action', {'action': 'start', 'server': target})
        started = [n for n in svc.names() if n.startswith('start_')]
        assert started == [expected]


# ==========================================================================
# The Letta PATCH routes — the only ones that reach the network directly
# ==========================================================================
class TestAgentModelPatch:
    def test_a_successful_patch_reports_the_new_handle(self, live, svc, stub, monkeypatch):
        stub('letta_id_for', lambda a: 'agent-1')
        stub('agent_model_options', lambda handle: ['openai/gpt-5.5'])
        fake = FakeUrllib(payload={'llm_config': {'handle': 'openai/gpt-5.5'}})
        monkeypatch.setattr(post_routes, 'urllib', fake)
        resp = live.post('/api/agent-model', {'agent': 'Mazda', 'model': 'openai/gpt-5.5'})
        assert resp.json == {'ok': True, 'model': 'openai/gpt-5.5'}

    def test_the_patch_targets_the_resolved_letta_id(self, live, svc, stub, monkeypatch):
        stub('letta_id_for', lambda a: 'agent-xyz')
        stub('agent_model_options', lambda handle: ['openai/gpt-5.5'])
        fake = FakeUrllib(payload={'llm_config': {'handle': 'h'}})
        monkeypatch.setattr(post_routes, 'urllib', fake)
        live.post('/api/agent-model', {'agent': 'Mazda', 'model': 'openai/gpt-5.5'})
        assert fake.calls[-1]['url'].endswith('/v1/agents/agent-xyz')
        assert fake.calls[-1]['method'] == 'PATCH'

    def test_an_http_error_from_letta_becomes_a_clean_ok_false(self, live, svc, stub, monkeypatch):
        import urllib.error
        stub('letta_id_for', lambda a: 'agent-1')
        stub('agent_model_options', lambda handle: ['x/y'])
        boom = urllib.error.HTTPError('u', 502, 'Bad Gateway', {}, None)
        monkeypatch.setattr(post_routes, 'urllib', FakeUrllib(raises=boom))
        resp = live.post('/api/agent-model', {'agent': 'Mazda', 'model': 'x/y'})
        assert resp.status == 200
        assert resp.json['ok'] is False
        assert 'letta 502' in resp.json['error']

    def test_a_model_outside_the_allowlist_is_refused_before_any_network_call(
            self, live, svc, stub, monkeypatch):
        """Fails closed: an unlisted model must never reach Letta."""
        stub('letta_id_for', lambda a: 'agent-1')
        stub('agent_model_options', lambda handle: ['openai/gpt-5.5'])
        fake = FakeUrllib(payload={})
        monkeypatch.setattr(post_routes, 'urllib', fake)
        resp = live.post('/api/agent-model', {'agent': 'M', 'model': 'evil/backdoor'})
        assert resp.json['ok'] is False
        assert 'not in the allowed list' in resp.json['error']
        assert fake.calls == [], 'a rejected model still hit the Letta API'

    def test_a_connection_failure_does_not_take_the_server_down(self, live, svc, stub, monkeypatch):
        stub('letta_id_for', lambda a: 'agent-1')
        stub('agent_model_options', lambda handle: ['x/y'])
        monkeypatch.setattr(post_routes, 'urllib', FakeUrllib(raises=OSError('refused')))
        assert live.post('/api/agent-model', {'agent': 'M', 'model': 'x/y'}).status < 500
        assert live.get('/api/code-status').status == 200      # still serving


# ==========================================================================
# Static serving through the live handler
# ==========================================================================
class TestStaticServingLive:
    def test_the_dashboard_page_is_served(self, live, svc):
        resp = live.get('/dashboard.html')
        assert resp.status == 200
        assert resp.headers['Content-Type'] == 'text/html'

    def test_root_serves_the_dashboard(self, live, svc):
        assert live.get('/').status == 200

    def test_a_css_asset_is_served_with_the_right_type(self, live, svc):
        resp = live.get('/css/dashboard.css')
        if resp.status == 200:
            assert resp.headers['Content-Type'] == 'text/css'

    def test_a_missing_asset_is_404(self, live, svc):
        assert live.get('/definitely-not-here.css').status == 404

    def test_traversal_is_refused_over_the_wire(self, live, svc):
        """The regression test for the disclosure bug, end to end."""
        resp = live.request('GET', '/../../../../etc/passwd')
        assert resp.status == 404
        assert b'root:' not in resp.body

    def test_traversal_into_the_repo_is_refused(self, live, svc):
        resp = live.request('GET', '/../../../.ssh/id_rsa')
        assert resp.status == 404


# ==========================================================================
# Robustness of the server itself
# ==========================================================================
class TestServerRobustness:
    def test_a_route_that_raises_does_not_kill_the_server(self, live, svc, stub):
        def boom():
            raise RuntimeError('service exploded')
        stub('get_code_status', boom)
        with pytest.raises(Exception):
            live.get('/api/code-status')
        assert live.get('/api/pc-monitors').status == 200

    def test_concurrent_requests_are_served(self, live, svc):
        """ReusableHTTPServer is threaded so a slow request cannot block pollers."""
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = [f.result() for f in
                       [pool.submit(live.get, '/api/code-status') for _ in range(24)]]
        assert all(r.status == 200 for r in results)

    def test_an_abruptly_closed_connection_does_not_kill_the_server(self, live, svc):
        s = socket.create_connection(('127.0.0.1', live.port), timeout=5)
        s.sendall(b'GET /api/code-status HTTP/1.0\r\n')
        s.close()
        assert live.get('/api/code-status').status == 200

    def test_a_garbage_request_line_does_not_kill_the_server(self, live, svc):
        s = socket.create_connection(('127.0.0.1', live.port), timeout=5)
        s.sendall(b'\x00\x01\x02 not-http\r\n\r\n')
        s.close()
        assert live.get('/api/code-status').status == 200

    def test_an_unsupported_method_is_rejected_cleanly(self, live, svc):
        assert live.request('DELETE', '/api/agents').status in (404, 501)

    def test_head_does_not_leak_a_body(self, live, svc):
        resp = live.request('HEAD', '/dashboard.html')
        assert resp.body == b''
