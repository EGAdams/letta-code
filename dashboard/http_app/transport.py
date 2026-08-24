"""HTTP response primitives for the dashboard handler (transport seam).

Everything here is about *how* a response leaves the socket — status line,
headers, body encoding — and nothing about *what* the dashboard means. The
route mixins own meaning; this mixin owns the wire.
"""
import json

from .models import NO_CACHE_HEADERS, ErrorResponse, StaticAsset


class HttpTransportMixin:
    """Response helpers shared by every route mixin.

    Mixed into DashboardHandler, so `self` is a BaseHTTPRequestHandler.
    """

    def _read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        return self.rfile.read(length).decode('utf-8')

    def _send_no_cache_headers(self):
        for name, value in NO_CACHE_HEADERS:
            self.send_header(name, value)

    def _write(self, body, content_type, code=200, extra_headers=()):
        """Single place that puts bytes on the wire. Everything below funnels here."""
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', len(body))
        for name, value in extra_headers:
            self.send_header(name, value)
        self._send_no_cache_headers()
        self.end_headers()
        self.wfile.write(body)

    def serve_file(self, file_path, content_type=None):
        asset = StaticAsset.resolve(file_path, content_type)
        try:
            with open(asset.path, 'rb') as f:
                content = f.read()
        except FileNotFoundError:
            return self.send_error(404)
        self._write(content, asset.content_type)

    def json_response(self, data):
        body = json.dumps(data, indent=2).encode('utf-8')
        self._write(body, 'application/json',
                    extra_headers=(('Access-Control-Allow-Origin', '*'),))

    def error_response(self, message, code=400):
        body = ErrorResponse(error=message).model_dump_json().encode('utf-8')
        self._write(body, 'application/json', code=code)

    def log_message(self, fmt, *args):
        print(f'[{self.log_date_time_string()}] {fmt % args}')
