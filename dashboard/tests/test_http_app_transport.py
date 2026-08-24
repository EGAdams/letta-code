"""Transport seam: how bytes actually leave the socket.

Every response in the dashboard funnels through HttpTransportMixin._write, so a
mistake here is a mistake on all 95 routes at once. These tests drive the mixin
against a fake socket rather than a live server, so they can assert on the exact
status line, header set and body bytes.
"""
import io
import json

import pytest

from http_app.models import DEFAULT_CONTENT_TYPE, NO_CACHE_HEADERS
from http_app.transport import HttpTransportMixin


class FakeTransport(HttpTransportMixin):
    """A mixin host that records the response instead of writing to a socket."""

    def __init__(self, body=b'', headers=None):
        self.rfile = io.BytesIO(body)
        self.wfile = io.BytesIO()
        self.headers = headers or {}
        self.status = None
        self.sent_headers = []
        self.ended = False
        self.errors = []

    def send_response(self, code):
        self.status = code

    def send_header(self, name, value):
        self.sent_headers.append((name, value))

    def end_headers(self):
        self.ended = True

    def send_error(self, code):
        self.errors.append(code)

    def log_date_time_string(self):
        return 'FIXED/TIME'

    # -- assertions helpers ------------------------------------------------
    @property
    def header_map(self):
        return {k: v for k, v in self.sent_headers}

    @property
    def body(self):
        return self.wfile.getvalue()

    @property
    def json_body(self):
        return json.loads(self.body.decode('utf-8'))


@pytest.fixture
def t():
    return FakeTransport()


# --------------------------------------------------------------------------
class TestReadBody:
    def test_reads_exactly_content_length(self):
        h = FakeTransport(b'{"a":1}extra', {'Content-Length': '7'})
        assert h._read_body() == '{"a":1}'

    def test_missing_content_length_reads_nothing(self):
        assert FakeTransport(b'ignored')._read_body() == ''

    def test_zero_length_reads_nothing(self):
        assert FakeTransport(b'ignored', {'Content-Length': '0'})._read_body() == ''

    def test_utf8_body_is_decoded(self):
        raw = 'café ≥ 2 ⚠'.encode('utf-8')
        h = FakeTransport(raw, {'Content-Length': str(len(raw))})
        assert h._read_body() == 'café ≥ 2 ⚠'

    def test_a_short_body_does_not_hang_or_pad(self):
        h = FakeTransport(b'ab', {'Content-Length': '999'})
        assert h._read_body() == 'ab'

    def test_a_non_numeric_content_length_raises_rather_than_guessing(self):
        with pytest.raises(ValueError):
            FakeTransport(b'x', {'Content-Length': 'banana'})._read_body()


# --------------------------------------------------------------------------
class TestNoCacheHeaders:
    def test_json_responses_are_uncacheable(self, t):
        t.json_response({'ok': True})
        for name, value in NO_CACHE_HEADERS:
            assert t.header_map[name] == value

    def test_error_responses_are_uncacheable(self, t):
        t.error_response('nope')
        for name, value in NO_CACHE_HEADERS:
            assert t.header_map[name] == value

    def test_static_files_are_uncacheable(self, t, tmp_path):
        f = tmp_path / 'a.js'
        f.write_text('x')
        t.serve_file(str(f))
        for name, value in NO_CACHE_HEADERS:
            assert t.header_map[name] == value


# --------------------------------------------------------------------------
class TestJsonResponse:
    def test_status_content_type_and_body(self, t):
        t.json_response({'ok': True, 'n': 3})
        assert t.status == 200
        assert t.header_map['Content-Type'] == 'application/json'
        assert t.json_body == {'ok': True, 'n': 3}

    def test_content_length_matches_the_body_exactly(self, t):
        t.json_response({'text': 'héllo ⚠'})
        assert int(t.header_map['Content-Length']) == len(t.body)

    def test_cors_header_is_present(self, t):
        t.json_response({})
        assert t.header_map['Access-Control-Allow-Origin'] == '*'

    def test_headers_are_ended_before_the_body(self, t):
        t.json_response({})
        assert t.ended is True

    @pytest.mark.parametrize('payload', [
        {}, [], None, 0, False, '', [[]], {'a': None},
        {'nested': {'deep': [1, 2, {'x': None}]}},
    ])
    def test_falsy_and_nested_payloads_still_serialise(self, payload):
        h = FakeTransport()
        h.json_response(payload)
        assert h.json_body == payload
        assert h.status == 200

    def test_a_bare_array_stays_a_bare_array(self, t):
        """/api/agents is contractually a bare array — never wrapped."""
        t.json_response([{'name': 'Mazda'}])
        assert isinstance(t.json_body, list)

    def test_non_ascii_survives_the_round_trip(self, t):
        t.json_response({'label': 'Rosemary ≥ 46 — ⚠'})
        assert t.json_body['label'] == 'Rosemary ≥ 46 — ⚠'

    def test_non_serialisable_payload_raises_rather_than_sending_a_half_response(self, t):
        with pytest.raises(TypeError):
            t.json_response({'when': object()})
        assert t.body == b''


# --------------------------------------------------------------------------
class TestErrorResponse:
    def test_defaults_to_400(self, t):
        t.error_response('bad input')
        assert t.status == 400
        assert t.json_body == {'error': 'bad input'}

    @pytest.mark.parametrize('code', [400, 404, 500, 502, 504])
    def test_explicit_codes_are_used(self, code):
        h = FakeTransport()
        h.error_response('x', code)
        assert h.status == code

    def test_content_type_is_json_so_the_frontend_can_parse_it(self, t):
        t.error_response('x', 500)
        assert t.header_map['Content-Type'] == 'application/json'

    def test_content_length_matches(self, t):
        t.error_response('a longer ⚠ message')
        assert int(t.header_map['Content-Length']) == len(t.body)

    def test_no_cors_header_on_errors(self, t):
        """Errors deliberately do not advertise cross-origin access."""
        t.error_response('x')
        assert 'Access-Control-Allow-Origin' not in t.header_map

    def test_message_is_not_html_escaped_or_truncated(self, t):
        msg = "can't parse <tag> & \"quotes\" — 100%"
        t.error_response(msg)
        assert t.json_body['error'] == msg

    @pytest.mark.parametrize('message,expected', [
        (404, '404'),
        (ValueError('boom'), 'boom'),
        (None, 'None'),
        (['a', 'b'], "['a', 'b']"),
    ])
    def test_a_non_string_message_is_coerced_not_raised(self, message, expected):
        """The error path must never fail *inside* the error path.

        Every caller passes str(e) today, but a route added during the route-
        registry refactor that passes the exception itself should still produce
        a clean 400 rather than a ValidationError from the handler.
        """
        h = FakeTransport()
        h.error_response(message)
        assert h.status == 400
        assert h.json_body['error'] == expected


# --------------------------------------------------------------------------
class TestServeFile:
    def test_serves_bytes_with_the_resolved_content_type(self, t, tmp_path):
        f = tmp_path / 'dashboard.html'
        f.write_bytes(b'<html>hi</html>')
        t.serve_file(str(f))
        assert t.status == 200
        assert t.header_map['Content-Type'] == 'text/html'
        assert t.body == b'<html>hi</html>'

    def test_an_explicit_content_type_wins(self, t, tmp_path):
        f = tmp_path / 'report.html'
        f.write_bytes(b'x')
        t.serve_file(str(f), 'text/plain')
        assert t.header_map['Content-Type'] == 'text/plain'

    def test_unknown_extension_falls_back_to_octet_stream(self, t, tmp_path):
        f = tmp_path / 'thing.weird'
        f.write_bytes(b'x')
        t.serve_file(str(f))
        assert t.header_map['Content-Type'] == DEFAULT_CONTENT_TYPE

    def test_a_missing_file_is_a_404_with_no_body(self, t, tmp_path):
        t.serve_file(str(tmp_path / 'nope.html'))
        assert t.errors == [404]
        assert t.status is None
        assert t.body == b''

    def test_an_empty_file_is_a_200_with_zero_length(self, t, tmp_path):
        f = tmp_path / 'empty.css'
        f.write_bytes(b'')
        t.serve_file(str(f))
        assert t.status == 200
        assert t.header_map['Content-Length'] == 0
        assert t.body == b''

    def test_binary_content_is_not_mangled(self, t, tmp_path):
        blob = bytes(range(256)) * 8
        f = tmp_path / 'scan.png'
        f.write_bytes(blob)
        t.serve_file(str(f))
        assert t.body == blob
        assert t.header_map['Content-Type'] == 'image/png'

    def test_content_length_matches_binary_length(self, t, tmp_path):
        blob = bytes(range(256))
        f = tmp_path / 'x.pdf'
        f.write_bytes(blob)
        t.serve_file(str(f))
        assert t.header_map['Content-Length'] == len(blob) == 256

    def test_a_directory_is_not_served_as_a_file(self, t, tmp_path):
        """IsADirectoryError must not escape as a 500 with a half-written body."""
        with pytest.raises(IsADirectoryError):
            t.serve_file(str(tmp_path))
        assert t.body == b''


# --------------------------------------------------------------------------
class TestLogMessage:
    def test_prefixes_with_the_request_timestamp(self, t, capsys):
        t.log_message('%s %s', 'GET', '/api/agents')
        assert capsys.readouterr().out.strip() == '[FIXED/TIME] GET /api/agents'

    def test_a_literal_percent_in_the_format_is_handled(self, t, capsys):
        t.log_message('%s done', '100%')
        assert '100% done' in capsys.readouterr().out


# --------------------------------------------------------------------------
class TestWriteFunnel:
    """_write is the single choke point; assert the ordering contract."""

    def test_status_headers_then_body(self, t):
        t._write(b'hi', 'text/plain')
        assert (t.status, t.ended, t.body) == (200, True, b'hi')

    def test_extra_headers_are_included(self, t):
        t._write(b'', 'text/plain', extra_headers=(('X-A', '1'), ('X-B', '2')))
        assert t.header_map['X-A'] == '1' and t.header_map['X-B'] == '2'

    def test_no_cache_headers_are_always_appended(self, t):
        t._write(b'', 'text/plain')
        assert 'Cache-Control' in t.header_map

    def test_content_length_is_always_set(self, t):
        t._write(b'abcd', 'text/plain')
        assert t.header_map['Content-Length'] == 4
