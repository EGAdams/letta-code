"""Tests for the Server Management helpers in server.py.

These cover the pure log/registry logic (no live network): the server
registry lookup, file tailing with stable line keys, log-row filtering,
the down-status path for an unreachable health check, and the
start/"starting" lifecycle used by the executor Start button.
"""
import server


class _FakeCursor:
    def __init__(self, rows):
        self.rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, *_args):
        return None

    def fetchall(self):
        return self.rows


class _FakeConnection:
    def __init__(self, rows):
        self.rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return _FakeCursor(self.rows)


def _clear_starting():
    """Reset the module-level starting-state between tests."""
    with server._starting_lock:
        server._starting_servers.clear()


def _clear_agent_caches():
    with server._letta_id_cache_lock:
        server._letta_id_cache.clear()
    with server._agent_list_cache_lock:
        server._agent_list_cache['value'] = None
        server._agent_list_cache['ts'] = 0.0


def test_get_server_known_and_unknown():
    assert server.get_server('letta')['name'] == 'Letta Server'
    assert server.get_server('nope') is None


def test_lookup_receipt_rejects_date_amount_file_when_matched_expense_url_is_empty(
        monkeypatch):
    expense = {
        'id': 1122,
        'id_light': 'goodwill_gandy_105_saint_petersb_fl',
        'description': 'GOODWILL GANDY #105 SAINT PETERSB FL',
        'receipt_url': '',
    }
    monkeypatch.setattr(
        server, '_rol_get_connection', lambda: _FakeConnection([expense]))
    monkeypatch.setattr(
        server, '_resolve_expense_receipt_path',
        lambda _date, _amount, _receipt_url: '/wrong/receipt.png')

    result = server.lookup_receipt(
        '2025-01-07',
        '-14.96',
        'goodwill_gandy_105_saint_petersb_fl',
        'GOODWILL GANDY #105 SAINT PETERSB FL',
    )

    assert result['ok'] is False
    assert result['expense_id'] == 1122
    assert result['receipt_url'] == ''
    assert result['receipt_path'] == ''
    assert result['error'] == 'No receipt on file for this expense.'


def test_receipts_present_is_scoped_to_each_matching_expense(monkeypatch):
    rows = [
        {
            'id': 1122,
            'expense_date': '2025-01-07',
            'amount': '14.96',
            'id_light': 'goodwill_gandy_105_saint_petersb_fl',
            'description': 'GOODWILL GANDY #105 SAINT PETERSB FL',
            'receipt_url': '',
        },
        {
            'id': 1123,
            'expense_date': '2025-01-07',
            'amount': '14.96',
            'id_light': 'other_vendor_01_07_25_14_96',
            'description': 'OTHER VENDOR',
            'receipt_url': 'receipts/other.png',
        },
    ]
    monkeypatch.setattr(
        server, '_rol_get_connection', lambda: _FakeConnection(rows))
    monkeypatch.setattr(
        server, '_resolve_expense_receipt_path',
        lambda _date, _amount, receipt_url:
        '/receipts/other.png' if receipt_url else None)

    result = server.receipts_present([
        {
            'date': '2025-01-07',
            'signed_amount': '-14.96',
            'vendor_key': 'goodwill_gandy_105_saint_petersb_fl',
            'description': 'GOODWILL GANDY #105 SAINT PETERSB FL',
        },
        {
            'date': '2025-01-07',
            'signed_amount': '-14.96',
            'vendor_key': 'other_vendor',
            'description': 'OTHER VENDOR',
        },
    ])

    assert result == {'ok': True, 'present': [False, True]}


def test_expense_receipt_resolution_falls_back_to_date_amount_for_nonempty_url(
        monkeypatch):
    monkeypatch.setattr(server, '_resolve_receipt_url_path', lambda _url: None)
    monkeypatch.setattr(
        server,
        '_receipt_index',
        lambda: ({('2025-02-26', '40.88'): ['/receipts/applebees.jpg']}, {}),
    )

    assert server._resolve_expense_receipt_path(
        '2025-02-26',
        '40.88',
        'applebees_comstock_park_02_26_25_40_88.jpg',
    ) == '/receipts/applebees.jpg'


def test_expense_receipt_resolution_never_falls_back_for_empty_url(monkeypatch):
    monkeypatch.setattr(
        server,
        '_receipt_index',
        lambda: ({('2025-01-07', '14.96'): ['/receipts/wrong.png']}, {}),
    )

    assert server._resolve_expense_receipt_path(
        '2025-01-07', '14.96', '') is None


def test_mazda_stage_agents_are_listed_for_dashboard():
    names = {cfg['name'] for cfg in server.LETTA_AGENTS}
    assert {
        'Mazda Router',
        'Mazda Parser',
        'Mazda Vendor Identity',
        'Mazda Receipt Linker',
        'Mazda Categorization',
    }.issubset(names)


def test_build_agent_list_uses_cached_list(monkeypatch):
    _clear_agent_caches()
    calls = {'count': 0}

    def fake_get_letta_id(cfg):
        calls['count'] += 1
        return 'agent-' + cfg['name'].lower().replace(' ', '-')

    monkeypatch.setattr(server, 'get_letta_id', fake_get_letta_id)

    first = server.build_agent_list()
    second = server.build_agent_list()

    assert first == second
    assert calls['count'] == len(server.LETTA_AGENTS)


def test_build_agent_list_force_refresh_bypasses_cache(monkeypatch):
    _clear_agent_caches()
    calls = {'count': 0}

    def fake_get_letta_id(cfg):
        calls['count'] += 1
        return 'agent-' + cfg['name'].lower().replace(' ', '-')

    monkeypatch.setattr(server, 'get_letta_id', fake_get_letta_id)

    server.build_agent_list()
    server.build_agent_list(force_refresh=True)

    assert calls['count'] == len(server.LETTA_AGENTS) * 2


def test_every_server_has_a_log_or_health_source():
    # A server with no monitorable source would silently render an empty,
    # useless view. Valid sources: a log_file, a health_url, a tcp_check, or a
    # named 'check' function in HEALTH_CHECKS.
    for cfg in server.SERVERS:
        assert (cfg.get('log_file') or cfg.get('health_url')
                or cfg.get('tcp_check') or cfg.get('check')), cfg['key']


def test_named_checks_resolve_to_callables():
    # Any SERVERS entry that uses 'check' must reference a real HEALTH_CHECKS fn.
    for cfg in server.SERVERS:
        name = cfg.get('check')
        if name:
            assert name in server.HEALTH_CHECKS, name
            assert callable(server.HEALTH_CHECKS[name])


def test_frita_executor_health_flags_missing_sdk(monkeypatch):
    # Good executor not ready -> down, with a clear "minions broken" message.
    def fake_probe(url, timeout):
        if url == server.FRITA_EXEC_GOOD_URL:
            return {'ready': False, 'sdk_present': False, 'claude_present': True,
                    'creds_present': True, 'host': 'good1'}
        return None  # nothing on :8797
    monkeypatch.setattr(server, '_probe_sdk_status', fake_probe)
    h = server.frita_executor_health(timeout=1)
    assert h['ok'] is False
    assert 'NOT ready' in h['text']
    assert 'sdk_present' in h['text']


def test_frita_executor_health_detects_ghost(monkeypatch):
    # Good executor ready, but a different no-SDK executor answers :8797 -> still
    # "up" (minions work) but the ghost is surfaced in the status text.
    def fake_probe(url, timeout):
        if url == server.FRITA_EXEC_GOOD_URL:
            return {'ready': True, 'sdk_present': True, 'claude_present': True,
                    'creds_present': True, 'host': 'good1'}
        if url == server.FRITA_EXEC_GHOST_URL:
            return {'ready': False, 'sdk_present': False, 'host': 'ghost9'}
        return None
    monkeypatch.setattr(server, '_probe_sdk_status', fake_probe)
    h = server.frita_executor_health(timeout=1)
    assert h['ok'] is True
    assert 'GHOST' in h['text']
    assert 'ghost9' in h['text']


def test_frita_executor_health_clean_when_no_ghost(monkeypatch):
    def fake_probe(url, timeout):
        if url == server.FRITA_EXEC_GOOD_URL:
            return {'ready': True, 'sdk_present': True, 'claude_present': True,
                    'creds_present': True, 'host': 'good1'}
        return None  # nothing on :8797 at all
    monkeypatch.setattr(server, '_probe_sdk_status', fake_probe)
    h = server.frita_executor_health(timeout=1)
    assert h['ok'] is True
    assert 'GHOST' not in h['text']


def test_compute_server_status_up_and_degraded_concern():
    assert server.compute_server_status({'ok': True}) == 'up'
    # reachable but degraded (e.g. frita ghost) -> yellow
    assert server.compute_server_status({'ok': True, 'concern': True}) == 'concern'


def test_compute_server_status_down_but_restartable_is_concern():
    # local restartable server that's down -> yellow (fixable from the dashboard)
    assert server.compute_server_status(
        {'ok': False, 'text': 'HTTP 503'}, restartable=True) == 'concern'


def test_compute_server_status_recently_restarted_is_starting():
    assert server.compute_server_status(
        {'ok': False, 'text': 'HTTP 000'}, starting=True, restartable=True) == 'starting'


def test_compute_server_status_dependency_down_is_concern():
    # Win10 dockerd down -> yellow even for a not-otherwise-restartable check
    assert server.compute_server_status(
        {'ok': False, 'text': 'unreachable: refused'},
        dependency_down=True) == 'concern'


def test_compute_server_status_red_when_host_unreachable():
    # remote box we can't even reach to restart -> red (truly stuck)
    assert server.compute_server_status(
        {'ok': False, 'text': 'unreachable: timed out'},
        restartable=True, host_unreachable=True) == 'down'


def test_compute_server_status_red_when_not_restartable():
    assert server.compute_server_status({'ok': False, 'text': 'HTTP 500'}) == 'down'


def test_every_server_is_restartable():
    # "the user never needs the command line": every SERVERS entry has a handler.
    for cfg in server.SERVERS:
        assert cfg['key'] in server.RESTARTABLE_KEYS, f"{cfg['key']} not restartable"


def test_restart_server_unknown_key_is_error():
    r = server.restart_server('does-not-exist')
    assert r['ok'] is False


def test_restart_server_dispatches_to_handler(monkeypatch):
    called = {}

    def fake_handler():
        called['hit'] = True
        return {'ok': True, 'text': 'ok'}

    monkeypatch.setitem(server.RESTART_HANDLERS, 'executor', fake_handler)
    r = server.restart_server('executor')
    assert r['ok'] is True and called.get('hit') is True


def test_frita_executor_health_concern_flag_set_on_ghost(monkeypatch):
    def fake_probe(url, timeout):
        if url == server.FRITA_EXEC_GOOD_URL:
            return {'ready': True, 'sdk_present': True, 'claude_present': True,
                    'creds_present': True, 'host': 'good1'}
        if url == server.FRITA_EXEC_GHOST_URL:
            return {'ready': False, 'sdk_present': False, 'host': 'ghost9'}
        return None
    monkeypatch.setattr(server, '_probe_sdk_status', fake_probe)
    h = server.frita_executor_health(timeout=1)
    assert h['ok'] is True and h.get('concern') is True


def test_container_status_for_summarizes_docker_state():
    states = {'letta-server': 'Exited (139) 54 minutes ago',
              'letta-memfs': 'Up 2 minutes (healthy)'}
    s = server.container_status_for('letta', states)
    assert 'letta-server: Exited (139) 54 minutes ago' in s
    # non-docker server key → empty
    assert server.container_status_for('dashboard', states) == ''
    # no states (probe failed) → empty
    assert server.container_status_for('letta', {}) == ''


def test_win10_container_states_parses_docker_ps(monkeypatch):
    class _R:
        stdout = 'letta-server|Up 3 minutes\nfrita-executor|Restarting (1) 2 seconds ago\n'
        stderr = ''
    monkeypatch.setattr(server.subprocess, 'run', lambda *a, **k: _R())
    server._win10_containers_cache['value'] = None
    server._win10_containers_cache['ts'] = 0.0
    states = server.win10_container_states()
    assert states['letta-server'] == 'Up 3 minutes'
    assert states['frita-executor'] == 'Restarting (1) 2 seconds ago'


def test_model_stats_sources_cover_w11_r46_gemini():
    keys = set(server.MODEL_STAT_SOURCES)
    assert {'w11-codex', 'r46-codex', 'w11-claude', 'r46-claude', 'gemini'} <= keys


def _codex_usage(primary, secondary=0, reached=False):
    return {'model': 'gpt-5.5', 'as_of': 1.0, 'usage': {
        'plan_type': 'plus',
        'rate_limit': {'limit_reached': reached,
                       'primary_window': {'used_percent': primary, 'reset_at': 9999999999},
                       'secondary_window': {'used_percent': secondary, 'reset_at': 9999999999}}}}


def test_model_stats_codex_red_at_100_percent(monkeypatch):
    monkeypatch.setattr(server, '_run_extractor', lambda *a, **k: _codex_usage(100.0, 64.0))
    d = server.model_stats('w11-codex')
    assert d['status'] == 'down'              # maxed → red
    assert len(d['windows']) == 2
    assert d['windows'][0]['used_percent'] == 100.0
    assert d['windows'][0]['resets_in']      # reset shown


def test_model_stats_codex_red_when_limit_reached_flag(monkeypatch):
    monkeypatch.setattr(server, '_run_extractor', lambda *a, **k: _codex_usage(20.0, reached=True))
    assert server.model_stats('w11-codex')['status'] == 'down'


def test_model_stats_codex_concern_when_high(monkeypatch):
    monkeypatch.setattr(server, '_run_extractor', lambda *a, **k: _codex_usage(85.0))
    assert server.model_stats('w11-codex')['status'] == 'concern'


def test_model_stats_codex_green_when_low(monkeypatch):
    # mom's machine ~90% left == ~10% used → green
    monkeypatch.setattr(server, '_run_extractor', lambda *a, **k: _codex_usage(10.0, 11.0))
    assert server.model_stats('r46-codex')['status'] == 'up'


def test_model_stats_codex_token_expired_is_concern_with_hint(monkeypatch):
    monkeypatch.setattr(server, '_run_extractor', lambda *a, **k: {'model': 'gpt-5.5', 'error': 'token_expired'})
    d = server.model_stats('w11-codex')
    assert d['status'] == 'concern' and 'codex login' in d['detail']


def test_model_stats_claude_live_windows(monkeypatch):
    monkeypatch.setattr(server, '_run_extractor', lambda *a, **k: {
        'recent_model': 'claude-opus-4-8', 'as_of': 1.0,
        'usage': {'five_hour': {'utilization': 19.0, 'resets_at': '2026-06-22T21:30:00+00:00'},
                  'seven_day': {'utilization': 12.0, 'resets_at': '2026-06-29T08:00:00+00:00'},
                  'extra_usage': {'is_enabled': False}}})
    d = server.model_stats('w11-claude')
    assert d['status'] == 'up'
    assert d['model'] == 'claude-opus-4-8'
    assert [w['used_percent'] for w in d['windows']] == [19.0, 12.0]


def test_model_stats_unknown_source():
    assert server.model_stats('nope')['ok'] is False


def test_classify_failure_distinguishes_classes():
    assert server.classify_failure('llm_error: HTTP Error 404: Not Found')[0] == 'not_found'
    assert server.classify_failure('HTTP 429 too many requests')[0] == 'rate_limit'
    assert server.classify_failure('urlopen error timed out')[0] == 'timeout'
    assert server.classify_failure('connection refused')[0] == 'refused'
    assert server.classify_failure('HTTP 401 Unauthorized')[0] == 'auth'
    # the bug we fixed: a 404 must NOT be labelled rate-limited
    assert server.classify_failure('HTTP Error 404')[1] != 'rate-limited'


def test_track_down_duration_clears_on_up_and_accumulates(monkeypatch):
    server._server_down_since.pop('dur-test', None)
    t = [1000.0]
    monkeypatch.setattr(server.time, 'time', lambda: t[0])
    assert server.track_down_duration('dur-test', 'down') == (0, False)
    t[0] = 1000.0 + 30
    dur, stale = server.track_down_duration('dur-test', 'down')
    assert dur == 30 and stale is False
    t[0] = 1000.0 + server.SERVER_STALE_DOWN_SECONDS + 1
    dur, stale = server.track_down_duration('dur-test', 'concern')
    assert stale is True
    assert server.track_down_duration('dur-test', 'up') == (0, False)


def test_win10_node_is_registered_check_and_restartable():
    keys = {s['key'] for s in server.SERVERS}
    assert 'win10-node' in keys
    assert 'win10_node_health' in server.HEALTH_CHECKS
    assert 'win10-node' in server.RESTARTABLE_KEYS


def test_win10_hosted_servers_depend_on_node():
    dep = {s['key']: s.get('depends_on') for s in server.SERVERS}
    for k in ('letta', 'logger-api', 'frita-executor', 'dashboard-proxy'):
        assert dep.get(k) == 'win10-node', f'{k} should depend on win10-node'


def _frita_cfg():
    return next(c for c in server.LETTA_AGENTS if c['name'] == 'Frita')


def test_frita_is_flagged_as_claude_sdk_user():
    # Frita drives the Claude SDK executor, so her tab must be eligible for the
    # /claude_sdk work-endpoint health check (she has no required_tools).
    assert _frita_cfg().get('uses_claude_sdk') is True


def test_agent_health_red_when_claude_sdk_endpoint_404(monkeypatch):
    # The work endpoint Frita's tool POSTs to (/claude_sdk) returns 404 -> her
    # tab must go RED with a clear message (this is the exact "HTTP Error 404"
    # failure the dashboard previously could not see).
    monkeypatch.setattr(server, 'get_letta_id', lambda cfg: cfg.get('id') or 'agent-x')
    h = server.agent_health_check(_frita_cfg(), timeout=1, sdk_status='not_found')
    assert h['ok'] is False
    assert '404' in h['text']


def test_agent_health_red_when_claude_sdk_endpoint_unreachable(monkeypatch):
    monkeypatch.setattr(server, 'get_letta_id', lambda cfg: cfg.get('id') or 'agent-x')
    h = server.agent_health_check(_frita_cfg(), timeout=1, sdk_status='unreachable')
    assert h['ok'] is False


def test_agent_health_ok_when_claude_sdk_endpoint_present(monkeypatch):
    monkeypatch.setattr(server, 'get_letta_id', lambda cfg: cfg.get('id') or 'agent-x')
    h = server.agent_health_check(_frita_cfg(), timeout=1, sdk_status='ok')
    assert h['ok'] is True


def test_probe_claude_sdk_endpoint_maps_404_to_not_found(monkeypatch):
    import urllib.error

    def boom(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 404, 'Not Found', {}, None)

    monkeypatch.setattr(server.urllib.request, 'urlopen', boom)
    assert server._probe_claude_sdk_endpoint('http://x/claude_sdk', 1) == 'not_found'


def test_probe_claude_sdk_endpoint_405_means_route_exists(monkeypatch):
    # The work route only accepts POST; a GET/HEAD 405 proves it exists -> ok.
    import urllib.error

    def boom(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 405, 'Method Not Allowed', {}, None)

    monkeypatch.setattr(server.urllib.request, 'urlopen', boom)
    assert server._probe_claude_sdk_endpoint('http://x/claude_sdk', 1) == 'ok'


def test_tail_lines_returns_trailing_lines_with_absolute_start(tmp_path):
    p = tmp_path / 'app.log'
    p.write_text('\n'.join(f'line {i}' for i in range(10)) + '\n')
    start, lines = server.tail_lines(str(p), 3)
    assert lines == ['line 7', 'line 8', 'line 9']
    assert start == 7  # absolute index of the first returned line


def test_tail_lines_missing_file_returns_none():
    assert server.tail_lines('/no/such/file.log', 5) is None


def test_server_log_rows_tails_file_and_assigns_stable_seq(tmp_path):
    p = tmp_path / 'app.log'
    p.write_text('alpha\nbeta\ngamma\n')
    cfg = {'key': 'x', 'name': 'X', 'log_file': str(p)}
    out = server.server_log_rows(cfg)
    texts = [r['text'] for r in out['rows']]
    assert texts == ['alpha', 'beta', 'gamma']
    # seq is the absolute line number — distinct and ascending.
    seqs = [r['seq'] for r in out['rows']]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)


def test_server_log_rows_filters_case_insensitively(tmp_path):
    p = tmp_path / 'app.log'
    p.write_text('starting up\nERROR: boom\nall good\nminor error here\n')
    cfg = {'key': 'x', 'name': 'X', 'log_file': str(p)}
    out = server.server_log_rows(cfg, q='error')
    assert [r['text'] for r in out['rows']] == ['ERROR: boom', 'minor error here']


def test_server_log_rows_missing_file_reports_a_row(tmp_path):
    cfg = {'key': 'x', 'name': 'X', 'log_file': str(tmp_path / 'absent.log')}
    out = server.server_log_rows(cfg)
    assert len(out['rows']) == 1
    assert 'not found' in out['rows'][0]['text']


def test_server_health_down_for_unreachable_url():
    # Port 1 is never a real HTTP server -> down, never raises.
    health = server.server_health({'health_url': 'http://127.0.0.1:1/'})
    assert health['ok'] is False
    assert health['text']


# ── starting-state lifecycle (executor Start button) ──────────────────────────

def test_mark_and_is_server_starting():
    _clear_starting()
    assert server.is_server_starting('executor') is False
    server.mark_server_starting('executor')
    assert server.is_server_starting('executor') is True


def test_is_server_starting_expires_after_window(monkeypatch):
    _clear_starting()
    server.mark_server_starting('executor')
    # Fast-forward the stored start time past the 120s window.
    from datetime import timedelta
    with server._starting_lock:
        server._starting_servers['executor'] -= timedelta(seconds=121)
    assert server.is_server_starting('executor') is False
    # Expired entry is also evicted.
    with server._starting_lock:
        assert 'executor' not in server._starting_servers


def test_server_log_rows_reports_starting_status(tmp_path):
    _clear_starting()
    server.mark_server_starting('executor')
    cfg = {'key': 'executor', 'name': 'Executor', 'health_url': 'http://127.0.0.1:1/'}
    out = server.server_log_rows(cfg)
    # "starting" wins over the (unreachable) health check.
    assert out['status']['ok'] is False
    assert 'STARTING' in out['status']['text']
    _clear_starting()


# ── Logger API "Start" self-healing (2026-06-10) ───────────────────────────────
#
# docker-compose v1.29.2 throws `KeyError: 'ContainerConfig'` when it tries to
# "recreate" a logger-api container stuck in the `Created` state (e.g. an
# earlier `docker-compose up` was interrupted, or the image was rebuilt with
# BuildKit). When that happened, clicking "Start Logger API" re-ran
# `docker-compose up -d` and hit the exact same error every time — the button
# could never recover the service on its own; it had to be fixed by hand over
# SSH (`docker rm` the stuck containers, then `docker-compose up -d`).
#
# These tests assert the Start command removes any logger-api containers
# stuck in `Created` state BEFORE running docker-compose, so the button is
# self-healing — see dashboard_logger_api_containerconfig_2026_06_10 memory.

def test_build_logger_api_start_command_removes_stuck_containers_first():
    cmd = server.build_logger_api_start_command()

    assert cmd[:5] == ['ssh', '-o', 'ConnectTimeout=10', '-o', 'BatchMode=yes']
    assert cmd[5] == server.LETTA_DOCKER_HOST
    assert cmd[6:8] == ['bash', '-c']

    remote_script = cmd[8]
    # Must remove containers stuck in `Created` state (the docker-compose
    # v1.29.2 `KeyError: 'ContainerConfig'` failure mode) before running
    # docker-compose, or `docker-compose up -d` hits the same recreate error.
    assert 'status=created' in remote_script
    assert 'docker rm' in remote_script
    assert 'logger-api' in remote_script
    # Still launches the real start script.
    assert server.LOGGER_API_START_SCRIPT in remote_script
    # Cleanup must happen BEFORE the start script runs.
    assert remote_script.index('docker rm') < remote_script.index(server.LOGGER_API_START_SCRIPT)


def test_start_logger_api_uses_self_healing_command(monkeypatch, tmp_path):
    _clear_starting()
    log_path = tmp_path / 'logger_api_startup.log'
    monkeypatch.setattr(server, 'LOGGER_API_STARTUP_LOG', str(log_path))

    captured = {}

    def fake_popen(cmd, **kwargs):
        captured['cmd'] = cmd

        class FakeProc:
            pass

        return FakeProc()

    monkeypatch.setattr(server.subprocess, 'Popen', fake_popen)

    result = server.start_logger_api()

    assert result['ok'] is True
    assert captured['cmd'] == server.build_logger_api_start_command()
    assert server.is_server_starting('logger-api')
    _clear_starting()


# ── Agent health checks ───────────────────────────────────────────────────────


def test_mazda_letta_agents_declare_required_tools():
    """Every Mazda minion in LETTA_AGENTS must declare required_tools=['run_claude_code_sdk'].
    FAILS until LETTA_AGENTS is updated with required_tools entries."""
    minion_names = {
        'Mazda Router', 'Mazda Parser', 'Mazda Vendor Identity',
        'Mazda Receipt Linker', 'Mazda Categorization',
    }
    for cfg in server.LETTA_AGENTS:
        if cfg['name'] in minion_names:
            assert cfg.get('required_tools'), f"{cfg['name']} missing required_tools"
            assert 'run_claude_code_sdk' in cfg['required_tools'], (
                f"{cfg['name']} required_tools missing run_claude_code_sdk"
            )


def test_mazda_declares_delegation_tool():
    # The live Mazda orchestrator (agent-6b536cf4) delegates via relay_message_to_chatgpt;
    # that's the tool whose presence signals it's wired up (the old
    # send_message_to_agent_and_wait_for_reply/executor_run set was a prior incarnation).
    mazda = next(cfg for cfg in server.LETTA_AGENTS if cfg['name'] == 'Mazda')
    assert mazda['required_tools'] == ['relay_message_to_chatgpt']


def test_agent_health_check_unresolvable_agent_is_unhealthy(monkeypatch):
    """Agent not found in Letta → health check returns ok=False.
    FAILS until agent_health_check is added to server.py."""
    cfg = {'name': 'Ghost', 'id': None, 'required_tools': []}
    monkeypatch.setattr(server, 'get_letta_id', lambda c: None)
    h = server.agent_health_check(cfg)
    assert h['ok'] is False
    assert 'not found' in h['text'].lower() or 'ghost' in h['text'].lower()


def test_agent_health_check_missing_required_tool_is_unhealthy(monkeypatch):
    """Mazda minion missing run_claude_code_sdk → health check red.
    FAILS until agent_health_check is added to server.py."""
    cfg = {'name': 'Mazda Router', 'id': 'agent-test-123', 'required_tools': ['run_claude_code_sdk']}
    monkeypatch.setattr(server, 'get_letta_id', lambda c: c['id'])
    monkeypatch.setattr(server, 'letta_get', lambda path, **kw: [
        {'name': 'memory_insert'}, {'name': 'memory_replace'},
    ])
    h = server.agent_health_check(cfg, sdk_status='ok')
    assert h['ok'] is False
    assert 'run_claude_code_sdk' in h['text']


def test_agent_health_check_all_tools_present_is_healthy(monkeypatch):
    """Mazda minion with run_claude_code_sdk → health check green.
    FAILS until agent_health_check is added to server.py."""
    cfg = {'name': 'Mazda Router', 'id': 'agent-test-123', 'required_tools': ['run_claude_code_sdk']}
    monkeypatch.setattr(server, 'get_letta_id', lambda c: c['id'])
    monkeypatch.setattr(server, 'letta_get', lambda path, **kw: [
        {'name': 'run_claude_code_sdk'}, {'name': 'memory_insert'},
    ])
    h = server.agent_health_check(cfg, sdk_status='ok')
    assert h['ok'] is True
    assert 'run_claude_code_sdk' in h['text']


# ── ChatGPT/Codex provider-wide rate-limit probe (2026-06-18) ────────────────
#
# Mazda + all 5 minions share one chatgpt-plus-pro OAuth account. A 429 from
# that provider hits all of them at once, but previously only surfaced once a
# human happened to use the dashboard's Test feature against one of them. The
# fix is a background probe (mirrors _health_poll_loop / _ssh_poll_loop) that
# proactively turns every agent on the provider red.

def test_mazda_and_minions_tagged_with_shared_llm_provider():
    fleet_names = {
        'Mazda', 'Mazda Router', 'Mazda Parser', 'Mazda Vendor Identity',
        'Mazda Receipt Linker', 'Mazda Categorization',
    }
    for cfg in server.LETTA_AGENTS:
        if cfg['name'] in fleet_names:
            assert cfg.get('llm_provider') == server.CHATGPT_PLUS_PRO, cfg['name']


def test_provider_agent_ids_returns_real_ids_for_tagged_agents():
    ids = server._provider_agent_ids(server.CHATGPT_PLUS_PRO)
    assert len(ids) == 6
    mazda = next(cfg for cfg in server.LETTA_AGENTS if cfg['name'] == 'Mazda')
    assert mazda['id'] in ids


def test_poll_chatgpt_provider_once_flags_every_fleet_agent_on_429(monkeypatch):
    monkeypatch.setattr(server, '_probe_chatgpt_provider',
                         lambda agent_id, timeout=20: {'ok': False, 'text': 'llm_rate_limit: too many requests'})
    server._poll_chatgpt_provider_once()
    for agent_id in server._provider_agent_ids(server.CHATGPT_PLUS_PRO):
        with server._agent_send_errors_lock:
            err = server._agent_send_errors.get(agent_id)
        assert err is not None, agent_id
        assert 'rate-limited' in err['text']
    # cleanup so this test doesn't leak state into others
    for agent_id in server._provider_agent_ids(server.CHATGPT_PLUS_PRO):
        server.clear_agent_send_error(agent_id)


def test_poll_chatgpt_provider_once_clears_every_fleet_agent_on_success(monkeypatch):
    for agent_id in server._provider_agent_ids(server.CHATGPT_PLUS_PRO):
        server.record_agent_send_error(agent_id, 'stale error from a previous sweep')
    monkeypatch.setattr(server, '_probe_chatgpt_provider',
                         lambda agent_id, timeout=20: {'ok': True, 'text': ''})
    server._poll_chatgpt_provider_once()
    for agent_id in server._provider_agent_ids(server.CHATGPT_PLUS_PRO):
        with server._agent_send_errors_lock:
            assert server._agent_send_errors.get(agent_id) is None, agent_id


def test_poll_chatgpt_provider_once_only_probes_the_canary(monkeypatch):
    # One probe call must cover the whole fleet, not one call per agent —
    # that's the whole point (avoid burning quota 6x for one rate-limit check).
    calls = []
    monkeypatch.setattr(server, '_probe_chatgpt_provider',
                         lambda agent_id, timeout=20: (calls.append(agent_id), {'ok': True, 'text': ''})[1])
    server._poll_chatgpt_provider_once()
    assert len(calls) == 1
