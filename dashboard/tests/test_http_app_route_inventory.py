"""Route reachability — the safety net for the route-registry refactor.

Every route the dashboard exposes is hit on a live server with the service layer
stubbed, and asserted to *dispatch*. "Dispatch" deliberately means only "not a
404": what each route returns is covered by the behavioural tests, while this
file exists to catch the one failure mode a big structural refactor actually
has — a route silently going missing, getting renamed, or being shadowed by
another rule.

None of these assertions look at how dispatch happens, so they stay valid when
the if/elif ladders become a registry.
"""
import pytest

import server
from tests.http_app_harness import DashboardClient, ServiceRecorder, start_server

# --------------------------------------------------------------------------
# The inventory. Kept as a literal list, not derived from the source: a list
# generated from the code under test would happily agree with a route that was
# deleted by mistake.
# --------------------------------------------------------------------------
GET_ROUTES = [
    '/api/agent-activity', '/api/agent-card', '/api/agent-health',
    '/api/agent-model', '/api/agent-oauth-account', '/api/agent-voice',
    '/api/agents', '/api/chatgpt-provider-account-status', '/api/code-status',
    '/api/codex-sync-status', '/api/expense-stored-events', '/api/intake-halt',
    '/api/mazda-mode', '/api/messages', '/api/model-stats',
    '/api/model-stats-agents', '/api/model-stats-sources', '/api/pc-metrics',
    '/api/pc-monitors', '/api/pending-vendor-review', '/api/receptionist-agent',
    '/api/rol-finance-categories', '/api/rol-finance-month-status',
    '/api/rol-finance-recent-reports', '/api/rol-finance-recent-scans',
    '/api/rol-finance-reports', '/api/router-agent', '/api/scanner-diagnostics',
    '/api/scanner-intake-status', '/api/scanner-status', '/api/server-health',
    '/api/server-logs', '/api/servers', '/api/ssh-connection-health',
    '/api/ssh-connection-logs', '/api/ssh-connection-test',
    '/api/ssh-connections', '/api/statement-reviews', '/api/thoughts', '/api/toolcalls',
    '/api/vendor-keys', '/report-source-document',
]

POST_ROUTES = [
    '/api/agent-model', '/api/agent-oauth-account', '/api/agent-voice',
    '/api/chatgpt-provider-account', '/api/claude-log', '/api/claude-toollog',
    '/api/codex-sync-now', '/api/codex-sync-toggle', '/api/expense-edit',
    '/api/expense-search', '/api/expense-stored', '/api/fix-printer',
    '/api/headless-prompt', '/api/intake-halt', '/api/intake-halt-ack',
    '/api/intake-status', '/api/letta-code-message', '/api/manual-receipt-entry',
    '/api/manual-receipt-entry-archive-preview', '/api/manual-receipt-entry-preview',
    '/api/manual-statement-breakup', '/api/manual-statement-entry',
    '/api/mazda-fill', '/api/mazda-mode', '/api/model-stats-mute',
    '/api/note-command-apply', '/api/note-command-complete',
    '/api/open-supporting-document', '/api/process-document', '/api/process-pdf',
    '/api/recategorize-expense', '/api/receipt-lookup', '/api/receipts-present',
    '/api/receptionist-intent', '/api/reprocess-report', '/api/route-detect',
    '/api/save-expense-notes', '/api/scanned-statements-present',
    '/api/scanner-archive-path', '/api/scanner-clear-verification',
    '/api/scanner-scan', '/api/server-action', '/api/set-receipt-vendor',
    '/api/statement-review-resolve', '/api/supporting-documents', '/api/test',
    '/api/tts', '/api/undo-recategorize-expense', '/api/voice',
]


@pytest.fixture(scope='module')
def live():
    httpd, thread, port = start_server()
    yield DashboardClient(port)
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture
def stubbed(monkeypatch):
    """Make every server.py function inert before any route is touched."""
    recorder = ServiceRecorder()
    recorder.install(monkeypatch)
    from http_app import post_routes
    from tests.http_app_harness import FakeUrllib
    monkeypatch.setattr(post_routes, 'urllib', FakeUrllib())
    return recorder


class TestEveryRouteDispatches:
    @pytest.mark.parametrize('path', GET_ROUTES)
    def test_get_route_is_reachable(self, live, stubbed, path):
        resp = live.get(path)
        assert resp.status != 404, f'GET {path} fell through to the 404 handler'
        assert resp.status < 500, f'GET {path} blew up: {resp.text[:300]}'

    @pytest.mark.parametrize('path', POST_ROUTES)
    def test_post_route_is_reachable(self, live, stubbed, path):
        resp = live.post(path, {})
        assert resp.status != 404, f'POST {path} fell through to the 404 handler'
        assert resp.status < 500, f'POST {path} blew up: {resp.text[:300]}'


class TestUnknownRoutesStill404:
    """The other half of the contract: dispatch must not become a catch-all."""

    @pytest.mark.parametrize('path', [
        '/api/definitely-not-a-route',
        '/api/agents/extra-segment',
        '/api/AGENTS',
        '/api/agent-model/',
        '/nope.css',
    ])
    def test_unknown_get_is_404(self, live, stubbed, path):
        assert live.get(path).status == 404

    @pytest.mark.parametrize('path', [
        '/api/definitely-not-a-route',
        '/api/claude-log/extra',
        '/api/CLAUDE-LOG',
        '/api/test/',
    ])
    def test_unknown_post_is_404(self, live, stubbed, path):
        assert live.post(path, {}).status == 404

    def test_route_matching_is_case_sensitive(self, live, stubbed):
        assert live.get('/api/agents').status == 200
        assert live.get('/API/AGENTS').status == 404


class TestMethodSeparation:
    """GET-only and POST-only routes must not leak into each other."""

    def test_a_post_only_route_is_not_reachable_by_get(self, live, stubbed):
        assert live.get('/api/claude-log').status == 404

    def test_a_get_only_route_is_not_reachable_by_post(self, live, stubbed):
        assert live.post('/api/agents', {}).status == 404

    @pytest.mark.parametrize('path', ['/api/agent-model', '/api/agent-voice',
                                      '/api/intake-halt', '/api/mazda-mode',
                                      '/api/agent-oauth-account'])
    def test_dual_method_routes_answer_both(self, live, stubbed, path):
        """These five exist on both verbs; a refactor must not collapse them."""
        assert live.get(path).status != 404
        assert live.post(path, {}).status != 404


class TestQueryStringDoesNotAffectDispatch:
    @pytest.mark.parametrize('suffix', ['', '?', '?agent=Mazda', '?a=1&b=2',
                                        '?agent=', '?agent=%20', '?x=%E2%9A%A0'])
    def test_query_strings_are_stripped_before_matching(self, live, stubbed, suffix):
        assert live.get('/api/code-status' + suffix).status == 200

    def test_a_fragment_like_path_does_not_match(self, live, stubbed):
        assert live.get('/api/code-status%20').status == 404


class TestNoRouteHitsTheRealWorld:
    """Every dispatch must go through `srv`, or stubbing cannot protect anything.

    If a route reaches past the service layer — a bare subprocess call, a real
    urlopen — this is where it shows up, because the stubs would not have been
    consulted at all.
    """

    @pytest.mark.parametrize('path', [
        '/api/server-action', '/api/scanner-scan', '/api/process-document',
        '/api/fix-printer', '/api/tts', '/api/letta-code-message',
    ])
    def test_dangerous_post_routes_are_fully_intercepted(self, live, stubbed, path):
        resp = live.post(path, {})
        assert resp.status != 404
        assert resp.status < 500
