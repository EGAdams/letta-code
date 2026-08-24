"""Edge-case coverage for the HTTP layer's Pydantic shapes.

These models replaced hand-rolled `int()` / `max(min())` parsing that used to
sit inline in the handler, so the point of these tests is the *nasty* input: a
browser that sends "abc" for a column count, a query string with the key
present but empty, a resize frame with a missing field. Every one of those used
to be a live crash risk on the terminal socket.
"""
import pytest
from pydantic import ValidationError

from http_app.models import (
    DEFAULT_COLS,
    DEFAULT_CONTENT_TYPE,
    DEFAULT_ROWS,
    MAX_COLS,
    MAX_ROWS,
    MIN_COLS,
    MIN_ROWS,
    NO_CACHE_HEADERS,
    BackgroundTask,
    ErrorResponse,
    ServerConfig,
    StaticAsset,
    TerminalGeometry,
    TerminalResizeFrame,
    TerminalSessionRequest,
)


# --------------------------------------------------------------------------
# TerminalGeometry — clamping
# --------------------------------------------------------------------------
class TestTerminalGeometry:
    def test_defaults_are_a_usable_terminal(self):
        g = TerminalGeometry()
        assert (g.cols, g.rows) == (DEFAULT_COLS, DEFAULT_ROWS)

    @pytest.mark.parametrize('cols,expected', [
        (0, MIN_COLS), (-1, MIN_COLS), (-99999, MIN_COLS),
        (MIN_COLS - 1, MIN_COLS), (MIN_COLS, MIN_COLS),
        (100, 100),
        (MAX_COLS, MAX_COLS), (MAX_COLS + 1, MAX_COLS), (10 ** 9, MAX_COLS),
    ])
    def test_cols_clamp_to_the_pty_range(self, cols, expected):
        assert TerminalGeometry(cols=cols).cols == expected

    @pytest.mark.parametrize('rows,expected', [
        (0, MIN_ROWS), (-1, MIN_ROWS), (MIN_ROWS - 1, MIN_ROWS),
        (MIN_ROWS, MIN_ROWS), (24, 24),
        (MAX_ROWS, MAX_ROWS), (MAX_ROWS + 1, MAX_ROWS), (10 ** 9, MAX_ROWS),
    ])
    def test_rows_clamp_to_the_pty_range(self, rows, expected):
        assert TerminalGeometry(rows=rows).rows == expected

    def test_clamping_is_idempotent(self):
        once = TerminalGeometry(cols=10 ** 6, rows=10 ** 6)
        twice = TerminalGeometry(cols=once.cols, rows=once.rows)
        assert (once.cols, once.rows) == (twice.cols, twice.rows)

    def test_bool_is_coerced_but_still_lands_in_range(self):
        # Pydantic's lax mode turns True into 1; the clamp is what saves the pty.
        assert TerminalGeometry(cols=True).cols == MIN_COLS

    def test_non_numeric_is_rejected_not_coerced(self):
        with pytest.raises(ValidationError):
            TerminalGeometry(cols='wide')

    def test_numeric_string_is_accepted_and_clamped(self):
        assert TerminalGeometry(cols='999').cols == MAX_COLS

    def test_float_with_fraction_is_rejected(self):
        with pytest.raises(ValidationError):
            TerminalGeometry(rows=24.5)


# --------------------------------------------------------------------------
# TerminalSessionRequest — the ?cols=&rows=&agent= query string
# --------------------------------------------------------------------------
class TestTerminalSessionRequest:
    def test_reads_a_well_formed_query(self):
        r = TerminalSessionRequest.from_query(
            {'agent': ['Mazda'], 'cols': ['120'], 'rows': ['40']})
        assert (r.agent, r.cols, r.rows) == ('Mazda', 120, 40)

    def test_missing_query_is_all_defaults(self):
        r = TerminalSessionRequest.from_query({})
        assert (r.agent, r.cols, r.rows) == ('', DEFAULT_COLS, DEFAULT_ROWS)

    def test_out_of_range_geometry_is_clamped_not_rejected(self):
        r = TerminalSessionRequest.from_query({'cols': ['99999'], 'rows': ['0']})
        assert (r.cols, r.rows) == (MAX_COLS, MIN_ROWS)

    @pytest.mark.parametrize('query', [
        {'cols': ['abc']},
        {'rows': ['']},
        {'cols': ['12.5']},
        {'cols': ['0x50']},
        {'rows': ['nan']},
        {'cols': ['  ']},
        {'cols': ['80; rm -rf /']},
    ])
    def test_garbled_geometry_falls_back_to_80x24(self, query):
        """Fails *soft*: a bad size is cosmetic, so never refuse the session."""
        r = TerminalSessionRequest.from_query(query)
        assert (r.cols, r.rows) == (DEFAULT_COLS, DEFAULT_ROWS)

    def test_unicode_digits_are_parsed_then_clamped_not_defaulted(self):
        """Python's int() accepts Arabic-Indic digits where Pydantic would not.

        from_query calls int() first, so '١٢٣...' becomes a real (huge) number
        and reaches the clamp rather than the except branch. Pinned because it
        is the one input where the two layers disagree, and the only thing
        keeping it safe is that the clamp runs last.
        """
        r = TerminalSessionRequest.from_query({'cols': ['١٢٣٤٥٦٧٨٩٠' * 3]})
        assert r.cols == MAX_COLS

    @pytest.mark.parametrize('raw', [
        'abc', '', '  ', '12.5', '0x50', 'nan', 'inf', '-inf', '1e9',
        '٠', '١٢٣٤٥٦٧٨٩٠' * 3, '9' * 400, '-' + '9' * 400, '80\x00', '٣', 'Ⅻ',
        '+80', '-80', '08', ' 80 ', '80\n', 'true', 'null', '[]', '{}',
    ])
    def test_no_hostile_geometry_ever_escapes_the_pty_range(self, raw):
        """The invariant that actually matters: whatever the browser sends, the
        numbers handed to TIOCSWINSZ are inside the range a pty accepts."""
        r = TerminalSessionRequest.from_query({'cols': [raw], 'rows': [raw]})
        assert MIN_COLS <= r.cols <= MAX_COLS
        assert MIN_ROWS <= r.rows <= MAX_ROWS

    def test_garbled_geometry_still_keeps_the_agent(self):
        r = TerminalSessionRequest.from_query({'agent': ['Suzuki'], 'cols': ['abc']})
        assert r.agent == 'Suzuki'
        assert (r.cols, r.rows) == (DEFAULT_COLS, DEFAULT_ROWS)

    @pytest.mark.parametrize('query', [
        {'cols': []},
        {'cols': ['']},
        {'agent': []},
    ])
    def test_present_but_empty_query_keys_use_defaults(self, query):
        """parse_qs can hand back an empty list or an empty string; both are 'absent'."""
        r = TerminalSessionRequest.from_query(query)
        assert (r.cols, r.rows) == (DEFAULT_COLS, DEFAULT_ROWS)

    def test_only_the_first_repeated_value_is_used(self):
        r = TerminalSessionRequest.from_query({'cols': ['100', '200']})
        assert r.cols == 100

    def test_agent_is_carried_verbatim_for_the_caller_to_validate(self):
        # The mixin, not the model, is what guards the exec: the model must not
        # quietly "clean" a hostile id into something that looks safe.
        hostile = 'agent-1; rm -rf /'
        assert TerminalSessionRequest.from_query({'agent': [hostile]}).agent == hostile

    def test_is_a_geometry(self):
        assert isinstance(TerminalSessionRequest.from_query({}), TerminalGeometry)


# --------------------------------------------------------------------------
# TerminalResizeFrame — the {"t":"r","c":..,"r":..} browser frame
# --------------------------------------------------------------------------
class TestTerminalResizeFrame:
    def test_reads_a_well_formed_frame(self):
        size = TerminalResizeFrame.from_frame(
            {'c': 120, 'r': 40}, TerminalGeometry())
        assert (size.cols, size.rows) == (120, 40)

    def test_missing_fields_fall_back_to_the_session_geometry(self):
        session = TerminalGeometry(cols=132, rows=43)
        assert TerminalResizeFrame.from_frame({}, session).cols == 132
        assert TerminalResizeFrame.from_frame({'c': 90}, session).rows == 43

    def test_frame_values_are_clamped(self):
        size = TerminalResizeFrame.from_frame({'c': 10 ** 9, 'r': -5}, TerminalGeometry())
        assert (size.cols, size.rows) == (MAX_COLS, MIN_ROWS)

    @pytest.mark.parametrize('frame', [
        {'c': 'wide'}, {'r': None}, {'c': [], 'r': {}}, {'c': 'ＮａＮ'},
    ])
    def test_a_junk_frame_returns_the_previous_geometry_unchanged(self, frame):
        """A bad resize must not resize *and* must not kill the socket."""
        session = TerminalGeometry(cols=111, rows=33)
        size = TerminalResizeFrame.from_frame(frame, session)
        assert (size.cols, size.rows) == (111, 33)

    def test_a_junk_frame_returns_the_fallback_object_itself(self):
        session = TerminalGeometry(cols=111, rows=33)
        assert TerminalResizeFrame.from_frame({'c': 'x'}, session) is session

    def test_numeric_strings_from_json_are_accepted(self):
        size = TerminalResizeFrame.from_frame({'c': '100', 'r': '30'}, TerminalGeometry())
        assert (size.cols, size.rows) == (100, 30)


# --------------------------------------------------------------------------
# StaticAsset — content-type resolution
# --------------------------------------------------------------------------
class TestStaticAsset:
    @pytest.mark.parametrize('path,expected', [
        ('/x/dashboard.html', 'text/html'),
        ('/x/boot.js', 'application/javascript'),
        ('/x/dashboard.css', 'text/css'),
        ('/x/recent_report.json', 'application/json'),
        ('/x/scan.jpg', 'image/jpeg'),
        ('/x/scan.jpeg', 'image/jpeg'),
        ('/x/shot.png', 'image/png'),
        ('/x/statement.pdf', 'application/pdf'),
    ])
    def test_known_extensions(self, path, expected):
        assert StaticAsset.resolve(path).content_type == expected

    @pytest.mark.parametrize('path', [
        '/x/archive.tar.gz', '/x/noextension', '/x/.bashrc', '/x/trailing.',
    ])
    def test_unknown_extensions_fall_back_to_octet_stream(self, path):
        assert StaticAsset.resolve(path).content_type == DEFAULT_CONTENT_TYPE

    def test_extension_match_is_case_insensitive(self):
        assert StaticAsset.resolve('/x/SCAN.PNG').content_type == 'image/png'

    def test_an_explicit_content_type_always_wins(self):
        asset = StaticAsset.resolve('/x/report.html', 'text/plain')
        assert asset.content_type == 'text/plain'

    def test_an_empty_explicit_content_type_is_treated_as_unset(self):
        assert StaticAsset.resolve('/x/report.html', '').content_type == 'text/html'

    def test_only_the_final_extension_counts(self):
        assert StaticAsset.resolve('/x/a.css/b.js').content_type == 'application/javascript'

    def test_path_is_preserved_exactly(self):
        weird = '/x/a b/åäö.html'
        assert StaticAsset.resolve(weird).path == weird


# --------------------------------------------------------------------------
# ErrorResponse / ServerConfig / BackgroundTask
# --------------------------------------------------------------------------
class TestErrorResponse:
    def test_serialises_to_the_shape_the_frontend_reads(self):
        assert ErrorResponse(error='nope').model_dump_json() == '{"error":"nope"}'

    def test_rejects_extra_fields_so_the_shape_cannot_drift(self):
        with pytest.raises(ValidationError):
            ErrorResponse(error='nope', code=400)

    def test_error_is_required(self):
        with pytest.raises(ValidationError):
            ErrorResponse()

    def test_non_ascii_survives_a_round_trip(self):
        payload = ErrorResponse(error='scan ≥ 2 pages — ⚠ failed').model_dump_json()
        import json
        assert json.loads(payload)['error'] == 'scan ≥ 2 pages — ⚠ failed'


class TestServerConfig:
    def test_defaults_match_the_documented_dashboard_port(self):
        c = ServerConfig()
        assert c.address == ('0.0.0.0', 8765)
        assert c.url == 'http://localhost:8765/'

    @pytest.mark.parametrize('port', [1, 8765, 65535])
    def test_valid_ports(self, port):
        assert ServerConfig(port=port).port == port

    @pytest.mark.parametrize('port', [0, -1, 65536, 99999])
    def test_out_of_range_ports_are_refused(self, port):
        """Fails closed: a bad PORT should stop boot, not bind something random."""
        with pytest.raises(ValidationError):
            ServerConfig(port=port)

    def test_port_is_reflected_in_the_banner_url(self):
        assert ServerConfig(port=9001).url == 'http://localhost:9001/'

    def test_host_is_carried_into_the_bind_address(self):
        assert ServerConfig(host='127.0.0.1', port=1234).address == ('127.0.0.1', 1234)


class TestBackgroundTask:
    def test_holds_a_callable_and_its_banner(self):
        calls = []
        task = BackgroundTask(label='poll', target=lambda: calls.append(1), banner='Polling')
        task.target()
        assert calls == [1] and task.banner == 'Polling'

    def test_banner_is_optional(self):
        assert BackgroundTask(label='quiet', target=lambda: None).banner == ''

    def test_a_non_callable_target_is_refused(self):
        with pytest.raises(ValidationError):
            BackgroundTask(label='bad', target='not_a_function')

    def test_label_is_required(self):
        with pytest.raises(ValidationError):
            BackgroundTask(target=lambda: None)


def test_no_cache_headers_cover_every_stale_response_vector():
    assert dict(NO_CACHE_HEADERS) == {
        'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
        'Pragma': 'no-cache',
        'Expires': '0',
    }
