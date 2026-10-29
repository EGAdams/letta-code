"""Exercise the embedded documentation through real HTTP on both sides."""
import http.server
import threading

import pytest

from http_app.documentation_proxy import LoopbackDocumentationUpstream
from http_app.handler import DashboardHandler
from tests.http_app_harness import DashboardClient, start_server


@pytest.fixture
def gateway(monkeypatch):
    requests = []

    class Upstream(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(('GET', self.path, None))
            self.send_response(404 if self.path == '/missing.js' else 200)
            self.send_header('Content-Type', 'application/javascript' if '.js' in self.path else 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(b'export const documentation = true;' if '.js' in self.path else b'<h1>Agent Blocks</h1>')

        def do_POST(self):
            body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
            requests.append(('POST', self.path, body))
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"ok":true}')

        def log_message(self, *_):
            pass

    upstream = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Upstream)
    threading.Thread(target=upstream.serve_forever, daemon=True).start()
    monkeypatch.setattr(DashboardHandler, 'documentation_upstream',
                        LoopbackDocumentationUpstream(f'http://127.0.0.1:{upstream.server_port}'))
    httpd, _, port = start_server()
    yield DashboardClient(port), requests
    httpd.shutdown()
    httpd.server_close()
    upstream.shutdown()
    upstream.server_close()


def test_embedded_page_preserves_query_and_is_not_cached(gateway):
    client, requests = gateway
    result = client.get('/agent-block/?embedded=1')
    assert result.status == 200 and b'Agent Blocks' in result.body
    assert requests == [('GET', '/?embedded=1', None)]
    assert 'no-store' in result.headers['Cache-Control']


def test_imported_javascript_has_the_right_type(gateway):
    client, _ = gateway
    result = client.get('/agent-block/app/core/client.js')
    assert result.status == 200
    assert result.headers['Content-Type'] == 'application/javascript'


def test_documentation_api_post_is_forwarded(gateway):
    client, requests = gateway
    result = client.post('/agent-block/api/run-update', body=b'{"item":"example"}')
    assert result.status == 200 and result.json['ok']
    assert requests == [('POST', '/api/run-update', b'{"item":"example"}')]


def test_missing_assets_keep_the_upstream_404(gateway):
    client, _ = gateway
    assert client.get('/agent-block/missing.js').status == 404


def test_bare_prefix_redirects_to_preserve_relative_urls(gateway):
    client, requests = gateway
    result = client.get('/agent-block?embedded=1')
    assert result.status == 307
    assert result.headers['Location'] == '/agent-block/?embedded=1'
    assert requests == []


def test_an_unavailable_upstream_is_a_clear_503(gateway, monkeypatch):
    client, _ = gateway

    class Offline:
        def fetch(self, *_):
            raise OSError('offline')

    monkeypatch.setattr(DashboardHandler, 'documentation_upstream', Offline())
    result = client.get('/agent-block/')
    assert result.status == 503 and 'unavailable' in result.json['error']


def test_similar_names_do_not_reach_the_documentation_service(gateway):
    client, requests = gateway
    assert client.get('/agent-block-secret').status == 404
    assert requests == []
