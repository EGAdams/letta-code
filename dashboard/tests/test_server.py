"""Tests for the Server Management helpers in server.py.

These cover the pure log/registry logic (no live network): the server
registry lookup, file tailing with stable line keys, log-row filtering,
the down-status path for an unreachable health check, and the
start/"starting" lifecycle used by the executor Start button.
"""
import json

import pytest
import server


@pytest.fixture(autouse=True)
def _clear_model_stats_cache():
    server._model_stats_cache.clear()


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


def test_rol_finance_reports_include_diners_annual_summary():
    report = next(
        (r for r in server.ROL_FINANCE_REPORTS
         if r['dir'] == 'diners_0587_whole_year_2025'),
        None,
    )
    assert report is not None
    assert report['key'] == 'diners-0587-year'
    assert report['label'] == 'Diners 0587 Year'


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


def test_receipt_index_walks_every_mount(monkeypatch, tmp_path):
    """A receipt living only in an EXTERNAL store (e.g. the live-pipeline Windows
    destination) must be indexed, not just readable_documents/receipts — otherwise
    freshly-stored receipts never get a marker. Regression for Bug 1."""
    canonical = tmp_path / 'readable' / 'receipts'
    external = tmp_path / 'winstore'
    (canonical / 'january').mkdir(parents=True)
    external.mkdir(parents=True)
    (canonical / 'january' / 'acme_01_05_25_10_00.jpg').write_bytes(b'x')
    (external / 'walmart_03_17_25_350_95.jpg').write_bytes(b'y')

    monkeypatch.setattr(server, 'RECEIPT_MOUNTS', [
        ('/rol_finances_receipts', str(tmp_path / 'readable'), str(canonical)),
        ('/rol_finances_receipts_ext', str(external), str(external)),
    ])
    by_da, by_stem = server._build_receipt_index()
    assert ('2025-01-05', '10.00') in by_da          # canonical store
    assert ('2025-03-17', '350.95') in by_da          # external store — the fix
    # URL for the external receipt uses the external mount's prefix.
    ext_fp = by_da[('2025-03-17', '350.95')][0]
    assert server._receipt_url_for_path(ext_fp) == (
        '/rol_finances_receipts_ext/walmart_03_17_25_350_95.jpg')


def test_receipt_url_for_path_canonical_includes_receipts_segment(monkeypatch, tmp_path):
    """Regression: canonical receipt URL must include the 'receipts/' path segment.

    _receipt_url_for_path computes rel from serve_base (readable_documents), not from
    the subtree (readable_documents/receipts). So a receipt at
    readable_documents/receipts/jan/acme.jpg → rel = receipts/jan/acme.jpg →
    URL = /rol_finances_receipts/receipts/jan/acme.jpg.

    Before the parallel baker fix, the baker used subtree-relative paths and
    produced /rol_finances_receipts/jan/acme.jpg (missing 'receipts/'), causing 404s.
    This test pins the correct server-side URL format so baker and server stay in sync.
    """
    canonical_docs = tmp_path / 'readable'
    (canonical_docs / 'receipts' / 'jan').mkdir(parents=True)
    receipt = canonical_docs / 'receipts' / 'jan' / 'acme_01_15_25_10_00.jpg'
    receipt.write_bytes(b'x')
    ext = tmp_path / 'ext'
    ext.mkdir()

    monkeypatch.setattr(server, 'RECEIPT_MOUNTS', [
        ('/rol_finances_receipts', str(canonical_docs), str(canonical_docs / 'receipts')),
        ('/rol_finances_receipts_ext', str(ext), str(ext)),
    ])

    url = server._receipt_url_for_path(str(receipt))
    assert url.startswith('/rol_finances_receipts/receipts/'), \
        f"Canonical URL missing 'receipts/' segment: {url}"
    assert 'jan/acme_01_15_25_10_00.jpg' in url


def test_receipt_url_for_path_external_gets_ext_prefix(monkeypatch, tmp_path):
    """External receipts (live-pipeline Windows store) must use /rol_finances_receipts_ext/."""
    canonical_docs = tmp_path / 'readable'
    (canonical_docs / 'receipts').mkdir(parents=True)
    ext = tmp_path / 'ext'
    ext.mkdir()
    ext_receipt = ext / 'walmart_03_17_25_350_95.jpg'
    ext_receipt.write_bytes(b'x')

    monkeypatch.setattr(server, 'RECEIPT_MOUNTS', [
        ('/rol_finances_receipts', str(canonical_docs), str(canonical_docs / 'receipts')),
        ('/rol_finances_receipts_ext', str(ext), str(ext)),
    ])

    url = server._receipt_url_for_path(str(ext_receipt))
    assert url == '/rol_finances_receipts_ext/walmart_03_17_25_350_95.jpg', \
        f"External receipt got wrong URL: {url}"


def test_record_stored_expense_busts_index_and_tags_event():
    """Storing an expense must invalidate the receipt-index cache (so the new
    receipt shows on the next view reload, no 300s wait) and carry kind/report_path
    so the frontend can target the right views."""
    server._RECEIPT_INDEX_CACHE.update(ts=9_999_999_999.0, by_da={}, by_stem={})
    out = server.record_stored_expense({
        'expense_id': 1169, 'kind': 'receipt', 'expense_date': '2025-03-17',
        'amount': '350.95', 'report_path': '/r/jan.html',
    })
    assert out == {'ok': True}
    assert server._RECEIPT_INDEX_CACHE['ts'] == 0.0   # cache busted
    ev = server.get_stored_expense_events(0)[-1]
    assert ev['kind'] == 'receipt'
    assert ev['report_path'] == '/r/jan.html'
    assert ev['expense_id'] == 1169


def test_record_stored_expense_defaults_kind_to_receipt():
    server.record_stored_expense({'expense_id': 7})
    assert server.get_stored_expense_events(0)[-1]['kind'] == 'receipt'


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


def test_classify_scan_result_busy():
    # The Freezer's notorious failure — reported FAST so the 5s poll stays cheap.
    r = server.classify_scan_result(6, 'SCANNER_BUSY\nScan failed: The WIA device is busy.', False)
    assert r['status'] == 'busy'
    # Also recognised from the raw COM message even without our marker.
    assert server.classify_scan_result(4, 'The WIA device is busy.', False)['status'] == 'busy'


def test_classify_scan_result_offline():
    r = server.classify_scan_result(5, "SCANNER_OFFLINE\nScanner not found matching 'HP063E28'", False)
    assert r['status'] == 'offline'


def test_classify_scan_result_ready_and_error():
    assert server.classify_scan_result(0, 'Saved: /x/scan.png', True)['status'] == 'ready'
    # exit 0 but no image on disk is NOT ready.
    assert server.classify_scan_result(0, 'Saved: /x/scan.png', False)['status'] == 'error'
    assert server.classify_scan_result(1, 'some other failure', False)['status'] == 'error'


def test_scanner_registry_selects_by_name_not_first_device():
    # Both scanners must target a named device script (the busy Freezer enumerates
    # first, so "first device" would grab the wrong scanner).
    assert server.SCANNERS['freezer']['script'] == 'run_scan_freezer.sh'
    assert server.SCANNERS['window']['script'] == 'run_scan_window.sh'
    assert server.SCANNERS['freezer']['output'] != server.SCANNERS['window']['output']


def test_build_pipeline_result_success_shapes_all_five_stages():
    facade = {
        'ok': True,
        'doc_kind': 'receipt',
        'routing_key': 'receipt.costco',
        'vendor': 'costco',
        'confidence': 0.94,
        'classification_method': 'rule_based',
        'recommended_action': 'auto',
        'parsed': {'vendor': 'costco', 'total': '84.12'},
        'error': None,
    }
    result = server.build_pipeline_result(facade, mazda_dispatched=True)
    assert result['ok'] is True
    assert result['mazda_dispatched'] is True
    names = [s['name'] for s in result['stages']]
    assert names == ['classify', 'parse', 'investigate', 'categorize', 'store']
    classify, parse = result['stages'][0], result['stages'][1]
    assert classify['status'] == 'done'
    assert classify['vendor'] == 'costco'
    assert parse['status'] == 'done' and parse['parsed']['total'] == '84.12'
    # The agentic back half is delegated to Mazda when she was dispatched.
    for stage in result['stages'][2:]:
        assert stage['status'] == 'delegated'
        assert stage['owner'] == 'mazda'


def test_build_pipeline_result_failure_marks_classify_error_and_pending_tail():
    facade = {'ok': False, 'error': 'file not found: /x.jpg'}
    result = server.build_pipeline_result(facade, mazda_dispatched=False)
    assert result['ok'] is False
    assert result['error'] == 'file not found: /x.jpg'
    assert result['mazda_dispatched'] is False
    assert result['stages'][0]['status'] == 'error'
    # Parse is an error too (no facade success), tail stages are pending.
    assert result['stages'][1]['status'] == 'error'
    for stage in result['stages'][2:]:
        assert stage['status'] == 'pending'
        assert stage['owner'] is None


def test_build_pipeline_result_ok_but_no_parse_is_skipped():
    facade = {'ok': True, 'doc_kind': 'receipt', 'parsed': None}
    result = server.build_pipeline_result(facade, mazda_dispatched=True)
    assert result['stages'][1]['status'] == 'skipped'


def test_run_intake_facade_missing_image_returns_structured_error():
    r = server.run_intake_facade('/nope/does-not-exist.jpg')
    assert r['ok'] is False
    assert 'not found' in r['error']


def test_process_scanned_document_unknown_scanner():
    r = server.process_scanned_document('bogus')
    assert r['ok'] is False
    assert 'Unknown scanner' in r['error']
    assert r['stages'] == []


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


def test_mazda_declares_self_improvement_tools():
    # The live Mazda orchestrator is healthy when its core self-improvement MCP
    # tools are attached. relay_message_to_chatgpt belonged to an older design.
    mazda = next(cfg for cfg in server.LETTA_AGENTS if cfg['name'] == 'Mazda')
    assert mazda['required_tools'] == [
        'record_trace',
        'propose_improvement',
        'run_experiment',
    ]
    assert mazda.get('orchestrator') is True


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
    # Mazda fleet (6) + Suzuki fleet (7) = 13 tagged agents
    assert len(ids) == 13
    mazda = next(cfg for cfg in server.LETTA_AGENTS if cfg['name'] == 'Mazda')
    assert mazda['id'] in ids
    suzuki = next(cfg for cfg in server.LETTA_AGENTS if cfg['name'] == 'Suzuki')
    assert suzuki['id'] in ids


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


def _write_badge(tmp_path, badge_text):
    p = tmp_path / 'report.html'
    p.write_text(f'<section class="hero"><div class="badge badge-pass">{badge_text}</div></section>')
    return str(p)


def test_classify_report_status_pass(tmp_path):
    assert server._classify_report_status(_write_badge(tmp_path, 'PASS - all good')) == 'pass'


def test_classify_report_status_review_needed(tmp_path):
    path = _write_badge(tmp_path, '⚠️ REVIEW NEEDED — uncategorized rows remain')
    assert server._classify_report_status(path) == 'review'


def test_classify_report_status_fail(tmp_path):
    assert server._classify_report_status(_write_badge(tmp_path, 'FAIL - totals do not reconcile')) == 'fail'


def test_classify_report_status_missing_file(tmp_path):
    assert server._classify_report_status(str(tmp_path / 'absent.html')) == 'fail'


def test_classify_report_status_unparseable_badge_defaults_to_review(tmp_path):
    p = tmp_path / 'report.html'
    p.write_text('<html><body>no badge here</body></html>')
    assert server._classify_report_status(str(p)) == 'review'


def _ssh_cfg():
    return {'key': '__test_ssh_conn', 'name': 'Test Conn', 'host': '0.0.0.0', 'user': 'nobody'}


def test_tailscale_test_accepts_ping_when_status_is_stale_offline(monkeypatch):
    calls = []

    def fake_run(cmd, **_kwargs):
        calls.append(cmd)
        if cmd[:2] == ['tailscale', 'status']:
            return type('Result', (), {
                'returncode': 0,
                'stdout': '100.111.161.7 samsung-sm-s156v eg1972@ android offline, last seen 4m ago\n',
                'stderr': '',
            })()
        return type('Result', (), {
            'returncode': 0,
            'stdout': 'pong from samsung-sm-s156v (100.111.161.7) via DERP(ord) in 90ms\n',
            'stderr': '',
        })()

    monkeypatch.setattr(server.subprocess, 'run', fake_run)

    result = server.tailscale_test({'host': '100.111.161.7'}, timeout=5)

    assert result['ok'] is True
    assert result['text'].startswith('reachable by tailscale ping')
    assert any(cmd[:2] == ['tailscale', 'ping'] for cmd in calls)


def test_tailscale_test_reports_down_when_status_and_ping_fail(monkeypatch):
    def fake_run(cmd, **_kwargs):
        if cmd[:2] == ['tailscale', 'status']:
            return type('Result', (), {
                'returncode': 0,
                'stdout': '100.111.161.7 samsung-sm-s156v eg1972@ android offline, last seen 4m ago\n',
                'stderr': '',
            })()
        return type('Result', (), {
            'returncode': 1,
            'stdout': '',
            'stderr': 'timed out waiting for pong\n',
        })()

    monkeypatch.setattr(server.subprocess, 'run', fake_run)

    result = server.tailscale_test({'host': '100.111.161.7'}, timeout=5)

    assert result['ok'] is False
    assert 'offline' in result['text']
    assert 'timed out waiting for pong' in result['text']


def test_ssh_health_one_slow_probe_does_not_flip_to_down(monkeypatch):
    # A single failed/slow DERP-relayed probe shouldn't flash the connection
    # red — it must survive SSH_HEALTH_FAIL_THRESHOLD consecutive failures.
    cfg = _ssh_cfg()
    server._ssh_health_cache.pop(cfg['key'], None)
    monkeypatch.setattr(server, 'connection_test', lambda cfg, timeout=None: {'ok': True, 'text': 'CONNECTED'})
    monkeypatch.setattr(server, 'SSH_CONNECTIONS', [cfg])
    server._poll_all_ssh_once()
    assert server.cached_ssh_health(cfg)['ok'] is True

    monkeypatch.setattr(server, 'connection_test', lambda cfg, timeout=None: {'ok': False, 'text': 'timed out'})
    server._poll_all_ssh_once()
    assert server.cached_ssh_health(cfg)['ok'] is True, 'one failure must not flip a healthy connection to down'

    server._poll_all_ssh_once()
    assert server.cached_ssh_health(cfg)['ok'] is False, 'second consecutive failure should flip to down'


def test_ssh_health_recovers_immediately_on_success(monkeypatch):
    cfg = _ssh_cfg()
    server._ssh_health_cache.pop(cfg['key'], None)
    monkeypatch.setattr(server, 'SSH_CONNECTIONS', [cfg])

    monkeypatch.setattr(server, 'connection_test', lambda cfg, timeout=None: {'ok': False, 'text': 'timed out'})
    server._poll_all_ssh_once()
    server._poll_all_ssh_once()
    assert server.cached_ssh_health(cfg)['ok'] is False

    monkeypatch.setattr(server, 'connection_test', lambda cfg, timeout=None: {'ok': True, 'text': 'CONNECTED'})
    server._poll_all_ssh_once()
    assert server.cached_ssh_health(cfg)['ok'] is True, 'a single success must clear the fail count immediately'


# ── ROL Finance: category persistence regression tests ─────────────────────
# These tests catch the three bugs fixed during the Diners 0587 Year session:
#  1. _update_report_row_color doubled cat-* when the same category was picked twice
#  2. _update_report_row_color left stale cat-* classes when changing categories
#  3. recategorize_expense returned ok:False for bank-only rows not in the DB
#  4. receipts_present returned False for rows whose DB date differs by 1-3 days
#     (credit-card posting date vs. purchase date)

_DINERS_ROW_HTML = """\
<table><tbody>
<tr class="{cls}" data-vendor-key="trinity_church" onclick="openCategoryPicker(this)">
<td>2025-01-17</td><td>-50.00</td><td>TRINITY CHURCH</td>
</tr>
</tbody></table>
"""


def _write_report(tmp_path, cls):
    p = tmp_path / 'report.html'
    p.write_text(_DINERS_ROW_HTML.format(cls=cls), encoding='utf-8')
    return p


def test_update_report_row_color_same_category_no_duplicate_class(tmp_path, monkeypatch):
    """Picking the same category a second time must not produce 'cat-x cat-x'."""
    p = _write_report(tmp_path, 'cat-food-and-hospitality')
    monkeypatch.setattr(server, '_report_file_for_url', lambda _: str(p))

    result = server._update_report_row_color(
        'fake/path', 'trinity_church', '2025-01-17', '-50.00',
        'cat-food-and-hospitality',
    )

    assert result is True
    html = p.read_text(encoding='utf-8')
    assert 'cat-food-and-hospitality cat-food-and-hospitality' not in html
    assert 'cat-food-and-hospitality' in html


def test_update_report_row_color_replaces_stale_cat_class(tmp_path, monkeypatch):
    """Changing category must strip the old cat-* class entirely, not append."""
    p = _write_report(tmp_path, 'cat-food-and-hospitality')
    monkeypatch.setattr(server, '_report_file_for_url', lambda _: str(p))

    server._update_report_row_color(
        'fake/path', 'trinity_church', '2025-01-17', '-50.00',
        'cat-personal',
    )

    html = p.read_text(encoding='utf-8')
    assert 'cat-personal' in html
    assert 'cat-food-and-hospitality' not in html


class _DateSelectCursor:
    """Cursor that returns expense rows only when the queried date matches."""
    def __init__(self, match_date, rows_for_match):
        self._match = match_date
        self._rows = rows_for_match
        self._last_date = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, _sql, params=None):
        self._last_date = params[0] if params else None

    def fetchall(self):
        if self._last_date == self._match:
            return self._rows
        return []


class _DateSelectConnection:
    def __init__(self, match_date, rows_for_match):
        self._cursor = _DateSelectCursor(match_date, rows_for_match)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def cursor(self):
        return self._cursor


def test_recategorize_expense_bank_only_row_returns_ok_with_warning(monkeypatch):
    """Rows not in the DB (annual-summary bank-only) must return ok:True + warning."""
    monkeypatch.setattr(
        server, '_rol_get_connection',
        lambda: _FakeConnection([]),  # empty DB
    )
    monkeypatch.setattr(server, '_update_report_row_color', lambda *_a, **_kw: True)

    result = server.recategorize_expense(
        '2025-01-17', '-50.00', 'trinity_church',
        'Food & Hospitality',
        report_path='/rol_finances_reports/jan-2025/diners_0587_whole_year_2025/report.html',
    )

    assert result['ok'] is True
    assert result['expense_id'] is None
    assert 'warning' in result


def test_receipts_present_credit_card_posting_date_offset(monkeypatch):
    """A DB expense dated 1 day before the report row must still resolve as present."""
    expense = {
        'id': 555,
        'expense_date': '2025-01-16',   # purchase date in DB
        'amount': '50.00',
        'id_light': 'trinity_church_01_16_25_50_00',
        'description': 'TRINITY CHURCH',
        'receipt_url': 'receipts/trinity_01_16_25_50_00.jpg',
    }
    monkeypatch.setattr(
        server, '_rol_get_connection', lambda: _FakeConnection([expense]))
    monkeypatch.setattr(
        server, '_resolve_expense_receipt_path',
        lambda _date, _amt, ru: '/receipts/trinity.jpg' if ru else None,
    )

    result = server.receipts_present([{
        'date': '2025-01-17',           # posting date on Diners statement (+1 day)
        'signed_amount': '-50.00',
        'vendor_key': 'trinity_church',
        'description': 'TRINITY CHURCH',
    }])

    assert result == {'ok': True, 'present': [True]}


def test_recategorize_expense_credit_card_posting_date_offset(monkeypatch):
    """recategorize_expense must match the DB row when dates differ by ±1-3 days."""
    expense = {
        'id': 555,
        'id_light': 'trinity_church_01_16_25_50_00',
        'description': 'TRINITY CHURCH',
        'category_id': None,
    }
    monkeypatch.setattr(
        server, '_rol_get_connection',
        lambda: _DateSelectConnection('2025-01-16', [expense]),
    )
    monkeypatch.setattr(server, '_update_report_row_color', lambda *_a, **_kw: True)

    result = server.recategorize_expense(
        '2025-01-17', '-50.00', 'trinity_church',
        'Food & Hospitality',
        report_path='/rol_finances_reports/jan-2025/diners_0587_whole_year_2025/report.html',
    )

    assert result['ok'] is True
    assert result['expense_id'] == 555


# ── Mazda scan-intake notification (regression: 2026-06-28 intake run) ───────
# Three bugs were caught the first time a real receipt was scanned and handed to
# Mazda. These tests pin the pure builder so they cannot silently return:
#   1. The JPEG facade exits 0 with doc_kind=unknown/confidence=0; treating that
#      as "classified" sent Mazda into investigate/categorize with empty data.
#   2. The categorizer/store commands were handed to Mazda as bare `python3`,
#      which dies with ModuleNotFoundError: No module named 'tools'.
#   3. Mazda recorded a trace but never judged it, so the autonomous reflection
#      loop (which keys on FAIL *verdicts*) could never see the failure.

# A facade result that genuinely identified a document.
_FACADE_IDENTIFIED = {
    'ok': True,
    'doc_kind': 'receipt',
    'routing_key': 'receipt.costco',
    'vendor': 'costco',
    'confidence': 0.94,
    'recommended_action': 'auto',
    'parsed': {'merchant_name': 'Costco', 'transaction_date': '2025-01-22',
               'total_amount': '84.12'},
}

# What the text-extraction facade actually returns for a JPEG scan: it ran fine
# (ok=True) but classified nothing.
_FACADE_JPEG_UNKNOWN = {
    'ok': True,
    'doc_kind': 'unknown',
    'routing_key': 'unknown',
    'vendor': 'unknown',
    'confidence': 0.0,
    'recommended_action': 'reject',
    'parsed': None,
    'error': None,
}


def test_facade_identified_true_only_for_real_classification():
    assert server.mazda_facade_identified(_FACADE_IDENTIFIED) is True


@pytest.mark.parametrize('facade', [
    _FACADE_JPEG_UNKNOWN,                                   # the live JPEG bug
    {'ok': False, 'error': 'file not found'},               # facade crashed
    {'ok': True, 'doc_kind': 'unknown', 'confidence': 0.9}, # unknown kind
    {'ok': True, 'doc_kind': 'receipt', 'confidence': 0.0}, # zero confidence
    {'ok': True, 'doc_kind': 'receipt', 'confidence': 0.9,
     'recommended_action': 'reject'},                       # rejected
    {},                                                     # nothing ran
    None,                                                   # no facade at all
])
def test_facade_identified_false_for_unusable_results(facade):
    assert server.mazda_facade_identified(facade) is False


def test_facade_identified_survives_non_numeric_confidence():
    # A garbled confidence must not raise — it should read as "not identified".
    assert server.mazda_facade_identified(
        {'ok': True, 'doc_kind': 'receipt', 'confidence': 'NaN-ish'}
    ) is False


def test_scan_message_jpeg_unknown_tells_mazda_to_classify_herself():
    """Bug 1: a doc_kind=unknown facade must NOT be sold to Mazda as classified."""
    msg = server.build_mazda_scan_message(
        '/scans/scan_freezer.jpg', 'Freezer Scanner', _FACADE_JPEG_UNKNOWN)
    # It must not claim the facade identified the document.
    assert 'IDENTIFIED this document' not in msg
    # It must route her to the vision classifier + parser herself.
    assert 'tools/classify_scan.py /scans/scan_freezer.jpg' in msg
    assert 'parse_and_categorize.py -f /scans/scan_freezer.jpg --json' in msg
    # And it must explain why (so a future reader understands the JPEG quirk).
    assert 'text extraction' in msg


def test_scan_message_identified_facade_skips_reclassify():
    """When the facade really classified, Mazda should reuse it, not redo it."""
    msg = server.build_mazda_scan_message(
        '/scans/x.jpg', 'Window Scanner', _FACADE_IDENTIFIED)
    assert 'IDENTIFIED this document' in msg
    assert 'Do NOT re-run classify or parse' in msg
    # No self-classify fallback block when the facade already did the work.
    assert 'tools/classify_scan.py' not in msg
    assert 'costco' in msg  # the vendor flows through


@pytest.mark.parametrize('facade', [_FACADE_IDENTIFIED, _FACADE_JPEG_UNKNOWN, {}, None])
def test_scan_message_commands_always_carry_pythonpath_and_venv(facade):
    """Bugs 2 + 3: every rol_finances command must use the venv python AND carry
    PYTHONPATH, or it dies with ModuleNotFoundError: No module named 'tools'.

    PYTHONPATH must travel via executor_run's ``env`` argument, NOT as an inline
    ``PYTHONPATH=...`` command prefix — the executor allowlist rejects a bare
    command whose first token is an env-assignment ("Command not in allowlist:
    PYTHONPATH=...", live trace 53, 2026-06-29)."""
    import re
    msg = server.build_mazda_scan_message('/scans/x.jpg', 'Scanner', facade)
    # PYTHONPATH is carried via the env argument (JSON object form).
    assert '{"PYTHONPATH": "/home/adamsl/rol_finances"}' in msg
    assert '/home/adamsl/rol_finances/.venv/bin/python3' in msg
    # The inline prefix form `PYTHONPATH=/path <cmd>` must NEVER be handed over —
    # that is the exact form the executor allowlist rejected on the bare command.
    assert not re.search(r'PYTHONPATH=/home/adamsl/rol_finances\s', msg)
    # A *bare* `python3 tools/...` (not the venv path, which ends in /python3)
    # must never be handed over — that is exactly the ModuleNotFoundError form.
    assert not re.search(r'(?<!/)python3 tools/', msg)
    # The store step uses the venv interpreter too.
    assert ('/home/adamsl/rol_finances/.venv/bin/python3 '
            'tools/receipt_scanning_tools/receipt_parsing_tools/parse_and_categorize.py') in msg


def test_scan_message_passes_pythonpath_via_executor_env_not_inline(facade=_FACADE_JPEG_UNKNOWN):
    """Pin the 2026-06-29 fix: executor_run steps instruct an env= argument and
    the prominent EXECUTOR RULE warns against the inline PYTHONPATH= prefix."""
    msg = server.build_mazda_scan_message('/scans/x.jpg', 'Scanner', facade)
    assert 'EXECUTOR RULE' in msg
    assert 'env={"PYTHONPATH": "/home/adamsl/rol_finances"}' in msg
    # The rule must explicitly forbid the inline prefix so future edits don't regress.
    assert 'Do NOT prefix' in msg


def test_scan_message_always_includes_judge_trace_step():
    """Bug 3: without judge_trace there is no verdict, so the autonomous
    reflection loop can never act on the failure."""
    for facade in (_FACADE_IDENTIFIED, _FACADE_JPEG_UNKNOWN, None):
        msg = server.build_mazda_scan_message('/scans/x.jpg', 'Scanner', facade)
        assert 'judge_trace(trace_id)' in msg
        assert 'record_trace(' in msg
        # judge must come after record in the instructions.
        assert msg.index('record_trace(') < msg.index('judge_trace(trace_id)')


def test_scan_message_never_passes_unknown_as_vendor_key():
    """The categorizer input must not carry the literal 'unknown' — that produced
    a guaranteed check_vendor_key miss + a wasted (Node-18-crashing) LLM call.

    Regression 2026-06-29: the JPEG path prefilled the categorizer JSON with
    description="unknown" because the facade had no parse, but by STEP 3 Mazda
    already has the REAL merchant from her own STEP 0 parse. The message must tell
    her to build the input from STEP 0, never feed her the literal placeholder."""
    msg = server.build_mazda_scan_message('/scans/x.jpg', 'Scanner', _FACADE_JPEG_UNKNOWN)
    assert '"vendor_key": "unknown"' not in msg
    # No literal placeholder categorizer input in the unidentified path.
    assert '"description": "unknown"' not in msg
    # Instead she is told to source the input from her STEP 0 parse results.
    assert 'from STEP 0' in msg


def test_scan_message_instructs_structured_intake_evidence():
    """STEP 5 must tell Mazda to record the structured IntakeVerificationEvidence
    JSON under task_name="document-intake" — that is what the intake verdict
    rubric reads to judge success vs failure. Pin the field contract so the
    dashboard message and the rol_finances rubric cannot silently drift apart."""
    msg = server.build_mazda_scan_message('/scans/x.jpg', 'Scanner', _FACADE_IDENTIFIED)
    assert 'task_name="document-intake"' in msg
    # Every field the IntakeVerificationEvidence model / judge depends on.
    for field in ('doc_kind', 'classification_confidence', 'vendor_key',
                  'vendor_key_recognized', 'category_id', 'duplicate_checked',
                  'is_duplicate', 'stored', 'expense_id', 'problems'):
        assert f'"{field}"' in msg, f'evidence field {field!r} missing from message'


def test_scan_message_judges_every_run_not_only_failures():
    """Once the intake rubric exists, a clean success must also be judged (it
    correctly PASSes), so the instruction is ALWAYS judge_trace — not the old
    'only on failure' guard that left successes unverified."""
    msg = server.build_mazda_scan_message('/scans/x.jpg', 'Scanner', _FACADE_IDENTIFIED)
    assert 'judge_trace(trace_id) — ALWAYS' in msg
    assert 'ONLY IF THE INTAKE FAILED' not in msg


def test_scan_message_round_trips_through_notify(monkeypatch):
    """_notify_mazda_of_scan must POST exactly the built message to Mazda."""
    captured = {}

    class _Resp:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def _fake_urlopen(req, timeout=0):
        captured['url'] = req.full_url
        captured['body'] = json.loads(req.data.decode())
        return _Resp()

    monkeypatch.setattr(server.urllib.request, 'urlopen', _fake_urlopen)
    server._notify_mazda_of_scan('/scans/x.jpg', 'Freezer Scanner', _FACADE_JPEG_UNKNOWN)

    expected = server.build_mazda_scan_message(
        '/scans/x.jpg', 'Freezer Scanner', _FACADE_JPEG_UNKNOWN)
    assert captured['body']['messages'][0]['content'] == expected
    assert server.MAZDA_AGENT_ID in captured['url']


# ── Scan message STEP 8 ───────────────────────────────────────────────────────

def test_scan_message_includes_dashboard_callback_step():
    """STEP 8 in the scan message instructs Mazda to POST /api/expense-stored."""
    msg = server.build_mazda_scan_message('/scans/x.jpg', 'Window Scanner')
    assert 'STEP 8' in msg
    assert '/api/expense-stored' in msg
    assert 'fire-and-forget' in msg.lower() or 'Ignore errors' in msg


# ── reprocess_report ──────────────────────────────────────────────────────────

def test_reprocess_report_empty_url():
    result = server.reprocess_report('')
    assert result['ok'] is False
    assert 'report_url' in result['error']


def test_reprocess_report_unrecognised_url():
    result = server.reprocess_report('/not/a/report/url')
    assert result['ok'] is False


def test_reprocess_report_no_source_doc(tmp_path, monkeypatch):
    """A valid report URL whose directory has no PDF/xlsx returns an error."""
    # Fake _source_document_path to return '' (no source doc found)
    monkeypatch.setattr(server, '_source_document_path', lambda _url: '')
    result = server.reprocess_report('/rol_finances_reports/jan-2025/stub/report.html')
    assert result['ok'] is False
    assert 'source document' in result['error'].lower()


def test_reprocess_report_delegates_to_process_pdf(tmp_path, monkeypatch):
    """When a source doc is found, reprocess_report calls process_pdf_document."""
    fake_pdf = str(tmp_path / 'statement.pdf')
    open(fake_pdf, 'w').close()

    called_with = {}

    def _fake_process_pdf(file_path, label=None, org_id=1, engine='gemini'):
        called_with['file_path'] = file_path
        called_with['label'] = label
        return {'ok': True, 'stages': [], 'file_path': file_path}

    monkeypatch.setattr(server, '_source_document_path', lambda _url: fake_pdf)
    monkeypatch.setattr(server, 'process_pdf_document', _fake_process_pdf)

    result = server.reprocess_report('/rol_finances_reports/jan-2025/stub/report.html')

    assert result['ok'] is True
    assert called_with['file_path'] == fake_pdf
    assert result['report_url'] == '/rol_finances_reports/jan-2025/stub/report.html'


# ── expense-stored event bus ──────────────────────────────────────────────────

def _clear_expense_events():
    with server._stored_expense_lock:
        server._stored_expense_events.clear()


def test_record_stored_expense_appends_event():
    _clear_expense_events()
    result = server.record_stored_expense({
        'expense_id': 42,
        'expense_date': '2025-01-07',
        'amount': '14.96',
        'vendor_key': 'goodwill_cascade',
        'description': 'Goodwill Cascade',
        'receipt_url': '/scans/scan.jpg',
    })
    assert result == {'ok': True}

    events = server.get_stored_expense_events(0.0)
    assert len(events) == 1
    assert events[0]['expense_id'] == 42
    assert events[0]['vendor_key'] == 'goodwill_cascade'
    assert 'stored_at' in events[0]
    _clear_expense_events()


def test_get_stored_expense_events_filters_by_since():
    _clear_expense_events()
    import time as _time
    server.record_stored_expense({'expense_id': 1})
    cutoff = _time.time()
    server.record_stored_expense({'expense_id': 2})

    all_events = server.get_stored_expense_events(0.0)
    assert len(all_events) == 2

    after = server.get_stored_expense_events(cutoff)
    assert len(after) == 1
    assert after[0]['expense_id'] == 2
    _clear_expense_events()
