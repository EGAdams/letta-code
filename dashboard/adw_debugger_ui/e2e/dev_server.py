#!/usr/bin/env python3
"""Test host for the ADW debugger: the real feed and the real bundle, nothing else.

    ADW_DEBUGGER_STALL_SECONDS=4 python3 e2e/dev_server.py 8795

Serves e2e/host.html (the Terminal tab's markup, cut down), the built bundle
from ../js/adw-debugger/, and GET /api/adw-debugger/feed through the same
`adw_debugger.feed.payload` the dashboard route calls. It exists so the browser
tests can run without restarting, or loading the rest of, the live dashboard.
"""
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
DASHBOARD = HERE.parent.parent
sys.path.insert(0, str(DASHBOARD))

from adw_debugger import feed  # noqa: E402

STATIC = {'/': (HERE / 'host.html', 'text/html'),
          '/js/adw-debugger/adw-debugger.js': (DASHBOARD / 'js/adw-debugger/adw-debugger.js', 'text/javascript'),
          '/js/adw-debugger/adw-debugger.css': (DASHBOARD / 'js/adw-debugger/adw-debugger.css', 'text/css')}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlparse(self.path)
        if url.path == '/api/adw-debugger/feed':
            return self._send(json.dumps(feed.payload(parse_qs(url.query))).encode(), 'application/json')
        if url.path in STATIC:
            path, kind = STATIC[url.path]
            return self._send(path.read_bytes(), kind)
        self.send_error(404)

    def _send(self, body, kind):
        self.send_response(200)
        self.send_header('Content-Type', f'{kind}; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8795
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()
