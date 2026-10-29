"""Serve Agent Blocks through the dashboard, without a Tailscale-only route.

The upstream is fixed at construction, so a request cannot choose a host.
The gateway forwards the documentation API as well as its page and assets.
"""
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .documentation_proxy_models import DocumentationResponse, DocumentationUpstream

PREFIX = '/agent-block'


class LoopbackDocumentationUpstream:
    def __init__(self, origin: str = 'http://127.0.0.1:8931') -> None:
        self._origin = origin.rstrip('/')

    def fetch(self, method: str, target: str, body: bytes | None,
              content_type: str) -> DocumentationResponse:
        request = Request(self._origin + target, data=body, method=method,
                          headers={'Content-Type': content_type})
        try:
            response = urlopen(request, timeout=15)
        except HTTPError as exc:
            response = exc
        with response:
            return DocumentationResponse(status=response.status, body=response.read(),
                                         content_type=response.headers.get('Content-Type', 'application/octet-stream'))


class DocumentationProxyMixin:
    documentation_upstream: DocumentationUpstream

    def do_GET(self):
        if self._is_documentation():
            return self._proxy_documentation('GET')
        return super().do_GET()

    def do_POST(self):
        if self._is_documentation():
            return self._proxy_documentation('POST')
        return super().do_POST()

    def _is_documentation(self) -> bool:
        path = urlsplit(self.path).path
        return path == PREFIX or path.startswith(PREFIX + '/')

    def _proxy_documentation(self, method: str) -> None:
        parsed = urlsplit(self.path)
        if parsed.path == PREFIX:
            # The trailing slash is required for the SPA's relative imports.
            location = PREFIX + '/' + ('?' + parsed.query if parsed.query else '')
            self._write(b'', 'text/plain', code=307,
                        extra_headers=(('Location', location),))
            return
        target = parsed.path[len(PREFIX):]
        if parsed.query:
            target += '?' + parsed.query
        body = None
        if method == 'POST':
            try:
                length = int(self.headers.get('Content-Length', '0'))
            except ValueError:
                return self.error_response('Invalid Content-Length', 400)
            if not 0 <= length <= 1024 * 1024:
                return self.error_response('Documentation request too large', 413)
            body = self.rfile.read(length)
        try:
            response = self.documentation_upstream.fetch(
                method, target, body, self.headers.get('Content-Type', 'application/json'))
        except (OSError, URLError, TimeoutError):
            return self.error_response('Agent Blocks documentation server is unavailable', 503)
        self._write(response.body, response.content_type, code=response.status)
