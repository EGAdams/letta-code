"""Tests for the Server Management helpers in server.py.

These cover the pure log/registry logic (no live network): the server
registry lookup, file tailing with stable line keys, log-row filtering,
the down-status path for an unreachable health check, and the
start/"starting" lifecycle used by the executor Start button.
"""
import json
import os
import re
import time
import types
import urllib.error

import pytest
import server
# Patch targets for the model-stats internals. server.py re-exports these, but a
# re-export is a second binding -- the readers close over their own module
# global, so patching `server` would leave the real extractor running against
# the live account while the test looked like it had stubbed it.
from health import document_vision as _docvision
from health import frita as _frita
from letta_code import runner as _letta_runner
from monitoring import pc_metrics as _pc
from model_stats import reader as _stats_reader
from model_stats import usage_history as _usage_history_mod
from finance.report_page import ReportRowMatch

REAL_CREATE_MAZDA_CONVERSATION = server._create_mazda_conversation


def write_scan_image(path):
    """Write a real, decodable, clearly non-blank JPEG at `path`.

    process_scanned_document rejects anything inspect_scan_image_quality can't
    decode, so a placeholder byte string is no longer a stand-in for "a scan
    happened" — a dispatch/routing test using one would pass for the wrong
    reason (or fail for a reason it isn't testing).
    """
    from PIL import Image, ImageDraw

    img = Image.new('L', (600, 800), color=245)
    draw = ImageDraw.Draw(img)
    for offset in range(0, 800, 40):
        draw.rectangle((40, offset + 8, 560, offset + 24), fill=30)
    path = str(path)
    img.save(path, format='JPEG')
    return path


@pytest.mark.parametrize(
    ('message', 'expected_type'),
    [
        ({'message_type': 'reasoning_message', 'reasoning': 'x' * 700}, 'thought'),
        ({'message_type': 'assistant_message', 'content': 'x' * 700}, None),
        ({'message_type': 'user_message', 'content': 'x' * 700}, 'user'),
    ],
)
def test_letta_thoughts_does_not_truncate_entries(monkeypatch, message, expected_type):
    monkeypatch.setattr(server, 'letta_messages', lambda _agent_id, limit: [message])

    rows = server.letta_thoughts('agent-test')

    assert rows[0]['text'] == 'x' * 700
    if expected_type is None:
        assert 'type' not in rows[0]
    else:
        assert rows[0]['type'] == expected_type


def test_letta_thoughts_reads_isolated_conversation(monkeypatch):
    seen = {}

    def fake_get(path, timeout=0):
        seen.update(path=path, timeout=timeout)
        return [{
            'message_type': 'reasoning_message',
            'created_at': '2026-08-12T19:07:44Z',
            'reasoning': 'I am processing this Window scan.',
        }]

    monkeypatch.setattr(server, 'letta_get', fake_get)
    monkeypatch.setattr(
        server, 'letta_messages',
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError('agent-wide messages must not be used')))

    result = server.letta_thoughts('agent-mazda', 'conv-window')

    assert seen == {
        'path': '/v1/conversations/conv-window/messages?limit=80',
        'timeout': 25,
    }
    assert result == [{
        'date': '2026-08-12T19:07:44',
        'type': 'thought',
        'text': 'I am processing this Window scan.',
    }]


def test_cached_thoughts_returns_cache_while_refresh_runs(monkeypatch):
    class FakeProxy:
        def get(self, key, *args, default=None):
            assert key == ('agent-mazda', 'conv-freezer')
            assert args == ('agent-mazda', 'conv-freezer')
            return [{'text': 'cached'}]

    monkeypatch.setattr(server, '_thoughts_proxy', FakeProxy())

    started = time.monotonic()
    rows = server.cached_thoughts('agent-mazda', 'conv-freezer')

    assert time.monotonic() - started < 0.1
    assert rows == [{'text': 'cached'}]


def test_cached_thoughts_keys_full_history_by_agent(monkeypatch):
    """Two different agents with no active scan conversation (conversation_id='')
    must not share one cache entry - the old scanner-only key was just the
    conversation_id, so both fell into the same '' bucket."""
    class FakeProxy:
        def get(self, key, *args, default=None):
            return key

    monkeypatch.setattr(server, '_thoughts_proxy', FakeProxy())

    assert server.cached_thoughts('agent-mazda', '') != server.cached_thoughts('agent-suzuki', '')


def test_scanner_intake_archive_path_resolves_receipt_from_expense_row(monkeypatch):
    archived = '/archive/2025/april/receipt.jpg'
    monkeypatch.setattr(
        server, '_associated_source_paths',
        lambda _rows: ('', archived))

    result = server.scanner_intake_archive_path(
        {'doc_kind': 'receipt', 'archive_paths': []},
        [{'receipt_url': 'receipt.jpg'}])

    assert result == archived


def test_scanner_intake_archive_path_falls_back_to_db_statement_evidence(
        tmp_path, monkeypatch):
    archived = tmp_path / 'american_express_4007_may_21__june_02.jpg'
    archived.write_bytes(b'scan')
    monkeypatch.setattr(server, '_statement_archive_path', lambda *_args, **_kwargs: '')
    monkeypatch.setattr(
        server, '_associated_evidence_paths',
        lambda _rows: (str(archived), ''))

    result = server.scanner_intake_archive_path(
        {'doc_kind': 'statement', 'archive_paths': []},
        [{'scanned_statement_url': str(archived)}])

    assert result == str(archived)


def test_scanner_intake_archive_path_rejects_missing_statement_evidence(monkeypatch):
    monkeypatch.setattr(server, '_statement_archive_path', lambda *_args, **_kwargs: '')
    monkeypatch.setattr(
        server, '_associated_evidence_paths',
        lambda _rows: ('/archive/missing-statement.jpg', ''))
    monkeypatch.setattr(server, '_associated_source_paths', lambda _rows: ('', ''))

    result = server.scanner_intake_archive_path(
        {'doc_kind': 'statement', 'archive_paths': []},
        [{'scanned_statement_url': '/archive/missing-statement.jpg'}])

    assert result == ''


class _CompletedProcess:
    def __init__(self, returncode=0, stdout='', stderr=''):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _ledm_status(*categories):
    """A minimal ProductStatusDyn.xml, namespaces and all, as the DeskJet serves it."""
    body = ''.join(
        f'<pscat:StatusCategory>{c}</pscat:StatusCategory>' for c in categories)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<psdyn:ProductStatusDyn'
        ' xmlns:psdyn="http://www.hp.com/schemas/imaging/con/ledm/productstatusdyn/2007/10/31"'
        ' xmlns:pscat="http://www.hp.com/schemas/imaging/con/ledm/productstatuscategories/2007/10/31">'
        f'<psdyn:Status>{body}</psdyn:Status>'
        '</psdyn:ProductStatusDyn>'
    ).encode()


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _ready_device():
    return {'reachable': True, 'categories': ['ready'], 'blocker': None, 'note': None}


def test_fix_deskjet_printer_uses_the_working_ipv4_port(monkeypatch):
    calls = []

    def fake_runner(command, **kwargs):
        calls.append((command, kwargs))
        return _CompletedProcess(
            stdout='{"ok":true,"status":"Normal","port":"IP_10.0.0.243"}\n')

    monkeypatch.setattr(server, '_wsl_interop_socket', lambda: '/run/WSL/test_interop')

    result = server.fix_deskjet_printer(
        runner=fake_runner, device_status=_ready_device)

    assert result == {
        'ok': True,
        'text': 'Printer fixed — the printer reports it is ready. Windows status: Normal.',
        'status': 'Normal',
        'port': 'IP_10.0.0.243',
        'device_status': ['ready'],
    }
    command, kwargs = calls[0]
    assert command[0] == server._WINDOWS_POWERSHELL
    assert 'Set-Printer' in command[-1]
    assert server.DESKJET_PRINTER_NAME in command[-1]
    assert server.DESKJET_PRINTER_IP in command[-1]
    assert kwargs['env']['WSL_INTEROP'] == '/run/WSL/test_interop'


def test_fix_deskjet_printer_explains_missing_windows_interop(monkeypatch):
    monkeypatch.setattr(server, '_wsl_interop_socket', lambda: None)

    result = server.fix_deskjet_printer(
        device_status=lambda: {
            'reachable': False, 'categories': [], 'blocker': None, 'note': None})

    assert result['ok'] is False
    assert 'Open a WSL window' in result['text']


def test_fix_deskjet_printer_treats_an_empty_paper_tray_as_a_note_not_a_failure(monkeypatch):
    """These buttons live on the *scanner* dialogs — scanning needs no paper.

    Windows reports this queue as permanently 'Normal' (SNMP is off on its RAW
    port), so the device's own report is the only honest source. But an empty
    tray only stops printing; failing the repair over it would be as misleading
    as the false "Printer fixed." it replaced.
    """
    monkeypatch.setattr(server, '_wsl_interop_socket', lambda: '/run/WSL/test_interop')

    result = server.fix_deskjet_printer(
        runner=lambda command, **kwargs: _CompletedProcess(
            stdout='{"ok":true,"status":"Normal","port":"IP_10.0.0.243"}\n'),
        device_status=lambda: {
            'reachable': True,
            'categories': ['trayEmpty', 'ready'],
            'blocker': None,
            'note': 'it is out of paper (printing only — scanning works without paper)',
        },
    )

    assert result['ok'] is True
    assert 'ready to scan' in result['text']
    assert 'out of paper' in result['text']


def test_fix_deskjet_printer_fails_on_a_condition_that_stops_scanning(monkeypatch):
    """An open ink door is the known cause of a Freezer scan wedged at "busy"."""
    monkeypatch.setattr(server, '_wsl_interop_socket', lambda: '/run/WSL/test_interop')

    result = server.fix_deskjet_printer(
        runner=lambda command, **kwargs: _CompletedProcess(
            stdout='{"ok":true,"status":"Normal","port":"IP_10.0.0.243"}\n'),
        device_status=lambda: {
            'reachable': True,
            'categories': ['doorOpen'],
            'blocker': 'A door or cover is open on the printer. Close it, then try again.',
            'note': None,
        },
    )

    assert result['ok'] is False
    assert 'door or cover is open' in result['text']
    assert 'fixed' not in result['text'].lower()


def test_fix_deskjet_printer_does_not_claim_success_when_the_device_is_silent(monkeypatch):
    monkeypatch.setattr(server, '_wsl_interop_socket', lambda: '/run/WSL/test_interop')

    result = server.fix_deskjet_printer(
        runner=lambda command, **kwargs: _CompletedProcess(
            stdout='{"ok":true,"status":"Normal","port":"IP_10.0.0.243"}\n'),
        device_status=lambda: {
            'reachable': False, 'categories': [], 'blocker': None, 'note': None},
    )

    assert result['ok'] is False
    assert 'did not answer' in result['text']


def test_fix_deskjet_printer_names_the_blocker_without_windows_access(monkeypatch):
    monkeypatch.setattr(server, '_wsl_interop_socket', lambda: None)

    result = server.fix_deskjet_printer(
        device_status=lambda: {
            'reachable': True,
            'categories': ['doorOpen'],
            'blocker': 'A door or cover is open on the printer. Close it, then try again.',
            'note': None,
        })

    assert result == {
        'ok': False,
        'text': 'A door or cover is open on the printer. Close it, then try again.',
    }


def test_read_deskjet_device_status_separates_print_only_from_blocking():
    status = server.read_deskjet_device_status(
        opener=lambda url, timeout=None: _FakeResponse(_ledm_status('trayEmpty', 'ready')))

    assert status['reachable'] is True
    assert status['categories'] == ['trayEmpty', 'ready']
    assert status['blocker'] is None            # paper never blocks scanning
    assert 'out of paper' in status['note']


def test_read_deskjet_device_status_flags_a_device_wide_blocker():
    status = server.read_deskjet_device_status(
        opener=lambda url, timeout=None: _FakeResponse(_ledm_status('doorOpen')))

    assert 'door or cover is open' in status['blocker']
    assert status['note'] is None


def test_read_deskjet_device_status_ignores_non_blocking_categories():
    status = server.read_deskjet_device_status(
        opener=lambda url, timeout=None: _FakeResponse(_ledm_status('ready', 'inPowerSave')))

    assert status == {
        'reachable': True,
        'categories': ['ready', 'inPowerSave'],
        'blocker': None,
        'note': None,
    }


def test_read_deskjet_device_status_survives_an_unreachable_printer():
    def boom(url, timeout=None):
        raise OSError('no route to host')

    assert server.read_deskjet_device_status(opener=boom) == {
        'reachable': False, 'categories': [], 'blocker': None, 'note': None,
    }


@pytest.fixture(autouse=True)
def _clear_model_stats_cache(tmp_path, monkeypatch):
    """Isolate the usage-history store from the live one.

    model_stats() records rate-of-change / leak-detector snapshots, and a test
    that writes fake percentages into the real MODEL_USAGE_HISTORY_FILE would
    poison the live leak detector on this box.

    Patch the modules that own these globals, not `server`. server.py
    re-exports all three names, but a re-export is a second binding: the
    readers close over their own module global, so patching the copy on
    `server` isolates nothing while looking exactly like it does. That is the
    one failure mode this fixture cannot afford, so it is spelled out here.
    """
    from model_stats import last_good, reader, usage_history
    reader._model_stats_cache.clear()
    monkeypatch.setattr(usage_history, 'MODEL_USAGE_HISTORY_FILE',
                        str(tmp_path / 'usage_history.json'))
    monkeypatch.setattr(last_good, 'MODEL_STATS_LAST_GOOD_FILE',
                        str(tmp_path / 'model_stats_last_good.json'))
    monkeypatch.setattr(usage_history, '_usage_history', {})


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


def test_rol_finance_reports_include_amazon_marketplace():
    report = next(
        (r for r in server.ROL_FINANCE_REPORTS
         if r['key'] == 'amazon-marketplace'),
        None,
    )
    assert report is not None
    assert report['label'] == 'Amazon Marketplace'
    assert report['dir'] == 'amazon_marketplace_january_2025'
    assert report.get('all_year') is True


def test_rol_finance_months_include_march_and_april_placeholders():
    assert server.ROL_FINANCES_REPORTS_MONTHS['mar-2025'] == 'march'
    assert server.ROL_FINANCES_REPORTS_MONTHS['apr-2025'] == 'april'
    assert server.ROL_FINANCES_MONTH_RANGES['mar-2025'] == (
        '2025-03-01', '2025-03-31')
    assert server.ROL_FINANCES_MONTH_RANGES['apr-2025'] == (
        '2025-04-01', '2025-04-30')


def test_all_year_report_cards_only_appear_in_january():
    january = server._rol_finance_reports_for_month('jan-2025')
    march = server._rol_finance_reports_for_month('mar-2025')
    assert any(r.get('all_year') for r in january)
    assert not any(r.get('all_year') for r in march)
    assert {r['key'] for r in march} == {
        r['key'] for r in server.ROL_FINANCE_REPORTS if not r.get('all_year')
    }


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


def test_lookup_receipt_keeps_source_document_metadata_without_receipt(
        monkeypatch):
    source_image = (
        '/home/adamsl/rol_finances/readable_documents/bank_statements/'
        '2024/march/fubo_4851/statement.jpg'
    )
    expense = {
        'id': 1659,
        'id_light': 'meijer',
        'description': 'MEIJER STORE #311 GRAND RAPIDS MI',
        'receipt_url': '',
        'document_url': source_image,
        'moms_ledger': None,
        'notes': '',
    }
    monkeypatch.setattr(
        server, '_rol_get_connection', lambda: _FakeConnection([expense]))
    monkeypatch.setattr(
        server, '_source_document_path', lambda _report_path: '')
    monkeypatch.setattr(
        server, '_resolve_local_supporting_document',
        lambda reference, kind: source_image if kind == 'source' else None)

    result = server.lookup_receipt(
        '2024-04-02', '-47.69', 'meijer',
        'MEIJER STORE #311 GRAND RAPIDS MI', expense_id=1659,
    )

    assert result['ok'] is False
    assert result['expense_id'] == 1659
    assert result['receipt_url'] == ''
    assert result['source_document_path'] == source_image


def test_lookup_receipt_prefers_document_url_when_receipt_also_exists(
        monkeypatch):
    source_image = (
        '/home/adamsl/rol_finances/readable_documents/bank_statements/'
        '2024/march/fubo_4851/statement.jpg'
    )
    expense = {
        'id': 1659,
        'id_light': 'meijer',
        'description': 'MEIJER STORE #311 GRAND RAPIDS MI',
        'receipt_url': 'meijer_04_02_24_47_69.jpg',
        'document_url': source_image,
        'moms_ledger': None,
        'notes': '',
    }
    monkeypatch.setattr(
        server, '_rol_get_connection', lambda: _FakeConnection([expense]))
    monkeypatch.setattr(
        server, '_resolve_local_supporting_document',
        lambda reference, kind: source_image if kind == 'source' else None)
    monkeypatch.setattr(
        server, '_resolve_expense_receipt_path',
        lambda *_args: '/receipts/meijer_04_02_24_47_69.jpg')
    monkeypatch.setattr(
        server, '_source_document_path',
        lambda *_args: '/legacy/report-derived-source.pdf')

    result = server.lookup_receipt(
        '2024-04-02', '-47.69', 'meijer',
        'MEIJER STORE #311 GRAND RAPIDS MI', expense_id=1659,
    )

    assert result['ok'] is True
    assert result['source_document_path'] == source_image


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


def test_scanned_statements_present_is_scoped_to_each_matching_expense(monkeypatch):
    rows = [
        {
            'id': 1366,
            'expense_date': '2025-07-31',
            'amount': '6.24',
            'id_light': 'kfc_k980120_07_31_25_6_24',
            'description': 'KFC K980120',
            'scanned_statement_url': '',
        },
        {
            'id': 1434,
            'expense_date': '2025-08-15',
            'amount': '179.08',
            'id_light': 'country_inn_by_carlson_08_15_25_179_08',
            'description': 'COUNTRY INN & SUITES - ELKHART',
            'scanned_statement_url':
                '/scanned_statements/2025/choice_..._scan.jpg',
        },
    ]
    monkeypatch.setattr(
        server, '_rol_get_connection', lambda: _FakeConnection(rows))
    monkeypatch.setattr(
        server, '_resolve_local_supporting_document',
        lambda reference, kind: '/x.jpg' if reference and kind == 'scanned_statement' else None)

    result = server.scanned_statements_present([
        {
            'date': '2025-07-31', 'signed_amount': '-6.24',
            'vendor_key': 'kfc_k980120', 'description': 'KFC K980120',
        },
        {
            'date': '2025-08-15', 'signed_amount': '-179.08',
            'vendor_key': 'country_inn_by_carlson',
            'description': 'COUNTRY INN & SUITES - ELKHART',
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
    monkeypatch.setattr(_frita, '_probe_sdk_status', fake_probe)
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
    monkeypatch.setattr(_frita, '_probe_sdk_status', fake_probe)
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
    monkeypatch.setattr(_frita, '_probe_sdk_status', fake_probe)
    h = server.frita_executor_health(timeout=1)
    assert h['ok'] is True
    assert 'GHOST' not in h['text']


def test_frita_executor_health_self_heals_expired_creds(monkeypatch):
    # creds_present but creds_valid:False -> resync script runs, and if the
    # re-probe then reports ready, the check reports up (yellow, not red).
    calls = {'probe': 0, 'resync': 0}

    def fake_probe(url, timeout):
        if url == server.FRITA_EXEC_GOOD_URL:
            calls['probe'] += 1
            if calls['probe'] == 1:
                return {'ready': False, 'sdk_present': True, 'claude_present': True,
                        'creds_present': True, 'creds_valid': False, 'host': 'good1'}
            return {'ready': True, 'sdk_present': True, 'claude_present': True,
                    'creds_present': True, 'creds_valid': True, 'host': 'good1'}
        return None

    def fake_resync(timeout):
        calls['resync'] += 1
        return True

    monkeypatch.setattr(_frita, '_probe_sdk_status', fake_probe)
    monkeypatch.setattr(_frita, '_resync_frita_creds', fake_resync)
    h = server.frita_executor_health(timeout=1)
    assert calls['resync'] == 1
    assert calls['probe'] == 2
    assert h['ok'] is True
    assert h.get('concern') is True
    assert 'auto-resynced' in h['text']


def test_frita_executor_health_reports_down_when_resync_fails(monkeypatch):
    # Resync itself fails (e.g. local token also expiring) -> stays down, and
    # the message now names creds_valid instead of a blank "missing:" list.
    def fake_probe(url, timeout):
        if url == server.FRITA_EXEC_GOOD_URL:
            return {'ready': False, 'sdk_present': True, 'claude_present': True,
                    'creds_present': True, 'creds_valid': False, 'host': 'good1'}
        return None

    monkeypatch.setattr(_frita, '_probe_sdk_status', fake_probe)
    monkeypatch.setattr(_frita, '_resync_frita_creds', lambda timeout: False)
    h = server.frita_executor_health(timeout=1)
    assert h['ok'] is False
    assert 'creds_valid' in h['text']


def test_frita_executor_health_resync_runs_but_still_not_ready(monkeypatch):
    # Resync "succeeds" (script exit 0) but the re-probe still isn't ready
    # (e.g. remote install step failed silently) -> stays down, not a false green.
    def fake_probe(url, timeout):
        if url == server.FRITA_EXEC_GOOD_URL:
            return {'ready': False, 'sdk_present': True, 'claude_present': True,
                    'creds_present': True, 'creds_valid': False, 'host': 'good1'}
        return None

    monkeypatch.setattr(_frita, '_probe_sdk_status', fake_probe)
    monkeypatch.setattr(_frita, '_resync_frita_creds', lambda timeout: True)
    h = server.frita_executor_health(timeout=1)
    assert h['ok'] is False


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
    monkeypatch.setattr(_frita, '_probe_sdk_status', fake_probe)
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


def test_gemini_flash_fill_extractor_counts_only_todays_calls(
        monkeypatch, tmp_path, capsys):
    # 2026-08-16: replaces the old Antigravity-CLI-token-refresh test -- that
    # card now monitors the Gemini API key (GEMINI_API_KEY, what "Gemini
    # Flash Fill" spends), which has no OAuth session to refresh; it just
    # counts today's lines in parse_and_categorize.py's self-written usage
    # log (see _log_gemini_api_call in that file).
    home = tmp_path
    (home / 'rol_finances').mkdir()
    (home / 'rol_finances' / '.env').write_text('GEMINI_API_KEY=test-key-123\n')
    monkeypatch.setenv('HOME', str(home))
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    monkeypatch.delenv('GEMINI_FLASH_FILL_DAILY_LIMIT', raising=False)

    import datetime
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    log_dir = home / '.gemini'
    log_dir.mkdir()
    log_file = log_dir / 'receipt_api_usage.log'
    log_file.write_text('\n'.join(json.dumps({'ts': datetime.datetime.combine(
        d, datetime.time(12, 0)).timestamp()}) for d in (today, today, yesterday)) + '\n')

    exec(server._GEMINI_FLASH_FILL_EXTRACT_PY, {})

    result = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert result['error'] is None
    assert result['configured'] is True
    assert result['used'] == 2  # only today's two entries, not yesterday's
    assert result['limit'] == 250
    assert result['resets_at']


def test_gemini_flash_fill_extractor_reports_unconfigured_without_a_key(
        monkeypatch, tmp_path, capsys):
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)

    exec(server._GEMINI_FLASH_FILL_EXTRACT_PY, {})

    result = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert result['configured'] is False
    assert result['error']


def _codex_usage(primary, secondary=0, reached=False):
    return {'model': 'gpt-5.5', 'as_of': 1.0, 'usage': {
        'plan_type': 'plus',
        'rate_limit': {'limit_reached': reached,
                       'primary_window': {'used_percent': primary, 'reset_at': 9999999999},
                       'secondary_window': {'used_percent': secondary, 'reset_at': 9999999999}}}}


def test_model_stats_codex_red_at_100_percent(monkeypatch):
    monkeypatch.setattr(_stats_reader, '_run_extractor', lambda *a, **k: _codex_usage(100.0, 64.0))
    d = server.model_stats('w11-codex')
    assert d['status'] == 'down'              # maxed → red
    assert len(d['windows']) == 2
    assert d['windows'][0]['used_percent'] == 100.0
    assert d['windows'][0]['resets_in']      # reset shown


def test_model_stats_codex_red_when_limit_reached_flag(monkeypatch):
    monkeypatch.setattr(_stats_reader, '_run_extractor', lambda *a, **k: _codex_usage(20.0, reached=True))
    assert server.model_stats('w11-codex')['status'] == 'down'


def test_model_stats_codex_concern_when_high(monkeypatch):
    monkeypatch.setattr(_stats_reader, '_run_extractor', lambda *a, **k: _codex_usage(85.0))
    assert server.model_stats('w11-codex')['status'] == 'concern'


def test_model_stats_codex_green_when_low(monkeypatch):
    # mom's machine ~90% left == ~10% used → green
    monkeypatch.setattr(_stats_reader, '_run_extractor', lambda *a, **k: _codex_usage(10.0, 11.0))
    assert server.model_stats('r46-codex')['status'] == 'up'


def test_model_stats_codex_token_expired_is_concern_with_hint(monkeypatch):
    monkeypatch.setattr(_stats_reader, '_run_extractor', lambda *a, **k: {'model': 'gpt-5.5', 'error': 'token_expired'})
    d = server.model_stats('w11-codex')
    assert d['status'] == 'concern' and 'codex login' in d['detail']


def test_model_stats_claude_live_windows(monkeypatch):
    monkeypatch.setattr(_stats_reader, '_run_extractor', lambda *a, **k: {
        'recent_model': 'claude-opus-4-8', 'as_of': 1.0,
        'usage': {'five_hour': {'utilization': 19.0, 'resets_at': '2026-06-22T21:30:00+00:00'},
                  'seven_day': {'utilization': 12.0, 'resets_at': '2026-06-29T08:00:00+00:00'},
                  'extra_usage': {'is_enabled': False}}})
    d = server.model_stats('w11-claude')
    assert d['status'] == 'up'
    assert d['model'] == 'claude-opus-4-8'
    assert [w['used_percent'] for w in d['windows']] == [19.0, 12.0]


def test_model_stats_claude_rate_limit_keeps_last_good_bars(monkeypatch):
    responses = iter([
        {'recent_model': 'claude-opus-4-8', 'as_of': 100.0,
         'usage': {'five_hour': {'utilization': 19.0, 'resets_at': None},
                   'seven_day': {'utilization': 12.0, 'resets_at': None}}},
        {'recent_model': 'claude-opus-4-8', 'as_of': 200.0,
         'error': 'HTTP 429', 'retry_after': 60},
    ])
    monkeypatch.setattr(_stats_reader, '_run_extractor', lambda *a, **k: next(responses))
    first = server.model_stats('r46-claude')
    server._model_stats_cache.clear()
    limited = server.model_stats('r46-claude')
    assert [w['used_percent'] for w in first['windows']] == [19.0, 12.0]
    assert [w['used_percent'] for w in limited['windows']] == [19.0, 12.0]
    assert limited['windows_stale'] is True
    assert limited['usage_as_of'] == 100.0
    assert limited['rate_limited'] is True


def test_claude_extractor_names_logged_out_before_any_request(tmp_path, monkeypatch, capsys):
    """Blank tokens are a logged-out host, not a throttle.

    R46 sat with accessToken == refreshToken == "" (a `claude` logout leaves the
    file behind), so every poll sent `Authorization: Bearer ` and Anthropic's
    edge answered 429 — which the dashboard then reported as a rate limit that
    would never clear. The extractor must recognise it locally, name the
    condition, and make no request at all."""
    cred_dir = tmp_path / '.claude'
    cred_dir.mkdir()
    (cred_dir / '.credentials.json').write_text(json.dumps({'claudeAiOauth': {
        'accessToken': '', 'refreshToken': '', 'expiresAt': 0,
        'subscriptionType': 'pro'}}))
    monkeypatch.setenv('HOME', str(tmp_path))

    def fail_urlopen(*a, **k):
        raise AssertionError('logged-out host must not be probed over the network')

    monkeypatch.setattr(server.urllib.request, 'urlopen', fail_urlopen)
    with pytest.raises(SystemExit):
        exec(server._CLAUDE_EXTRACT_PY, {})

    d = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert d['condition'] == 'logged_out'
    assert 'usage' not in d


def test_model_stats_claude_logged_out_is_red_with_login_instruction(monkeypatch):
    monkeypatch.setattr(_stats_reader, '_run_extractor', lambda *a, **k: {
        'as_of': 1.0, 'condition': 'logged_out', 'error': 'logged out (no OAuth token on this host)'})
    d = server.model_stats('r46-claude')
    assert d['status'] == 'down'                    # red, not a yellow "throttled"
    assert d['logged_out'] is True
    assert not d.get('rate_limited')
    assert server.R46_SSH_HOST in d['detail']       # says WHICH host to log into
    assert 'claude' in d['detail'] and '/login' in d['detail']


def test_model_stats_claude_logged_out_does_not_show_stale_bars(monkeypatch):
    """Last-good bars are restored only for a throttle. A logged-out host has
    no live quota reading at all, so showing yesterday's bars would hide it."""
    responses = iter([
        {'as_of': 100.0, 'usage': {'five_hour': {'utilization': 19.0, 'resets_at': None},
                                   'seven_day': {'utilization': 12.0, 'resets_at': None}}},
        {'as_of': 200.0, 'condition': 'logged_out', 'error': 'logged out (no OAuth token on this host)'},
    ])
    monkeypatch.setattr(_stats_reader, '_run_extractor', lambda *a, **k: next(responses))
    server.model_stats('r46-claude')
    server._model_stats_cache.clear()
    out = server.model_stats('r46-claude')
    assert out['windows'] == []
    assert out['status'] == 'down'


def test_model_stats_codex_logged_out_reuses_shared_explanation(monkeypatch):
    """The condition is described once, not once per provider."""
    monkeypatch.setattr(_stats_reader, '_run_extractor', lambda *a, **k: {
        'model': 'gpt-5.5', 'condition': 'logged_out', 'error': 'no auth.json'})
    d = server.model_stats('w11-codex')
    assert d['status'] == 'down' and d['logged_out'] is True
    assert 'codex login' in d['detail']
    assert 'this box' in d['detail']                # local source names itself


def test_model_stats_claude_rate_limit_restores_primary_history(monkeypatch):
    with open(server.MODEL_USAGE_HISTORY_FILE, 'w', encoding='utf-8') as fh:
        json.dump({'r46-claude': [[100.0, 51.0]]}, fh)
    monkeypatch.setattr(_stats_reader, '_run_extractor', lambda *a, **k: {
        'as_of': 200.0, 'error': 'HTTP 429', 'retry_after': 60})
    limited = server.model_stats('r46-claude')
    assert limited['windows'][0]['label'] == '5-hour'
    assert limited['windows'][0]['used_percent'] == 51.0
    assert limited['windows'][1]['label'] == 'weekly'
    assert limited['windows'][1]['unavailable'] is True
    assert limited['windows_stale'] is True


def test_model_stats_claude_rate_limited_is_flagged_with_reset(monkeypatch):
    # A provider-side 429 (the R46 Claude incident, 2026-07-15) must be flagged
    # with an absolute reset epoch, not a bare yellow "usage unavailable".
    # Claude's severity is 'concern', not 'down': the usage-stats endpoint
    # throttles independently of the chat API, so Claude itself may still work
    # (see _fill_rate_limited). These two assertions were left at 'down' when
    # that severity changed, and had been failing since.
    monkeypatch.setattr(_stats_reader, '_run_extractor', lambda *a, **k: {
        'as_of': 1000.0, 'error': 'HTTP 429', 'retry_after': 2627,
        'recent_model': 'claude-opus-4-8'})
    d = server.model_stats('r46-claude')
    assert d['status'] == 'concern'
    assert d['rate_limited'] is True
    assert d['rate_limited_until'] == 1000.0 + 2627
    assert 'RATE LIMITED' in d['detail']


def test_model_stats_claude_rate_limited_without_retry_after(monkeypatch):
    monkeypatch.setattr(_stats_reader, '_run_extractor', lambda *a, **k: {
        'as_of': 1000.0, 'error': 'HTTP 429'})
    d = server.model_stats('w11-claude')
    assert d['status'] == 'concern' and d['rate_limited'] is True
    assert 'rate_limited_until' not in d
    assert 'reset time not reported' in d['detail']


def test_model_stats_codex_rate_limited_is_red(monkeypatch):
    monkeypatch.setattr(_stats_reader, '_run_extractor', lambda *a, **k: {
        'model': 'gpt-5.5', 'as_of': 500.0,
        'error': 'rate_limit_exceeded', 'retry_after': 60})
    d = server.model_stats('w11-codex')
    assert d['status'] == 'down' and d['rate_limited'] is True
    assert d['rate_limited_until'] == 560.0


def test_model_stats_claude_non_rate_limit_error_stays_concern(monkeypatch):
    monkeypatch.setattr(_stats_reader, '_run_extractor', lambda *a, **k: {
        'as_of': 1.0, 'error': 'HTTP 401'})
    d = server.model_stats('r46-claude')
    assert d['status'] == 'concern' and not d.get('rate_limited')


def test_model_stats_unknown_source():
    assert server.model_stats('nope')['ok'] is False


def test_validate_letta_code_prompt_accepts_normal_multiline_text():
    assert server.validate_letta_code_prompt('hello\r\nMazda\t!') == 'hello\nMazda\t!'


@pytest.mark.parametrize('text', ['bad\x00text', '\x1b[31mred', 'bad\x7ftext'])
def test_validate_letta_code_prompt_rejects_terminal_control_characters(text):
    with pytest.raises(ValueError, match='control characters'):
        server.validate_letta_code_prompt(text)


def test_run_letta_code_message_returns_only_final_result(monkeypatch):
    monkeypatch.setattr(_letta_runner, 'LETTA_CODE_BUN', '/home/test/.bun/bin/bun')
    monkeypatch.setattr(server.os.path, 'isfile',
                        lambda path: path == '/home/test/.bun/bin/bun')
    seen = {}

    def fake_run(argv, **kwargs):
        seen['argv'] = argv
        seen.update(kwargs)
        return server.subprocess.CompletedProcess(
            argv, 0,
            stdout=json.dumps({'result': 'The clean answer.',
                               'agent_id': 'agent-ok',
                               'conversation_id': 'conv-ok'}), stderr='')

    monkeypatch.setattr(server.subprocess, 'run', fake_run)
    agent_id = 'agent-6b536cf4-ec88-4290-b595-fed21d14bd8e'
    result = server.run_letta_code_message(agent_id, 'question?')
    assert result['reply'] == 'The clean answer.'
    assert seen['argv'][:4] == [
        '/home/test/.bun/bin/bun', 'run', 'dev', '--']
    assert '--output-format' in seen['argv'] and 'json' in seen['argv']
    assert seen['cwd'] == server.REPO_ROOT
    assert seen['timeout'] == 900
    assert seen['env']['PATH'].split(server.os.pathsep)[0] == '/home/test/.bun/bin'
    # Headless auto-denies gated tools, so without a raised permission mode the
    # agent can never apply an edit it says it made.
    argv = seen['argv']
    assert argv[argv.index('--permission-mode') + 1] == 'acceptEdits'
    # ...but never blanket bypass: this endpoint is reachable over the network.
    assert '--yolo' not in argv
    assert 'bypassPermissions' not in argv
    # No conversation_id yet: falls back to --agent, which the CLI's headless
    # path turns into a brand-new conversation.
    assert argv[argv.index('--agent') + 1] == agent_id
    assert '--conversation' not in argv


def test_run_letta_code_message_resumes_a_given_conversation(monkeypatch):
    monkeypatch.setattr(_letta_runner, 'LETTA_CODE_BUN', '/home/test/.bun/bin/bun')
    monkeypatch.setattr(server.os.path, 'isfile',
                        lambda path: path == '/home/test/.bun/bin/bun')
    seen = {}

    def fake_run(argv, **kwargs):
        seen['argv'] = argv
        return server.subprocess.CompletedProcess(
            argv, 0,
            stdout=json.dumps({'result': 'Still remember.',
                               'agent_id': 'agent-ok',
                               'conversation_id': 'conv-abc123'}), stderr='')

    monkeypatch.setattr(server.subprocess, 'run', fake_run)
    agent_id = 'agent-6b536cf4-ec88-4290-b595-fed21d14bd8e'
    result = server.run_letta_code_message(
        agent_id, 'and then?', conversation_id='conv-abc123')
    assert result['reply'] == 'Still remember.'
    argv = seen['argv']
    # --conversation derives the agent from the conversation itself, so the
    # CLI rejects it alongside --agent.
    assert argv[argv.index('--conversation') + 1] == 'conv-abc123'
    assert '--agent' not in argv


def test_letta_code_command_falls_back_to_linked_cli(monkeypatch):
    monkeypatch.setattr(_letta_runner, 'LETTA_CODE_BUN', '/missing/bun')
    monkeypatch.setattr(server.os.path, 'isfile', lambda _path: False)
    monkeypatch.setattr(
        server.shutil, 'which',
        lambda name: '/usr/local/bin/letta' if name == 'letta' else None)

    assert server._letta_code_command() == ['/usr/local/bin/letta']


def test_run_letta_headless_uses_same_working_message_path(monkeypatch):
    monkeypatch.setattr(
        server, 'run_letta_code_message',
        lambda agent, prompt, timeout: {'ok': True, 'reply': 'Fixed it.'})

    assert server.run_letta_headless('agent-live', 'repair') == {
        'ok': True, 'output': 'Fixed it.'}


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
    assert server.classify_scan_result(1, 'scanimage: device busy', False)['status'] == 'busy'


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
    assert server.SCANNERS['freezer']['airscan_device'] == 'airscan:e1:Freezer Scanner'
    assert server.SCANNERS['window']['airscan_device'] == 'airscan:e0:Window Scanner'


def _diag_by_id(result, check_id):
    return next(c for c in result['checks'] if c['id'] == check_id)


def test_scanner_diag_all_healthy_is_green():
    ps = {'stisvc': 'Running', 'stale_scans': 0,
          'hp_scan_doctor': 'Stopped', 'driver_present': True,
          'driver_status': 'OK', 'wia': 'present', 'wia_connect': 'ready'}
    r = server.build_scanner_diagnostics('window', True, ps)
    assert r['overall'] == 'ok'
    assert all(c['state'] == 'ok' for c in r['checks'])
    # No printer-device LED on the Window scanner (that's a Freezer-only LAN probe).
    assert not any(c['id'] == 'device' for c in r['checks'])


def test_scanner_diag_airscan_healthy_ignores_stale_windows_wia():
    ps = {'stisvc': 'Running', 'stale_scans': 0,
          'driver_present': True, 'driver_status': 'Unknown',
          'wia': 'absent', 'wia_connect': 'not-tested'}
    r = server.build_scanner_diagnostics(
        'window', True, ps, airscan_ready=True)
    assert r['overall'] == 'ok'
    assert all(c['state'] == 'ok' for c in r['checks'])
    assert 'directly over the network' in _diag_by_id(r, 'bridge')['detail']
    assert 'Windows WIA is not required' in _diag_by_id(r, 'service')['detail']


def test_scanner_diag_device_holder_shows_two_red_leds():
    ps = {'stisvc': 'Running', 'stale_scans': 0,
          'hp_scan_doctor': 'Running', 'driver_present': True,
          'driver_status': 'OK', 'wia': 'present', 'wia_connect': 'busy'}
    r = server.build_scanner_diagnostics('window', True, ps)
    assert _diag_by_id(r, 'hp-doctor')['state'] == 'bad'
    assert 'stop and disable' in _diag_by_id(r, 'hp-doctor')['detail'].lower()
    assert _diag_by_id(r, 'access')['state'] == 'bad'
    assert 'holding it busy' in _diag_by_id(r, 'access')['detail'].lower()
    assert r['overall'] == 'bad'


def test_scanner_diag_running_hp_doctor_is_only_warning_when_access_works():
    ps = {'stisvc': 'Running', 'stale_scans': 0,
          'hp_scan_doctor': 'Running', 'driver_present': True,
          'driver_status': 'OK', 'wia': 'present', 'wia_connect': 'ready'}
    r = server.build_scanner_diagnostics('freezer', True, ps)
    assert _diag_by_id(r, 'hp-doctor')['state'] == 'warn'
    assert _diag_by_id(r, 'access')['state'] == 'ok'
    assert r['overall'] == 'warn'


def test_scanner_diag_no_wsl_bridge_is_red_and_windows_checks_unknown():
    # The most common "reset everything" cause: no interactive WSL session for the
    # service to borrow an interop socket from. Every Windows-side LED goes grey,
    # not red — "we couldn't ask" is not "the scanner is broken".
    r = server.build_scanner_diagnostics('window', False, None)
    assert r['overall'] == 'bad'
    assert _diag_by_id(r, 'bridge')['state'] == 'bad'
    for cid in ('service', 'driver', 'online', 'stale'):
        assert _diag_by_id(r, cid)['state'] == 'unknown'


def test_scanner_diag_stisvc_stopped_is_red():
    ps = {'stisvc': 'Stopped', 'stale_scans': 0,
          'driver_present': True, 'driver_status': 'OK', 'wia': 'service-down'}
    r = server.build_scanner_diagnostics('window', True, ps)
    assert _diag_by_id(r, 'service')['state'] == 'bad'
    assert r['overall'] == 'bad'


def test_scanner_diag_driver_absent_prompts_reinstall():
    ps = {'stisvc': 'Running', 'stale_scans': 0,
          'driver_present': False, 'driver_status': 'absent', 'wia': 'absent'}
    r = server.build_scanner_diagnostics('window', True, ps)
    driver = _diag_by_id(r, 'driver')
    assert driver['state'] == 'bad'
    assert 'reinstall' in driver['detail'].lower()


def test_scanner_diag_offline_and_wia_timeout_are_red():
    off = server.build_scanner_diagnostics(
        'window', True,
        {'stisvc': 'Running', 'stale_scans': 0, 'driver_status': 'OK',
         'driver_present': True, 'wia': 'absent'})
    assert _diag_by_id(off, 'online')['state'] == 'bad'
    wedged = server.build_scanner_diagnostics(
        'window', True,
        {'stisvc': 'Running', 'stale_scans': 0, 'driver_status': 'OK',
         'driver_present': True, 'wia': 'timeout'})
    assert _diag_by_id(wedged, 'online')['state'] == 'bad'


def test_scanner_diag_stuck_scans_are_yellow():
    ps = {'stisvc': 'Running', 'stale_scans': 2,
          'driver_present': True, 'driver_status': 'OK', 'wia': 'present'}
    r = server.build_scanner_diagnostics('window', True, ps)
    assert _diag_by_id(r, 'stale')['state'] == 'warn'
    assert r['overall'] == 'warn'


def test_scanner_diag_freezer_device_blocker_is_red():
    ps = {'stisvc': 'Running', 'stale_scans': 0,
          'driver_present': True, 'driver_status': 'OK', 'wia': 'present'}
    device = {'reachable': True, 'categories': ['doorOpen'],
              'blocker': 'A door or cover is open on the printer.', 'note': None}
    r = server.build_scanner_diagnostics('freezer', True, ps, device)
    dev = _diag_by_id(r, 'device')
    assert dev['state'] == 'bad'
    assert dev['label'] == 'Scanner Hardware'
    assert dev['detail'] == device['blocker']
    assert r['overall'] == 'bad'


def test_scanner_diag_freezer_hides_print_only_status_entirely():
    ps = {'stisvc': 'Running', 'stale_scans': 0,
          'driver_present': True, 'driver_status': 'OK', 'wia': 'present'}
    device = {'reachable': True, 'categories': ['inputTrayEmpty'], 'blocker': None,
              'note': 'it is out of paper (printing only — scanning works without paper)'}
    r = server.build_scanner_diagnostics('freezer', True, ps, device)
    assert not any(check['id'] == 'device' for check in r['checks'])
    assert r['overall'] == 'ok'


def test_airscan_freezer_hides_print_only_status_entirely():
    device = {'reachable': True, 'categories': ['inputTrayEmpty'], 'blocker': None,
              'note': 'it is out of paper (printing only — scanning works without paper)'}
    r = server.build_scanner_diagnostics(
        'freezer', False, None, device, airscan_ready=True)
    assert not any(check['id'] == 'device' for check in r['checks'])
    assert r['overall'] == 'ok'


def test_scanner_diag_unknown_scanner_errors():
    r = server.build_scanner_diagnostics('nope', True, {})
    # Falls through to no checks; the wrapper is what returns the error, but a bad
    # key here should not raise.
    assert r['scanner'] == 'nope'


def test_scanner_diagnostics_wrapper_rejects_unknown_key():
    r = server.scanner_diagnostics('nope')
    assert r['overall'] == 'bad'
    assert 'error' in r
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


def test_process_scanned_document_waits_until_scanner_finishes(
        tmp_path, monkeypatch):
    scan_dir = tmp_path / 'scans'
    scan_dir.mkdir()
    (scan_dir / 'window_scan.jpg').write_bytes(b'partial scan bytes')
    monkeypatch.setattr(server, 'SCAN_TOOLS_DIR', str(scan_dir))
    monkeypatch.setattr(
        server, '_SCAN_LOCK', type('BusyLock', (), {'locked': lambda self: True})())
    facade_calls = []
    monkeypatch.setattr(
        server, 'run_intake_facade',
        lambda *args, **kwargs: facade_calls.append(args))

    result = server.process_scanned_document('window')

    assert result['ok'] is False
    assert 'still scanning' in result['error']
    assert facade_calls == []


def test_process_scanned_statement_pauses_for_missing_bank_metadata(
        tmp_path, monkeypatch):
    scan_dir = tmp_path / 'scans'
    scan_dir.mkdir()
    write_scan_image(scan_dir / 'window_scan.jpg')
    monkeypatch.setattr(server, 'SCAN_TOOLS_DIR', str(scan_dir))
    monkeypatch.setattr(server, 'SCANNERS', {
        'window': {'name': 'Window Scanner', 'output': 'window_scan.jpg'},
    })
    facade = {'ok': True, 'doc_kind': 'statement', 'confidence': .99}
    monkeypatch.setattr(server, 'run_intake_facade', lambda *a, **kw: facade)
    monkeypatch.setattr(server, 'document_vision_health', lambda: {'ok': True})
    monkeypatch.setattr(server, 'run_statement_preflight', lambda *a, **kw: {
        'ok': False,
        'needs_statement_metadata': True,
        'missing_fields': ['account_last4'],
        'bank_name': 'Chase',
        'account_last4': None,
    })
    staged = []
    monkeypatch.setattr(server, '_stage_scan_for_mazda', lambda p: staged.append(p))

    result = server.process_scanned_document('window')

    assert result['mazda_dispatched'] is False
    assert result['needs_statement_metadata'] is True
    assert result['missing_fields'] == ['account_last4']
    assert result['statement_metadata']['bank_name'] == 'Chase'
    assert staged == []


def test_process_scanned_statement_resumes_with_user_metadata(
        tmp_path, monkeypatch):
    scan_dir = tmp_path / 'scans'
    scan_dir.mkdir()
    write_scan_image(scan_dir / 'window_scan.jpg')
    monkeypatch.setattr(server, 'SCAN_TOOLS_DIR', str(scan_dir))
    monkeypatch.setattr(server, 'SCANNERS', {
        'window': {'name': 'Window Scanner', 'output': 'window_scan.jpg'},
    })
    facade = {'ok': True, 'doc_kind': 'statement', 'confidence': .99}
    monkeypatch.setattr(server, 'run_intake_facade', lambda *a, **kw: dict(facade))
    monkeypatch.setattr(server, 'document_vision_health', lambda: {'ok': True})
    captured = {}

    def _preflight(path, facade_result, metadata=None):
        captured['metadata'] = metadata
        return {
            'ok': True, 'bank_name': metadata['bank_name'],
            'account_last4': metadata['account_last4'],
            'transactions': [
                {'date': '2025-01-04', 'description': 'STORE', 'amount': -10}
            ],
        }

    monkeypatch.setattr(server, 'run_statement_preflight', _preflight)
    monkeypatch.setattr(server, '_stage_scan_for_mazda', lambda p: '/staged/window_scan.jpg')
    dispatches = []
    monkeypatch.setattr(
        server.threading, 'Thread',
        lambda target, args, daemon: dispatches.append(args) or _NoopThread())

    result = server.process_scanned_document(
        'window', statement_metadata={'bank_name': 'Chase', 'account_last4': '1234'})

    assert captured['metadata'] == {'bank_name': 'Chase', 'account_last4': '1234'}
    assert result['mazda_dispatched'] is True
    assert dispatches[0][2]['statement_preflight']['account_last4'] == '1234'


def test_process_scanned_document_doc_kind_override_skips_the_paid_classify_call(
        tmp_path, monkeypatch):
    """The 'Not a receipt -- process as statement' escape hatch: the operator
    already looked at the document (Show Image), so run_intake_facade's real
    (paid, vision-based) classify call must never run -- only
    run_statement_preflight, which still has to read the document's own
    transactions and can't be skipped."""
    scan_dir = tmp_path / 'scans'
    scan_dir.mkdir()
    write_scan_image(scan_dir / 'window_scan.jpg')
    monkeypatch.setattr(server, 'SCAN_TOOLS_DIR', str(scan_dir))
    monkeypatch.setattr(server, 'SCANNERS', {
        'window': {'name': 'Window Scanner', 'output': 'window_scan.jpg'},
    })
    facade_calls = []
    monkeypatch.setattr(
        server, 'run_intake_facade',
        lambda *a, **kw: facade_calls.append((a, kw)) or {'ok': True})
    monkeypatch.setattr(server, 'document_vision_health', lambda: {'ok': True})
    preflight_calls = []

    def _preflight(path, facade_result, metadata=None):
        preflight_calls.append(facade_result)
        return {
            'ok': True, 'bank_name': 'Chase', 'account_last4': '1234',
            'transactions': [
                {'date': '2025-01-04', 'description': 'STORE', 'amount': -10}
            ],
        }

    monkeypatch.setattr(server, 'run_statement_preflight', _preflight)
    monkeypatch.setattr(server, '_stage_scan_for_mazda', lambda p: '/staged/window_scan.jpg')
    monkeypatch.setattr(
        server.threading, 'Thread',
        lambda target, args, daemon: _NoopThread())

    result = server.process_scanned_document(
        'window', doc_kind_override='statement',
        statement_metadata={'bank_name': 'Chase', 'account_last4': '1234'})

    assert facade_calls == []
    assert preflight_calls[0]['doc_kind'] == 'statement'
    assert preflight_calls[0]['classification_method'] == 'human_override'
    assert preflight_calls[0]['parsed'] is None
    assert result['mazda_dispatched'] is True


def test_process_scanned_document_rejects_an_unsupported_doc_kind_override(
        tmp_path, monkeypatch):
    scan_dir = tmp_path / 'scans'
    scan_dir.mkdir()
    write_scan_image(scan_dir / 'window_scan.jpg')
    monkeypatch.setattr(server, 'SCAN_TOOLS_DIR', str(scan_dir))
    monkeypatch.setattr(server, 'SCANNERS', {
        'window': {'name': 'Window Scanner', 'output': 'window_scan.jpg'},
    })
    facade_calls = []
    monkeypatch.setattr(
        server, 'run_intake_facade',
        lambda *a, **kw: facade_calls.append(a) or {'ok': True})

    result = server.process_scanned_document('window', doc_kind_override='receipt')

    assert result['ok'] is False
    assert 'Unsupported doc_kind_override' in result['error']
    assert facade_calls == []


def test_process_scanned_statement_rejects_no_transactions(tmp_path, monkeypatch):
    scan_dir = tmp_path / 'scans'
    scan_dir.mkdir()
    write_scan_image(scan_dir / 'window_scan.jpg')
    monkeypatch.setattr(server, 'SCAN_TOOLS_DIR', str(scan_dir))
    monkeypatch.setattr(server, 'SCANNERS', {
        'window': {'name': 'Window Scanner', 'output': 'window_scan.jpg'},
    })
    monkeypatch.setattr(server, 'run_intake_facade', lambda *a, **kw: {
        'ok': True, 'doc_kind': 'statement', 'confidence': .99})
    monkeypatch.setattr(server, 'document_vision_health', lambda: {'ok': True})
    monkeypatch.setattr(server, 'run_statement_preflight', lambda *a, **kw: {
        'ok': False, 'rejected': True, 'needs_statement_metadata': False,
        'error': 'statement has no complete transaction',
    })

    result = server.process_scanned_document('window')

    assert result['mazda_dispatched'] is False
    assert result['statement_rejected'] is True
    assert 'complete transaction' in result['stage_error']


def test_stage_scan_for_mazda_missing_local_file_returns_none():
    assert server._stage_scan_for_mazda('/nope/does-not-exist.jpg') is None


def test_stage_scan_for_mazda_rejects_empty_scan(tmp_path):
    empty_scan = tmp_path / 'window_scan.jpg'
    empty_scan.touch()

    assert server._stage_scan_for_mazda(str(empty_scan)) is None


def test_scan_output_must_be_a_nonempty_file(tmp_path):
    scan = tmp_path / 'window_scan.jpg'
    assert server._scan_output_ready(str(scan)) is False
    scan.touch()
    assert server._scan_output_ready(str(scan)) is False
    scan.write_bytes(b'jpeg bytes')
    assert server._scan_output_ready(str(scan)) is True


def test_inspect_scan_image_quality_rejects_blank_white_page(tmp_path):
    pil = pytest.importorskip('PIL.Image')
    scan = tmp_path / 'blank.jpg'
    pil.new('RGB', (300, 400), 'white').save(scan, format='JPEG')

    result = server.inspect_scan_image_quality(str(scan))

    assert result['ok'] is False
    assert result['blank_like'] is True
    assert 'blank or unreadable' in result['reason'].lower()


def test_inspect_scan_image_quality_allows_nonblank_document_like_page(tmp_path):
    pil = pytest.importorskip('PIL.Image')
    draw = pytest.importorskip('PIL.ImageDraw')
    scan = tmp_path / 'document.jpg'
    img = pil.new('RGB', (600, 800), 'white')
    pen = draw.Draw(img)
    for y in range(60, 760, 36):
        pen.rectangle((55, y, 540, y + 6), fill='black')
    img.save(scan, format='JPEG', quality=90)

    result = server.inspect_scan_image_quality(str(scan))

    assert result['ok'] is True
    assert result['blank_like'] is False


def test_inspect_scan_image_quality_allows_a_small_receipt_on_a_full_page(tmp_path):
    """The ordinary flatbed case: a small receipt on a letter-size page.

    ~95% of that scan is genuinely blank paper, so a whole-page stddev reads
    ~6 -- under any threshold that still catches an empty sheet. Measured
    against the real archive, this shape was the single false reject a
    whole-page test produced, so it is pinned here.
    """
    pil = pytest.importorskip('PIL.Image')
    draw = pytest.importorskip('PIL.ImageDraw')
    scan = tmp_path / 'small_receipt.jpg'
    page = pil.new('L', (2550, 3508), color=255)
    pen = draw.Draw(page)
    for y in range(240, 900, 26):
        pen.rectangle((300, y, 780, y + 9), fill=40)
    page.save(scan, format='JPEG', quality=90)

    result = server.inspect_scan_image_quality(str(scan))

    assert result['ok'] is True
    assert result['blank_like'] is False


def test_process_scanned_document_rejects_blank_scan_before_mazda_dispatch(
        tmp_path, monkeypatch):
    scan = tmp_path / 'window_scan.jpg'
    scan.write_bytes(b'fake-image-bytes')
    monkeypatch.setitem(server.SCANNERS, 'window', {'output': scan.name})
    monkeypatch.setattr(server, 'SCAN_TOOLS_DIR', str(tmp_path))
    monkeypatch.setattr(server, 'inspect_scan_image_quality', lambda _path: {
        'ok': False,
        'blank_like': True,
        'reason': 'The scan appears blank or unreadable (nearly uniform page).',
    })

    result = server.process_scanned_document('window')

    assert result['ok'] is False
    assert result['mazda_dispatched'] is False
    assert result['trainer_dispatched'] is False
    assert 'blank or unreadable' in result['error'].lower()
    assert 'image_quality' in result


def test_inspect_scan_image_quality_rejects_blank_dark_page(tmp_path):
    pil = pytest.importorskip('PIL.Image')
    scan = tmp_path / 'dark.jpg'
    pil.new('RGB', (300, 400), 'black').save(scan, format='JPEG')

    result = server.inspect_scan_image_quality(str(scan))

    assert result['ok'] is False
    assert result['blank_like'] is True
    assert 'blank or unreadable' in result['reason'].lower()


def test_inspect_scan_image_quality_rejects_undecodable_file(tmp_path):
    pytest.importorskip('PIL.Image')
    scan = tmp_path / 'corrupt.jpg'
    scan.write_bytes(b'not a real image')

    result = server.inspect_scan_image_quality(str(scan))

    assert result['ok'] is False
    assert result['blank_like'] is True
    assert 'could not be decoded' in result['reason'].lower()


def test_inspect_scan_image_quality_skips_when_pillow_unavailable(monkeypatch):
    # Pillow now lives with the gate it backs, in hardware/scan_result.py.
    from hardware import scan_result
    monkeypatch.setattr(scan_result, 'Image', None)
    monkeypatch.setattr(scan_result, 'ImageStat', None)

    result = server.inspect_scan_image_quality('/tmp/does-not-matter.jpg')

    assert result['ok'] is True
    assert result['blank_like'] is False
    assert 'pillow unavailable' in result['reason'].lower()


def test_stage_scan_for_mazda_copies_locally_and_mirrors_to_win10(
        tmp_path, monkeypatch):
    """executor_run (Mazda's primary intake tool) runs on THIS box, so the scan
    must land in the local rol_finances incoming_scans; the Win10 copy is only
    a best-effort mirror for run_claude_code_sdk sessions."""
    staging_dir = tmp_path / 'incoming_scans'
    monkeypatch.setattr(server, 'SCAN_STAGING_REMOTE_DIR', str(staging_dir))
    local = tmp_path / 'scan_freezer.jpg'
    local.write_bytes(b'fake-jpeg')
    calls = []

    def _fake_run(cmd, **kwargs):
        calls.append(cmd)
        class _R:
            returncode = 0
        return _R()

    monkeypatch.setattr(server.subprocess, 'run', _fake_run)
    staged_path = server._stage_scan_for_mazda(str(local))
    staged_name = os.path.basename(staged_path)
    assert staged_path.startswith(f'{staging_dir}/scan_freezer_')
    assert staged_path.endswith('_42f114e0f62e.jpg')
    assert (staging_dir / staged_name).read_bytes() == b'fake-jpeg'
    assert calls[0][:2] == ['ssh', '-o']
    assert 'mkdir' in calls[0]
    assert calls[1][0] == 'scp'
    assert str(local) in calls[1]
    assert f'{server.SCAN_STAGING_HOST}:{staged_path}' in calls[1]


def test_stage_scan_for_mazda_ssh_failure_is_nonfatal(tmp_path, monkeypatch):
    """A dead Win10 box must not block intake — executor_run reads the local
    copy, so staging succeeds as long as the local copy lands."""
    staging_dir = tmp_path / 'incoming_scans'
    monkeypatch.setattr(server, 'SCAN_STAGING_REMOTE_DIR', str(staging_dir))
    local = tmp_path / 'window_scan.jpg'
    local.write_bytes(b'fake-jpeg')

    def _fake_run(cmd, **kwargs):
        raise server.subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(server.subprocess, 'run', _fake_run)
    staged_path = server._stage_scan_for_mazda(str(local))
    assert staged_path.startswith(f'{staging_dir}/window_scan_')
    assert os.path.exists(staged_path)


def test_stage_scan_for_mazda_returns_none_when_local_copy_fails(
        tmp_path, monkeypatch):
    monkeypatch.setattr(server, 'SCAN_STAGING_REMOTE_DIR',
                        str(tmp_path / 'staged'))
    local = tmp_path / 'window_scan.jpg'
    local.write_bytes(b'fake-jpeg')

    def _boom(src, dst):
        raise OSError('disk full')

    monkeypatch.setattr(server.shutil, 'copyfile', _boom)
    assert server._stage_scan_for_mazda(str(local)) is None


def test_process_scanned_document_dispatches_mazda_with_staged_remote_path(
        tmp_path, monkeypatch):
    """The message Mazda receives must reference the REMOTE (staged) path, not
    the local scan path her executor tools can't reach."""
    scan_dir = tmp_path / 'scans'
    scan_dir.mkdir()
    write_scan_image(scan_dir / 'window_scan.jpg')
    monkeypatch.setattr(server, 'SCAN_TOOLS_DIR', str(scan_dir))
    monkeypatch.setattr(server, 'SCANNERS', {
        'window': {'name': 'Window Scanner', 'script': 'run_scan_window.sh',
                   'output': 'window_scan.jpg'},
    })
    monkeypatch.setattr(server, 'run_intake_facade',
                         lambda *a, **kw: {'ok': True, 'doc_kind': 'unknown', 'confidence': 0})
    monkeypatch.setattr(server, 'document_vision_health', lambda *a, **kw: {'ok': True})
    monkeypatch.setattr(server, 'inspect_scan_image_quality',
                        lambda *a, **kw: {'ok': True})
    monkeypatch.setattr(server, 'inspect_scan_image_quality',
                        lambda *a, **kw: {'ok': True})
    monkeypatch.setattr(server, '_stage_scan_for_mazda',
                         lambda local_path: '/home/adamsl/rol_finances/tools/'
                                             'receipt_scanning_tools/incoming_scans/window_scan.jpg')
    captured = {}

    def _fake_thread(target, args, daemon):
        captured['args'] = args
        return _NoopThread()

    monkeypatch.setattr(server.threading, 'Thread', _fake_thread)

    result = server.process_scanned_document('window')
    assert result['mazda_dispatched'] is True
    assert captured['args'][0] == (
        '/home/adamsl/rol_finances/tools/receipt_scanning_tools/incoming_scans/window_scan.jpg')
    assert captured['args'][3] == 'conv-test-isolated'
    assert result['conversation_id'] == 'conv-test-isolated'
    assert 'stage_error' not in result


def test_window_and_freezer_dispatch_to_distinct_conversations(
        tmp_path, monkeypatch):
    """Concurrent scanners must never share Mazda context or Trainer scope."""
    scan_dir = tmp_path / 'scans'
    scan_dir.mkdir()
    write_scan_image(scan_dir / 'window_scan.jpg')
    write_scan_image(scan_dir / 'scan_freezer.jpg')
    monkeypatch.setattr(server, 'SCAN_TOOLS_DIR', str(scan_dir))
    monkeypatch.setattr(server, 'SCANNERS', {
        'window': {'name': 'Window Scanner', 'script': 'window.sh',
                   'output': 'window_scan.jpg'},
        'freezer': {'name': 'Freezer Scanner', 'script': 'freezer.sh',
                    'output': 'scan_freezer.jpg'},
    })
    monkeypatch.setattr(server, 'run_intake_facade',
                        lambda *a, **kw: {'ok': True, 'doc_kind': 'unknown'})
    monkeypatch.setattr(server, 'document_vision_health', lambda: {'ok': True})
    monkeypatch.setattr(
        server, '_stage_scan_for_mazda',
        lambda path: f'/staged/{os.path.basename(path)}')
    conversations = iter(('conv-window', 'conv-freezer'))
    monkeypatch.setattr(server, '_create_mazda_conversation',
                        lambda: next(conversations))
    mazda_dispatches = []
    trainer_watches = []

    def _fake_thread(target, args, daemon):
        mazda_dispatches.append(args)
        return _NoopThread()

    def _fake_watch(path, name, facade, conversation_id, dispatched_at):
        trainer_watches.append((name, conversation_id, dispatched_at))
        return True

    monkeypatch.setattr(server.threading, 'Thread', _fake_thread)
    monkeypatch.setattr(server, '_watch_intake_for_problems', _fake_watch)

    window = server.process_scanned_document('window')
    freezer = server.process_scanned_document('freezer')

    assert window['conversation_id'] == 'conv-window'
    assert freezer['conversation_id'] == 'conv-freezer'
    assert [args[3] for args in mazda_dispatches] == [
        'conv-window', 'conv-freezer']
    assert [(name, conv) for name, conv, _ in trainer_watches] == [
        ('Window Scanner', 'conv-window'),
        ('Freezer Scanner', 'conv-freezer'),
    ]
    assert window['trainer_dispatched'] is False
    assert freezer['trainer_dispatched'] is False
    pointer = server._read_recent_pointer_file()
    assert pointer['scanner_intakes']['Window Scanner']['conversation_id'] == 'conv-window'
    assert pointer['scanner_intakes']['Freezer Scanner']['conversation_id'] == 'conv-freezer'


def test_process_scanned_document_reports_stage_error_and_skips_mazda(
        tmp_path, monkeypatch):
    scan_dir = tmp_path / 'scans'
    scan_dir.mkdir()
    write_scan_image(scan_dir / 'window_scan.jpg')
    monkeypatch.setattr(server, 'SCAN_TOOLS_DIR', str(scan_dir))
    monkeypatch.setattr(server, 'SCANNERS', {
        'window': {'name': 'Window Scanner', 'script': 'run_scan_window.sh',
                   'output': 'window_scan.jpg'},
    })
    monkeypatch.setattr(server, 'run_intake_facade',
                         lambda *a, **kw: {'ok': True, 'doc_kind': 'unknown', 'confidence': 0})
    monkeypatch.setattr(server, 'document_vision_health', lambda *a, **kw: {'ok': True})
    monkeypatch.setattr(server, '_stage_scan_for_mazda', lambda local_path: None)
    threads_started = []
    monkeypatch.setattr(
        server.threading, 'Thread',
        lambda target, args, daemon: threads_started.append(args))

    result = server.process_scanned_document('window')
    assert result['mazda_dispatched'] is False
    assert threads_started == []
    assert 'stage_error' in result
    assert 'Mazda' in result['stage_error']


def test_process_scanned_document_fails_closed_when_conversation_creation_fails(
        tmp_path, monkeypatch):
    scan_dir = tmp_path / 'scans'
    scan_dir.mkdir()
    image = scan_dir / 'window_scan.jpg'
    write_scan_image(image)
    monkeypatch.setattr(server, 'SCAN_TOOLS_DIR', str(scan_dir))
    monkeypatch.setattr(server, 'SCANNERS', {
        'window': {'name': 'Window Scanner', 'script': 'window.sh',
                   'output': 'window_scan.jpg'},
    })
    monkeypatch.setattr(server, 'run_intake_facade',
                        lambda *a, **kw: {'ok': True, 'doc_kind': 'unknown'})
    monkeypatch.setattr(server, 'document_vision_health', lambda: {'ok': True})
    monkeypatch.setattr(server, '_stage_scan_for_mazda',
                        lambda path: '/staged/window_scan.jpg')
    monkeypatch.setattr(server, '_create_mazda_conversation', lambda: None)
    threads = []
    monkeypatch.setattr(
        server.threading, 'Thread',
        lambda *a, **k: threads.append((a, k)))

    result = server.process_scanned_document('window')

    assert result['mazda_dispatched'] is False
    assert result['trainer_dispatched'] is False
    assert 'isolated Mazda conversation' in result['stage_error']
    assert threads == []
    assert 'window' not in server._scan_dispatch_claims


def test_process_scanned_document_halts_when_vision_all_down(tmp_path, monkeypatch):
    """RED document-vision (all 3 classify_scan.py tiers down) must skip Mazda
    entirely, not just fail deep inside her trace."""
    scan_dir = tmp_path / 'scans'
    scan_dir.mkdir()
    write_scan_image(scan_dir / 'window_scan.jpg')
    monkeypatch.setattr(server, 'SCAN_TOOLS_DIR', str(scan_dir))
    monkeypatch.setattr(server, 'SCANNERS', {
        'window': {'name': 'Window Scanner', 'script': 'run_scan_window.sh',
                   'output': 'window_scan.jpg'},
    })
    monkeypatch.setattr(server, 'run_intake_facade',
                         lambda *a, **kw: {'ok': True, 'doc_kind': 'unknown', 'confidence': 0})
    monkeypatch.setattr(server, 'document_vision_health',
                         lambda *a, **kw: {'ok': False, 'text': 'ALL vision tiers down'})
    staged = []
    monkeypatch.setattr(server, '_stage_scan_for_mazda', lambda p: staged.append(p))
    threads_started = []
    monkeypatch.setattr(
        server.threading, 'Thread',
        lambda target, args, daemon: threads_started.append(args))

    result = server.process_scanned_document('window')
    assert result['mazda_dispatched'] is False
    assert result['vision_halted'] is True
    assert threads_started == []
    assert staged == []  # never even attempted to stage/dispatch
    assert 'Mazda' in result['stage_error']


def test_document_vision_health_all_tiers_down(monkeypatch, tmp_path):
    missing_env = tmp_path / '.env'
    missing_env.write_text('')
    monkeypatch.setattr(_docvision, 'ROL_FINANCES_ENV_PATH', str(missing_env))
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    monkeypatch.delenv('GOOGLE_API_KEY', raising=False)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.setattr(_docvision.os.path, 'expanduser',
                         lambda p: str(tmp_path / 'no-such-auth.json') if p == '~/.codex/auth.json' else p)

    health = server.document_vision_health()
    assert health['ok'] is False
    assert 'ALL vision tiers down' in health['text']


def test_document_vision_health_two_tiers_up_is_green_not_concern(monkeypatch, tmp_path):
    env_file = tmp_path / '.env'
    env_file.write_text('GEMINI_API_KEY=AQ.fake\n')
    monkeypatch.setattr(_docvision, 'ROL_FINANCES_ENV_PATH', str(env_file))
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    monkeypatch.delenv('GOOGLE_API_KEY', raising=False)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)

    import base64
    future_exp = int(time.time()) + 3600
    payload = base64.urlsafe_b64encode(
        json.dumps({'exp': future_exp}).encode()).decode().rstrip('=')
    fake_jwt = f'h.{payload}.s'
    auth_path = tmp_path / 'auth.json'
    auth_path.write_text(json.dumps({'tokens': {'access_token': fake_jwt}}))
    monkeypatch.setattr(_docvision.os.path, 'expanduser',
                         lambda p: str(auth_path) if p == '~/.codex/auth.json' else p)

    # Isolate the shared provider-health event log: this test pins the
    # credential-presence signal only, not fallback history.
    monkeypatch.setattr(_docvision, 'MAZDA_PROVIDER_HEALTH_PATH',
                        str(tmp_path / 'absent.json'))

    health = server.document_vision_health()
    assert health['ok'] is True
    assert not health.get('concern')


def test_document_vision_health_one_tier_up_is_concern(monkeypatch, tmp_path):
    env_file = tmp_path / '.env'
    env_file.write_text('GEMINI_API_KEY=AQ.fake\n')
    monkeypatch.setattr(_docvision, 'ROL_FINANCES_ENV_PATH', str(env_file))
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    monkeypatch.delenv('GOOGLE_API_KEY', raising=False)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.setattr(_docvision.os.path, 'expanduser',
                         lambda p: str(tmp_path / 'no-such-auth.json') if p == '~/.codex/auth.json' else p)

    health = server.document_vision_health()
    assert health['ok'] is True
    assert health.get('concern') is True


def test_categorizer_health_ignores_document_vision_entries(monkeypatch, tmp_path):
    """Vision outcomes in the shared file must not make categorizer yellow/red."""
    path = tmp_path / 'provider_health.json'
    path.write_text(json.dumps({
        'chatgpt-oauth-vision:eg': {
            'last_failure': time.time(),
            'last_failure_detail': 'vision token missing',
        },
        'chatgpt-oauth-vision:moms': {
            'last_failure': time.time(),
            'last_failure_detail': 'vision token missing',
        },
    }))
    monkeypatch.setattr(_docvision, 'MAZDA_PROVIDER_HEALTH_PATH', str(path))

    health = server.mazda_categorizer_fallback_health()

    assert health == {'ok': True, 'text': 'no categorizer LLM calls logged yet'}


def test_categorizer_health_keeps_categorizer_failure_with_vision_entries(
        monkeypatch, tmp_path):
    """Filtering unrelated entries must not hide a real categorizer failure."""
    path = tmp_path / 'provider_health.json'
    now = time.time()
    path.write_text(json.dumps({
        'chatgpt-oauth-vision:eg': {
            'last_failure': now,
            'last_failure_detail': 'vision token missing',
        },
        'gemini': {
            'last_failure': now,
            'last_failure_detail': 'gemini CLI timed out',
        },
    }))
    monkeypatch.setattr(_docvision, 'MAZDA_PROVIDER_HEALTH_PATH', str(path))

    health = server.mazda_categorizer_fallback_health()

    assert health['ok'] is False
    assert health['hard'] is True
    assert 'gemini: timeout' in health['text']


class _NoopThread:
    def start(self):
        pass


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


def test_server_health_down_for_unreachable_url():
    # Port 1 is never a real HTTP server -> down, never raises.
    health = server.server_health({'health_url': 'http://127.0.0.1:1/'})
    assert health['ok'] is False
    assert health['text']


# The starting-window and down-duration clocks, and the log-file helpers, moved
# to monitoring/server_lifecycle.py and monitoring/log_files.py. Their tests
# moved with them (tests/test_server_lifecycle.py, tests/test_log_files.py) and
# now patch the owning modules -- patching them on `server` would only rebind a
# re-export and isolate nothing. What stays here is the wiring that is genuinely
# server.py's: the six restart handlers that call mark_server_starting().


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
        'itemize_existing_expense',
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
    # The whole Mazda fleet (her + her 5 minions) moved to the shared
    # claude-pro-max OAuth provider (this box's Claude subscription token,
    # never an ANTHROPIC_API_KEY); Suzuki's fleet stays on chatgpt-plus-pro.
    mazda_fleet_names = {
        'Mazda', 'Mazda Router', 'Mazda Parser', 'Mazda Vendor Identity',
        'Mazda Receipt Linker', 'Mazda Categorization',
    }
    for cfg in server.LETTA_AGENTS:
        if cfg['name'] in mazda_fleet_names:
            assert cfg.get('llm_provider') == server.CLAUDE_PRO_MAX, cfg['name']


def test_provider_agent_ids_returns_real_ids_for_tagged_agents():
    ids = server._provider_agent_ids(server.CHATGPT_PLUS_PRO)
    # Suzuki fleet only (7); the whole Mazda fleet moved to claude-pro-max
    assert len(ids) == 7
    mazda = next(cfg for cfg in server.LETTA_AGENTS if cfg['name'] == 'Mazda')
    assert mazda['id'] not in ids
    suzuki = next(cfg for cfg in server.LETTA_AGENTS if cfg['name'] == 'Suzuki')
    assert suzuki['id'] in ids


def test_mazda_fleet_tagged_with_claude_pro_max_provider():
    ids = set(server._provider_agent_ids(server.CLAUDE_PRO_MAX))
    mazda_fleet_names = {
        'Mazda', 'Mazda Router', 'Mazda Parser', 'Mazda Vendor Identity',
        'Mazda Receipt Linker', 'Mazda Categorization',
    }
    expected = {cfg['id'] for cfg in server.LETTA_AGENTS if cfg['name'] in mazda_fleet_names}
    assert ids == expected
    assert len(ids) == 6


def _patch_provider_probe(monkeypatch, probe_result, calls=None):
    """Route the poll at a fake provider token + probe (no network, no LLM)."""
    monkeypatch.setattr(server, '_fetch_provider_oauth_creds',
                        lambda name: ({'access_token': 't', 'account_id': 'a'}, 'chatgpt_oauth'))

    def fake_probe(creds, timeout=20):
        if calls is not None:
            calls.append(creds)
        return probe_result
    monkeypatch.setitem(server.PROVIDER_USAGE_PROBES, 'chatgpt_oauth', fake_probe)


def test_poll_chatgpt_provider_once_flags_every_fleet_agent_on_429(monkeypatch):
    _patch_provider_probe(monkeypatch, {'ok': False, 'text': 'llm_rate_limit: too many requests'})
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
    _patch_provider_probe(monkeypatch, {'ok': True, 'text': '5h 37% / weekly 44%'})
    server._poll_chatgpt_provider_once()
    for agent_id in server._provider_agent_ids(server.CHATGPT_PLUS_PRO):
        with server._agent_send_errors_lock:
            assert server._agent_send_errors.get(agent_id) is None, agent_id


def test_poll_chatgpt_provider_once_makes_one_usage_call_and_no_llm_calls(monkeypatch):
    # One usage-API call covers the whole fleet. The probe must NEVER message an
    # agent — the old 'ping' canary burned ~40 full-context LLM calls per hour
    # against the very quota it was watching (2026-07-07).
    calls = []
    _patch_provider_probe(monkeypatch, {'ok': True, 'text': ''}, calls=calls)

    def _no_llm(*a, **k):
        raise AssertionError('probe must not POST to any agent')
    monkeypatch.setattr(server.urllib.request, 'urlopen', _no_llm)
    server._poll_chatgpt_provider_once()
    assert len(calls) == 1


def test_poll_skips_sweep_when_letta_api_unreachable(monkeypatch):
    # Letta down ≠ quota exhausted: leave agent state alone (Server Management
    # owns the server-down signal), and definitely don't crash the loop.
    def _boom(name):
        raise OSError('connection refused')
    monkeypatch.setattr(server, '_fetch_provider_oauth_creds', _boom)
    server.record_agent_send_error('agent-keep', 'pre-existing error')
    server._poll_chatgpt_provider_once()
    with server._agent_send_errors_lock:
        assert server._agent_send_errors.get('agent-keep') is not None
    server.clear_agent_send_error('agent-keep')


def test_classify_codex_usage_ok_under_limit():
    usage = {'rate_limit': {'allowed': True, 'limit_reached': False,
                            'primary_window': {'used_percent': 37, 'reset_at': 4102444800},
                            'secondary_window': {'used_percent': 44, 'reset_at': 4102444800}}}
    r = server._classify_codex_usage(usage)
    assert r['ok'] is True
    assert '5h 37%' in r['text'] and 'weekly 44%' in r['text']


def test_classify_codex_usage_flags_maxed_window_as_rate_limit():
    usage = {'rate_limit': {'allowed': True, 'limit_reached': False,
                            'primary_window': {'used_percent': 100, 'reset_at': 4102444800}}}
    r = server._classify_codex_usage(usage)
    assert r['ok'] is False
    assert r['text'].startswith('llm_rate_limit:')
    assert server.classify_failure(r['text'])[1] == 'rate-limited'


def test_codex_window_label_uses_the_declared_duration():
    assert server.codex_window_label({'limit_window_seconds': 18000}, '?') == '5h'
    assert server.codex_window_label({'limit_window_seconds': 604800}, '?') == 'weekly'
    assert server.codex_window_label({'limit_window_seconds': 86400}, '?') == '1d'
    # No duration in the payload — keep the positional name rather than guess.
    assert server.codex_window_label({}, '5h') == '5h'


def test_classify_codex_usage_labels_a_weekly_primary_window_weekly():
    # The 2026-08-19 shape: one primary window that is actually 7 days long.
    usage = {'rate_limit': {'allowed': False, 'limit_reached': True,
                            'primary_window': {'used_percent': 100, 'reset_at': 4102444800,
                                               'limit_window_seconds': 604800},
                            'secondary_window': None}}
    r = server._classify_codex_usage(usage)
    assert r['ok'] is False
    assert 'weekly window 100% used' in r['text']
    assert '5h window' not in r['text']


def test_classify_codex_usage_respects_limit_reached_flag():
    usage = {'rate_limit': {'allowed': False, 'limit_reached': True,
                            'primary_window': {'used_percent': 63, 'reset_at': 4102444800}}}
    r = server._classify_codex_usage(usage)
    assert r['ok'] is False and 'llm_rate_limit' in r['text']


def test_classify_claude_usage_contract():
    ok = server._classify_claude_usage({'five_hour': {'utilization': 12, 'resets_at': None},
                                        'seven_day': {'utilization': 80, 'resets_at': None}})
    assert ok['ok'] is True
    maxed = server._classify_claude_usage({'five_hour': {'utilization': 100, 'resets_at': None},
                                           'seven_day': {'utilization': 55, 'resets_at': None}})
    assert maxed['ok'] is False and maxed['text'].startswith('llm_rate_limit:')


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


_FAIL_REPORT_HTML = '''
<section class="hero">
  <div class="badge">⚠️ FAIL - Math verified, DB/category issues remain</div>
</section>
<section class="card">
  <h2>Overall Result</h2>
  <div class="summary-box"><strong>FAIL</strong> - one deposit is not traceable
  to a persisted DB row and several categories need review.</div>
</section>
<section class="card">
  <h2>Verification Summary</h2>
  <table><tbody><tr><td>Source PDF read</td>
  <td class="center"><span class="status-pass">PASS</span></td></tr></tbody></table>
</section>
<section class="card">
  <h2>Expense Category Verification</h2>
  <p><span class="status-warn">REVIEW NEEDED</span> Several rows still use broad
  <code class="inline-code">Personal</code> categories.</p>
</section>
<section class="card">
  <h2>Final Verification Status</h2>
  <p><strong>Required next action:</strong> decide whether the broad Personal
  categories are acceptable policy outcomes.</p>
</section>
'''


def test_extract_report_failure_detail(tmp_path):
    p = tmp_path / 'report.html'
    p.write_text(_FAIL_REPORT_HTML)
    d = server._extract_report_failure_detail(str(p))
    assert d['badge'] == '⚠️ FAIL - Math verified, DB/category issues remain'
    assert 'not traceable' in d['summary']
    # Only the non-PASS section is listed as remaining work, with the status
    # pill's label pulled out of the paragraph text.
    assert len(d['issues']) == 1
    issue = d['issues'][0]
    assert issue['section'] == 'Expense Category Verification'
    assert issue['status'] == 'REVIEW NEEDED'
    assert issue['text'].startswith('Several rows')
    assert 'REVIEW NEEDED' not in issue['text']
    assert d['recommended_action'].startswith('decide whether')


def test_extract_report_attention_detail_supports_review_reports(tmp_path):
    p = tmp_path / 'report.html'
    p.write_text(_FAIL_REPORT_HTML.replace('FAIL', 'REVIEW NEEDED'))
    d = server._extract_report_attention_detail(str(p))
    assert d['badge'].startswith('⚠️ REVIEW NEEDED')
    assert d['recommended_action'].startswith('decide whether')


def test_extract_report_failure_detail_missing_file(tmp_path):
    assert server._extract_report_failure_detail(str(tmp_path / 'absent.html')) is None


def test_extract_report_failure_detail_empty_report(tmp_path):
    p = tmp_path / 'report.html'
    p.write_text('<html><body>nothing recognizable</body></html>')
    assert server._extract_report_failure_detail(str(p)) is None


def _setup_recent_reports_fixture(tmp_path, monkeypatch, reports):
    """reports: list of (month_key, report_key, label, dir_name, badge_text, mtime)."""
    monkeypatch.setattr(server, 'ROL_FINANCES_REPORTS_PARENT', str(tmp_path))
    months = {}
    by_key = {}
    for month_key, report_key, label, dir_name, badge_text, mtime in reports:
        months[month_key] = month_key  # sub-dir name == month_key for simplicity
        by_key[(month_key, report_key)] = (label, dir_name)
        report_dir = tmp_path / month_key / dir_name
        report_dir.mkdir(parents=True, exist_ok=True)
        report_file = report_dir / 'report.html'
        report_file.write_text(
            f'<section class="hero"><div class="badge">{badge_text}</div></section>')
        if mtime is not None:
            os.utime(report_file, (mtime, mtime))
    monkeypatch.setattr(server, 'ROL_FINANCES_REPORTS_MONTHS', months)
    seen_dirs = set()
    flat_reports = []
    for (month_key, report_key), (label, dir_name) in by_key.items():
        if dir_name in seen_dirs:
            continue
        seen_dirs.add(dir_name)
        flat_reports.append({'key': report_key, 'label': label, 'dir': dir_name})
    monkeypatch.setattr(server, 'ROL_FINANCE_REPORTS', flat_reports)


def test_recent_reports_prioritizes_needs_attention_over_recency(tmp_path, monkeypatch):
    _setup_recent_reports_fixture(tmp_path, monkeypatch, [
        ('jan-2025', 'old-fail', 'Old Fail', 'old-fail-dir', 'FAIL - bad', 100),
        ('jan-2025', 'new-pass', 'New Pass', 'new-pass-dir', 'PASS - good', 200),
    ])
    result = server._rol_finance_recent_reports(limit=5)
    assert [item['key'] for item in result['items']] == ['old-fail', 'new-pass']
    # Latest by recency regardless of status.
    assert result['latest']['key'] == 'new-pass'


def test_recent_reports_within_a_tier_sorts_by_recency(tmp_path, monkeypatch):
    _setup_recent_reports_fixture(tmp_path, monkeypatch, [
        ('jan-2025', 'older-review', 'Older Review', 'older-review-dir', 'REVIEW NEEDED', 100),
        ('jan-2025', 'newer-review', 'Newer Review', 'newer-review-dir', 'REVIEW NEEDED', 200),
    ])
    result = server._rol_finance_recent_reports(limit=5)
    assert [item['key'] for item in result['items']] == ['newer-review', 'older-review']


def test_recent_reports_respects_limit(tmp_path, monkeypatch):
    _setup_recent_reports_fixture(tmp_path, monkeypatch, [
        ('jan-2025', f'r{i}', f'Report {i}', f'r{i}-dir', 'PASS - good', float(i))
        for i in range(8)
    ])
    result = server._rol_finance_recent_reports(limit=5)
    assert len(result['items']) == 5
    # Newest-first among equal-priority (all 'pass') candidates.
    assert [item['key'] for item in result['items']] == ['r7', 'r6', 'r5', 'r4', 'r3']


def test_recent_reports_skips_reports_with_no_file_on_disk(tmp_path, monkeypatch):
    monkeypatch.setattr(server, 'ROL_FINANCES_REPORTS_PARENT', str(tmp_path))
    monkeypatch.setattr(server, 'ROL_FINANCES_REPORTS_MONTHS', {'jan-2025': 'jan-2025'})
    monkeypatch.setattr(server, 'ROL_FINANCE_REPORTS', [
        {'key': 'missing', 'label': 'Missing', 'dir': 'missing-dir'},
    ])
    result = server._rol_finance_recent_reports(limit=5)
    assert result == {'latest': None, 'items': []}


def test_recent_reports_needs_attention_flag_matches_status(tmp_path, monkeypatch):
    _setup_recent_reports_fixture(tmp_path, monkeypatch, [
        ('jan-2025', 'pass-doc', 'Pass Doc', 'pass-doc-dir', 'PASS - good', 100),
        ('jan-2025', 'review-doc', 'Review Doc', 'review-doc-dir', 'REVIEW NEEDED', 200),
    ])
    result = server._rol_finance_recent_reports(limit=5)
    by_key = {item['key']: item for item in result['items']}
    assert by_key['pass-doc']['needs_attention'] is False
    assert by_key['review-doc']['needs_attention'] is True


def _ssh_cfg():
    return {'key': '__test_ssh_conn', 'name': 'Test Conn', 'host': '0.0.0.0', 'user': 'nobody'}


@pytest.mark.parametrize('identity_key', ['identity_files', 'identity_file'])
def test_ssh_test_uses_configured_identity_file(monkeypatch, tmp_path, identity_key):
    """`identity_files` is the current contract; the singular `identity_file`
    key is still accepted for older connection configs, so both must reach the
    same `-i` invocation."""
    identity = tmp_path / 'id_ed25519'
    identity.write_text('test key')
    calls = []

    def fake_run(cmd, **_kwargs):
        calls.append(cmd)
        return type('Result', (), {
            'returncode': 0,
            'stdout': 'CONNECTED\nDESKTOP-SHDBATI\n',
            'stderr': '',
        })()

    monkeypatch.setattr(server.subprocess, 'run', fake_run)
    cfg_value = (str(identity),) if identity_key == 'identity_files' else str(identity)
    result = server.ssh_test({**_ssh_cfg(), identity_key: cfg_value}, timeout=5)

    assert result['ok'] is True
    assert calls == [[
        'ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes',
        '-o', 'StrictHostKeyChecking=accept-new', '-o', 'IdentitiesOnly=yes',
        '-i', str(identity), 'nobody@0.0.0.0', 'echo CONNECTED && hostname',
    ]]


def test_ssh_test_falls_through_a_dead_preferred_key_to_a_working_one(monkeypatch, tmp_path):
    # A key can exist on disk but no longer be authorized on the remote end
    # (rotated/revoked). Picking "the first file that exists" would wedge on
    # that dead key forever even though a later one in the list still works.
    dead = tmp_path / 'id_dead'
    dead.write_text('dead key')
    live = tmp_path / 'id_live'
    live.write_text('live key')
    calls = []

    def fake_run(cmd, **_kwargs):
        calls.append(cmd)
        if str(dead) in cmd:
            return type('Result', (), {
                'returncode': 255,
                'stdout': '',
                'stderr': 'nobody@0.0.0.0: Permission denied (publickey).',
            })()
        return type('Result', (), {
            'returncode': 0,
            'stdout': 'CONNECTED\nDESKTOP-SHDBATI\n',
            'stderr': '',
        })()

    monkeypatch.setattr(server.subprocess, 'run', fake_run)
    result = server.ssh_test(
        {**_ssh_cfg(), 'identity_files': (str(dead), str(live))}, timeout=5,
    )

    assert result['ok'] is True
    assert len(calls) == 2  # tried the dead key first, then fell through to the live one


def test_ssh_test_reports_the_last_failure_when_every_identity_fails(monkeypatch, tmp_path):
    dead = tmp_path / 'id_dead'
    dead.write_text('dead key')

    def fake_run(cmd, **_kwargs):
        return type('Result', (), {
            'returncode': 255,
            'stdout': '',
            'stderr': 'nobody@0.0.0.0: Permission denied (publickey).',
        })()

    monkeypatch.setattr(server.subprocess, 'run', fake_run)
    result = server.ssh_test({**_ssh_cfg(), 'identity_files': (str(dead),)}, timeout=5)

    assert result['ok'] is False
    assert 'Permission denied' in result['text']


def test_tailscale_test_accepts_ping_when_status_is_stale_offline(monkeypatch):
    calls = []
    monkeypatch.setattr(server, '_tailscale_cli', lambda: 'tailscale')

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
    monkeypatch.setattr(server, '_tailscale_cli', lambda: 'tailscale')

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


def test_tailscale_cli_falls_back_to_windows_host_client(monkeypatch):
    def fake_which(name):
        if name == 'tailscale.exe':
            return '/mnt/c/Program Files/Tailscale/tailscale.exe'
        return None

    monkeypatch.setattr(server.shutil, 'which', fake_which)

    assert server._tailscale_cli() == '/mnt/c/Program Files/Tailscale/tailscale.exe'


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


# ── ROL Finance: receipt presence on a Verified-Transactions row ───────────
# The category write itself, its undo and the report-row repaint moved to
# finance/recategorize.py -- tests/test_recategorize.py owns them, pointed at
# that module rather than at this one. What stays here is receipts_present,
# which shares the same ±1-3 day credit-card posting-date tolerance: a DB
# expense dated before the report row must still resolve as present.

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


def _write_verified_row(report_dir, vendor_key, date_str, amount_str, cls='cat-uncategorized'):
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / 'report.html').write_text(
        f'<table><tbody>\n'
        f'<tr class="{cls}" data-vendor-key="{vendor_key}" onclick="openCategoryPicker(this)">'
        f'<td>DESC</td><td class="number">{amount_str}</td><td>{date_str}</td></tr>\n'
        f'</tbody></table>',
        encoding='utf-8',
    )


def test_find_matching_report_row_ignores_vendor_key_mismatch(tmp_path, monkeypatch):
    """The report's own vendor_key ('..._walker') need not match the DB's
    ('kum_go_2608r') — date+amount alone must be enough to find the row."""
    monkeypatch.setattr(server, 'ROL_FINANCES_REPORTS_PARENT', str(tmp_path))
    monkeypatch.setattr(server, 'ROL_FINANCES_REPORTS_MONTHS', {'feb-2025': 'february'})
    monkeypatch.setattr(server, 'ROL_FINANCES_REPORTS_DEFAULT_MONTH', 'feb-2025')
    monkeypatch.setattr(server, 'ROL_FINANCE_REPORTS', [
        {'key': 'platinum-year', 'label': 'Platinum Year', 'dir': 'platinum_year'},
    ])
    _write_verified_row(tmp_path / 'february' / 'platinum_year', 'kum_go_2608r_walker',
                         '2025-04-03', '28.10')

    found = server._find_matching_report_row('2025-04-03', '28.10', 'kum_go_2608r')

    assert found is not None
    assert found.label == 'Platinum Year'
    assert found.row_vendor_key == 'kum_go_2608r_walker'
    assert found.report_path == '/rol_finances_reports/feb-2025/platinum_year/report.html'


def test_find_matching_report_row_returns_none_when_no_row_matches(tmp_path, monkeypatch):
    monkeypatch.setattr(server, 'ROL_FINANCES_REPORTS_PARENT', str(tmp_path))
    monkeypatch.setattr(server, 'ROL_FINANCES_REPORTS_MONTHS', {'feb-2025': 'february'})
    monkeypatch.setattr(server, 'ROL_FINANCES_REPORTS_DEFAULT_MONTH', 'feb-2025')
    monkeypatch.setattr(server, 'ROL_FINANCE_REPORTS', [
        {'key': 'platinum-year', 'label': 'Platinum Year', 'dir': 'platinum_year'},
    ])
    _write_verified_row(tmp_path / 'february' / 'platinum_year', 'someone_else',
                         '2025-04-03', '28.10')

    found = server._find_matching_report_row('2025-01-01', '999.00', 'kum_go_2608r')
    assert found is None


def test_find_matching_report_row_ambiguous_without_vendor_hint_returns_none(tmp_path, monkeypatch):
    """Same date+amount in two different reports, and vendor_key doesn't narrow it
    down — must not guess which report to patch."""
    monkeypatch.setattr(server, 'ROL_FINANCES_REPORTS_PARENT', str(tmp_path))
    monkeypatch.setattr(server, 'ROL_FINANCES_REPORTS_MONTHS', {'feb-2025': 'february'})
    monkeypatch.setattr(server, 'ROL_FINANCES_REPORTS_DEFAULT_MONTH', 'feb-2025')
    monkeypatch.setattr(server, 'ROL_FINANCE_REPORTS', [
        {'key': 'a', 'label': 'Report A', 'dir': 'report_a'},
        {'key': 'b', 'label': 'Report B', 'dir': 'report_b'},
    ])
    _write_verified_row(tmp_path / 'february' / 'report_a', 'vendor_a', '2025-04-03', '28.10')
    _write_verified_row(tmp_path / 'february' / 'report_b', 'vendor_b', '2025-04-03', '28.10')

    found = server._find_matching_report_row('2025-04-03', '28.10', 'unrelated_vendor')
    assert found is None


def test_find_matching_report_row_disambiguates_via_vendor_key_prefix(tmp_path, monkeypatch):
    monkeypatch.setattr(server, 'ROL_FINANCES_REPORTS_PARENT', str(tmp_path))
    monkeypatch.setattr(server, 'ROL_FINANCES_REPORTS_MONTHS', {'feb-2025': 'february'})
    monkeypatch.setattr(server, 'ROL_FINANCES_REPORTS_DEFAULT_MONTH', 'feb-2025')
    monkeypatch.setattr(server, 'ROL_FINANCE_REPORTS', [
        {'key': 'a', 'label': 'Report A', 'dir': 'report_a'},
        {'key': 'b', 'label': 'Report B', 'dir': 'report_b'},
    ])
    _write_verified_row(tmp_path / 'february' / 'report_a', 'kum_go_2608r_walker', '2025-04-03', '28.10')
    _write_verified_row(tmp_path / 'february' / 'report_b', 'someone_unrelated', '2025-04-03', '28.10')

    found = server._find_matching_report_row('2025-04-03', '28.10', 'kum_go_2608r')
    assert found is not None
    assert found.label == 'Report A'


class _FakeVendorLookup:
    def __init__(self, vendor_keys=None, category_id=None):
        self._vendor_keys = vendor_keys or []
        self._category_id = category_id

    def list_vendor_keys(self):
        return self._vendor_keys

    def get_category_id(self, vendor_key):
        return self._category_id


def test_list_vendor_keys_returns_lookup_results(monkeypatch):
    vendor_keys = [{'vendor_key': 'costco', 'category_id': 130, 'category_name': 'Food & Hospitality'}]
    monkeypatch.setattr(server, '_vendor_category_lookup', lambda: _FakeVendorLookup(vendor_keys))

    result = server.list_vendor_keys()

    assert result == {'ok': True, 'vendor_keys': vendor_keys}


def test_list_vendor_keys_reports_load_failure(monkeypatch):
    def _boom():
        raise RuntimeError('yaml missing')
    monkeypatch.setattr(server, '_vendor_category_lookup', _boom)

    result = server.list_vendor_keys()

    assert result['ok'] is False
    assert 'yaml missing' in result['error']
    assert result['vendor_keys'] == []


def test_list_pending_vendor_review_builds_image_url(tmp_path, monkeypatch):
    receipt_file = tmp_path / 'bjs_05_10_26_40_77.jpg'
    receipt_file.write_bytes(b'image')
    row = {
        'id': 321, 'expense_date': '2026-05-10', 'amount': '40.77',
        'description': "BJ's Restaurant", 'receipt_url': 'bjs_05_10_26_40_77.jpg',
        'source_file': str(receipt_file),
    }
    monkeypatch.setattr(server, '_rol_get_connection', lambda: _FakeConnection([row]))
    monkeypatch.setattr(server, '_receipt_url_for_path', lambda fp: '/rol_finances_receipts/' + os.path.basename(fp))

    result = server.list_pending_vendor_review()

    assert result['ok'] is True
    assert result['rows'] == [{
        'expense_id': 321, 'expense_date': '2026-05-10', 'amount': '40.77',
        'description': "BJ's Restaurant", 'receipt_url': 'bjs_05_10_26_40_77.jpg',
        'image_url': '/rol_finances_receipts/bjs_05_10_26_40_77.jpg',
    }]


def test_list_pending_vendor_review_missing_file_has_no_image_url(monkeypatch):
    row = {
        'id': 321, 'expense_date': '2026-05-10', 'amount': '40.77',
        'description': "BJ's Restaurant", 'receipt_url': 'bjs.jpg',
        'source_file': '/does/not/exist.jpg',
    }
    monkeypatch.setattr(server, '_rol_get_connection', lambda: _FakeConnection([row]))

    result = server.list_pending_vendor_review()

    assert result['ok'] is True
    assert result['rows'][0]['image_url'] is None


def test_set_receipt_vendor_resolves_category_and_updates(monkeypatch):
    monkeypatch.setattr(server, '_vendor_category_lookup', lambda: _FakeVendorLookup(category_id=130))
    conn = _FakeConnection([])
    monkeypatch.setattr(server, '_rol_get_connection', lambda: conn)

    result = server.set_receipt_vendor(321, 'costco')

    assert result == {'ok': True, 'expense_id': 321, 'category_id': 130}


def test_set_receipt_vendor_rejects_unknown_vendor_key(monkeypatch):
    monkeypatch.setattr(server, '_vendor_category_lookup', lambda: _FakeVendorLookup(category_id=None))

    result = server.set_receipt_vendor(321, 'totally_unknown')

    assert result == {'ok': False, 'error': 'Unknown vendor_key: totally_unknown'}


def test_set_receipt_vendor_rejects_bad_expense_id(monkeypatch):
    result = server.set_receipt_vendor('not-an-int', 'costco')

    assert result['ok'] is False
    assert 'Bad expense_id' in result['error']


def test_set_receipt_vendor_requires_vendor_key():
    result = server.set_receipt_vendor(321, '')

    assert result == {'ok': False, 'error': 'vendor_key is required'}


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
    assert '--write-parsed-json /tmp/mazda_receipt_' in msg
    assert '--parsed-json /tmp/mazda_receipt_' in msg
    assert 'Do not run receipt vision a second time' in msg
    artifact_out = re.search(
        r'--write-parsed-json (/tmp/mazda_receipt_[a-f0-9]+\.json)', msg
    ).group(1)
    artifact_in = re.search(
        r'--parsed-json (/tmp/mazda_receipt_[a-f0-9]+\.json)', msg
    ).group(1)
    assert artifact_in == artifact_out
    assert 'HARD ROUTING BARRIER' in msg
    assert 'Never chain the classifier to a parser or store command' in msg
    assert 'If doc_type is `bank_statement` or `statement`, STOP STEP 0 HERE' in msg
    assert 'ONLY for receipt OR invoice, parse in a NEW executor_run call' in msg
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


def test_scan_message_fails_closed_on_unresolved_vendor_or_category():
    """An unresolved vendor/category no longer drops the receipt: STEP 4 still
    runs (without --category-id) so the image + a NEEDS_VENDOR_KEY placeholder
    row get saved for a human to categorize later."""
    msg = server.build_mazda_scan_message('/scans/x.jpg', 'Scanner', _FACADE_JPEG_UNKNOWN)
    assert 'FAIL-CLOSED CATEGORY RULE' in msg
    assert 'STILL run STEP 4 but OMIT --category-id entirely' in msg
    assert 'NEEDS_VENDOR_KEY' in msg
    assert 'awaiting_vendor_review' in msg
    assert 'final duplicate guard using the SAME validated' in msg
    assert 'Never retry with --allow-duplicate' in msg
    assert 'parse_artifact_verified=true' in msg
    assert 'duplicate at a different amount or scope is not proof' in msg
    assert 'Store EVEN IF category_id' not in msg


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


def test_scan_message_routes_statements_to_statement_pipeline():
    """Statements can never complete the receipt STEPS 2-4 (three identical
    stall-after-classification runs on 2026-07-10 proved it), so the message
    must carry an explicit statement branch: vision parse → dedupe+store,
    then the STATEMENT evidence contract the statement rubric judges."""
    msg = server.build_mazda_scan_message('/scans/x.jpg', 'Scanner', _FACADE_IDENTIFIED)
    assert 'STATEMENT BRANCH' in msg
    assert 'tools/receipt_scanning_tools/parse_statement_scan.py' in msg
    assert 'tools/receipt_scanning_tools/store_statement_transactions.py' in msg
    # Statement evidence fields the statement-aware intake rubric reads.
    for field in ('transactions_parsed', 'transactions_stored',
                  'transactions_duplicate', 'transactions_skipped_credits',
                  'deposits_stored'):
        assert f'"{field}"' in msg, f'statement field {field!r} missing from message'
    # After store, EG's handwritten category notes must be applied — the vendor
    # lookup can't tell Rosemary's charge from Robert's, only his pen can.
    assert 'apply_statement_annotations.py' in msg


def test_scan_message_routes_moms_ledger_to_category_reconciliation():
    msg = server.build_mazda_scan_message(
        '/scans/moms-ledger.jpg', 'Window Scanner', _FACADE_JPEG_UNKNOWN
    )

    assert 'MOM LEDGER BRANCH' in msg
    assert 'moms_ledger_reconciler.py --image /scans/moms-ledger.jpg' in msg
    assert 'supported category evidence' in msg
    assert 'never flatten a correct specific category back to generic 190' in msg
    assert 'OpenAI Codex CLI' in msg
    assert 'doc_kind="moms_ledger"' in msg
    assert 'do not run receipt or statement storage' in msg


def test_scan_message_distinguishes_annotated_statement_from_moms_ledger():
    msg = server.build_mazda_scan_message(
        '/scans/annotated-statement.jpg', 'Window Scanner',
        _FACADE_JPEG_UNKNOWN,
    )

    assert 'cut-and-assembled composite' in msg
    assert 'issuer letterhead, account metadata, a billing cycle' in msg
    assert 'regardless of the amount of handwriting' in msg
    assert '"moms_ledger"' in msg


def test_statement_branches_apply_handwritten_annotations_after_store():
    """Both statement paths (facade-identified statement, and the JPEG→classify
    fallback) must run apply_statement_annotations.py so EG's on-page category
    notes become the category — never a manual dashboard fix afterward."""
    # Facade-identified statement path.
    facade = dict(_FACADE_IDENTIFIED)
    facade['doc_kind'] = 'statement'
    stmt_msg = server.build_mazda_scan_message('/scans/x.jpg', 'Scanner', facade)
    assert 'apply_statement_annotations.py' in stmt_msg
    assert 'annotations_applied' in stmt_msg
    assert (
        'apply_statement_annotations.py --image /scans/x.jpg '
        '--expense-ids <IDS>'
    ) in stmt_msg
    assert 'do not use singular --expense-id, shell substitution' in stmt_msg
    # It must feed the tool BOTH stored and duplicate ids (EG annotates dups too),
    # and it must run after the store, not before.
    assert stmt_msg.index('store_statement_transactions.py') < \
        stmt_msg.index('apply_statement_annotations.py')

    # JPEG → classify-yourself fallback path.
    fb_msg = server.build_mazda_scan_message(
        '/scans/x.jpg', 'Scanner', _FACADE_JPEG_UNKNOWN)
    assert 'apply_statement_annotations.py' in fb_msg


def test_statement_branches_require_canonical_dashboard_report():
    """A stored statement is not complete until Mazda writes and validates the
    exact report.html file the dashboard resolves."""
    facade = dict(_FACADE_IDENTIFIED)
    facade['doc_kind'] = 'statement'
    stmt_msg = server.build_mazda_scan_message(
        '/statements/march/bank_6285/statement.pdf', 'Scanner', facade)

    for required in (
        '/statements/march/bank_6285/report.html',
        'REPORT_OUTPUT_CONTRACT.md',
        'restructure_verified_transactions.py',
        'hydrate_report_categories_from_db.py',
        'audit_statement_reports.py',
        'id="verified-transactions"',
        'data-vendor-key',
        'rol-category-picker:start',
        'report_generated=true',
        'report_audit_status',
        'CATEGORY AUTHORITY RULE',
        'expenses.category_id is authoritative',
        ('tools/python_tasks/verification_lib/audit_statement_reports.py '
         '/statements/march/bank_6285'),
    ):
        assert required in stmt_msg
    assert stmt_msg.index('apply_statement_annotations.py') < \
        stmt_msg.index('BUILD THE DASHBOARD REPORT')
    assert stmt_msg.index('BUILD THE DASHBOARD REPORT') < \
        stmt_msg.index('record_trace(')
    assert '/tmp/mazda_statement_' in stmt_msg
    assert '/tmp/mazda_stmt.json' not in stmt_msg

    # The classify-yourself fallback must carry the same report obligation if
    # STEP 0 discovers that an image is a statement.
    fallback_msg = server.build_mazda_scan_message(
        '/statements/march/bank_6285/scan.jpg',
        'Scanner',
        _FACADE_JPEG_UNKNOWN,
    )
    assert '/statements/march/bank_6285/report.html' in fallback_msg
    assert 'restructure_verified_transactions.py' in fallback_msg
    assert 'hydrate_report_categories_from_db.py' in fallback_msg
    assert 'audit_statement_reports.py' in fallback_msg
    assert '/tmp/mazda_statement_' in fallback_msg
    assert '/tmp/mazda_stmt.json' not in fallback_msg


def test_statement_dispatch_carries_confirmed_metadata_and_archive_evidence():
    facade = dict(_FACADE_IDENTIFIED)
    facade.update({
        'doc_kind': 'statement',
        'statement_preflight': {
            'bank_name': 'Fifth Third Bank',
            'account_last4': '5938',
        },
    })

    msg = server.build_mazda_scan_message('/scans/x.jpg', 'Scanner', facade)

    assert "--bank-name 'Fifth Third Bank' --account-last4 5938" in msg
    assert 'archive_paths' in msg
    assert 'archive_years' in msg


def test_statement_dispatch_reuses_validated_preflight_json():
    facade = dict(_FACADE_IDENTIFIED)
    facade.update({
        'doc_kind': 'statement',
        'statement_preflight': {
            'bank_name': 'Chase',
            'account_last4': '5783',
            'payload_path': '/scans/validated.statement.json',
        },
    })

    msg = server.build_mazda_scan_message('/scans/x.jpg', 'Scanner', facade)

    assert 'validated.statement.json' in msg
    assert 'Do not run statement vision again' in msg
    assert 'parse_statement_scan.py /scans/x.jpg' not in msg


def test_statement_preflight_payload_uses_the_validated_rows():
    preflight = {
        'ok': True,
        'bank_name': 'Chase',
        'account_last4': '5783',
        'transactions': [{
            'date': '2025-09-15',
            'description': 'MICROSOFT 365',
            'amount': -106.99,
        }],
        'statements': [{
            'statement_period': {'start': '2025-08-23', 'end': '2025-09-22'},
            'statement_total': 106.99,
        }],
    }

    payload = server._statement_preflight_payload('/staged/scan.jpg', preflight)

    assert payload['source_image'] == '/staged/scan.jpg'
    assert payload['statements'][0]['account_number'] == '5783'
    assert payload['statements'][0]['transactions'][0]['date'] == '2025-09-15'
    assert payload['statements'][0]['transactions'][0]['amount'] == -106.99


def test_statement_preflight_payload_never_drops_an_unreadable_row():
    preflight = {
        'ok': True,
        'bank_name': 'Chase',
        'account_last4': '5783',
        # Top-level rows are the preflight's complete-row summary.
        'transactions': [_STMT_ROWS[0]],
        # The original parser envelope retains the incomplete row that must
        # reach store validation and quarantine the entire statement.
        'statements': [{
            'transactions': [
                _STMT_ROWS[0],
                {'date': None, 'description': 'SMUDGED',
                 'amount': -9.99, 'unreadable': True},
            ],
        }],
    }

    payload = server._statement_preflight_payload('/staged/scan.jpg', preflight)

    rows = payload['statements'][0]['transactions']
    assert len(rows) == 2
    assert rows[1]['description'] == 'SMUDGED'
    assert payload['statements'][0]['unreadable_count'] == 1


def test_scan_message_invoice_route_overrides_generic_email_bill_rule():
    """An email screenshot containing an invoice must not be routed away."""
    msg = server.build_mazda_scan_message('/scans/x.jpg', 'Scanner', _FACADE_JPEG_UNKNOWN)
    assert 'receipt OR invoice' in msg
    assert 'explicit `doc_type`' in msg
    assert 'email screenshot whose enclosed document is `invoice` MUST run' in msg
    assert '--save --invoice' in msg


def test_scan_message_closes_the_improvement_loop():
    """STEP 1 must deliver the learned rules (load_wrapper_revision
    `instructions`) and STEP 7 must chain propose_improvement →
    apply_proposal — without both halves, proposals pile up in PROPOSED and
    the wrapper never leaves its baseline, so nothing is ever learned."""
    msg = server.build_mazda_scan_message('/scans/x.jpg', 'Scanner', _FACADE_IDENTIFIED)
    assert 'LEARNED RULES' in msg
    assert 'apply_proposal(proposal_id=' in msg
    assert 'instruction_note=' in msg


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
    server._notify_mazda_of_scan(
        '/scans/x.jpg', 'Freezer Scanner', _FACADE_JPEG_UNKNOWN,
        'conv-freezer')

    expected = server.build_mazda_scan_message(
        '/scans/x.jpg', 'Freezer Scanner', _FACADE_JPEG_UNKNOWN,
        conversation_id='conv-freezer')
    assert captured['body']['messages'][0]['content'] == expected
    assert captured['url'].endswith('/v1/conversations/conv-freezer/messages')
    assert captured['body']['streaming'] is False


#: What Letta returns for a conversation nothing was ever posted to: the system
#: prompt it is born with. Reproduced from the live stalled intake
#: (conv-8f235c63, 2026-08-19) -- the old probe read this as "delivered".
_ONLY_THE_SYSTEM_PROMPT = [{'role': None, 'message_type': 'system_message'}]
_DISPATCH_DELIVERED = _ONLY_THE_SYSTEM_PROMPT + [
    {'role': 'user', 'message_type': 'user_message'}]


def test_scan_notify_timeout_is_success_when_conversation_received_message(monkeypatch):
    """A slow synchronous agent run must not be reported as delivery failure."""
    monkeypatch.setattr(
        server.urllib.request, 'urlopen',
        lambda *args, **kwargs: (_ for _ in ()).throw(TimeoutError('timed out')))
    monkeypatch.setattr(
        server, 'letta_get', lambda path, timeout: _DISPATCH_DELIVERED)

    assert server._notify_mazda_of_scan(
        '/scans/x.jpg', 'Freezer Scanner', _FACADE_JPEG_UNKNOWN,
        'conv-freezer') is True


def test_scan_notify_failure_remains_failure_when_conversation_is_empty(monkeypatch):
    monkeypatch.setattr(
        server.urllib.request, 'urlopen',
        lambda *args, **kwargs: (_ for _ in ()).throw(TimeoutError('timed out')))
    monkeypatch.setattr(server, 'letta_get', lambda path, timeout: [])

    assert server._notify_mazda_of_scan(
        '/scans/x.jpg', 'Freezer Scanner', _FACADE_JPEG_UNKNOWN,
        'conv-freezer') is False


def test_a_rejected_dispatch_is_reported_as_a_failure(monkeypatch):
    """The 2026-08-19 defect, at the level the operator feels it.

    The POST was rejected with HTTP 429 -- nothing was queued -- and the probe
    saw the system prompt every conversation is born with and called it
    delivered. The scan was recorded `processing` and hung until the Trainer
    reported it as an infrastructure problem.
    """
    monkeypatch.setattr(
        server.urllib.request, 'urlopen',
        lambda *args, **kwargs: (_ for _ in ()).throw(
            urllib.error.HTTPError('u', 429, 'Too Many Requests', {}, None)))
    monkeypatch.setattr(
        server, 'letta_get', lambda path, timeout: _ONLY_THE_SYSTEM_PROMPT)

    assert server._notify_mazda_of_scan(
        '/scans/x.jpg', 'Window Scanner', _FACADE_JPEG_UNKNOWN,
        'conv-8f235c63') is False


def test_scan_notify_failure_marks_exact_intake_terminal(tmp_path, monkeypatch):
    _recent_report_env(tmp_path, monkeypatch)
    server.record_recent_intake(
        '/staged/window.jpg', 'Window Scanner',
        conversation_id='conv-window', dispatched_at=1234)
    monkeypatch.setattr(server, '_notify_mazda_of_scan', lambda *a, **k: False)

    assert server._notify_mazda_of_scan_and_record_failure(
        '/staged/window.jpg', 'Window Scanner', {}, 'conv-window', 1234) is False

    intake = server._read_recent_pointer_file()['scanner_intakes']['Window Scanner']
    assert intake['status'] == 'fail'
    assert intake['status_source'] == 'transport'
    assert 'Mazda could not be reached' in intake['status_detail']


def test_success_callback_clears_only_provisional_transport_failure(tmp_path, monkeypatch):
    _recent_report_env(tmp_path, monkeypatch)
    server.record_recent_intake(
        '/staged/freezer.jpg', 'Freezer Scanner',
        conversation_id='conv-freezer', dispatched_at=1234)
    server.merge_recent_intake_status({
        'conversation_id': 'conv-freezer',
        'status': 'fail',
        'status_source': 'transport',
        'detail': 'Mazda could not be reached',
    })

    assert server.merge_recent_intake_event({
        'conversation_id': 'conv-freezer',
        'dispatched_at': 1234,
        'parsed': 11,
        'stored': 0,
        'expense_ids': [981],
    })

    intake = server._read_recent_pointer_file()['scanner_intakes']['Freezer Scanner']
    assert intake['status'] == 'complete'
    assert intake['status_detail'] == ''
    assert intake['status_source'] == 'callback'


def test_mazda_progress_does_not_block_report_for_full_letta_timeout(monkeypatch):
    captured = {}

    def _fake_get(path, timeout):
        captured.update(path=path, timeout=timeout)
        return None

    monkeypatch.setattr(server, 'letta_get', _fake_get)
    progress = server.mazda_intake_progress({'conversation_id': 'conv-window'})

    assert captured['timeout'] == 3
    assert progress['percent'] == 0


def test_create_mazda_conversation_uses_agent_query_and_returns_id(monkeypatch):
    captured = {}

    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b'{"id":"conv-isolated-123"}'

    def _fake_urlopen(req, timeout=0):
        captured['url'] = req.full_url
        captured['method'] = req.method
        captured['body'] = req.data
        return _Resp()

    monkeypatch.setattr(server.urllib.request, 'urlopen', _fake_urlopen)
    assert REAL_CREATE_MAZDA_CONVERSATION() == 'conv-isolated-123'
    assert captured['method'] == 'POST'
    assert captured['body'] == b'{}'
    assert '/v1/conversations/?agent_id=' in captured['url']
    assert server.MAZDA_AGENT_ID in captured['url']


# ── Scan message STEP 8 ───────────────────────────────────────────────────────

def test_scan_message_includes_dashboard_callback_step():
    """STEP 8 in the scan message instructs Mazda to POST /api/expense-stored."""
    msg = server.build_mazda_scan_message('/scans/x.jpg', 'Window Scanner')
    assert 'STEP 8' in msg
    assert '/api/expense-stored' in msg
    assert 'fire-and-forget' in msg.lower() or 'Ignore errors' in msg


def test_scan_message_duplicate_ids_are_not_statement_only():
    """The receipt/invoice branch must report its duplicate id too. The old
    wording sourced duplicate_expense_ids from store_statement_transactions.py
    alone, and Mazda (backed by her Trainer) read that as "statement branch
    only" — so an invoice duplicate posted [] and the Recent Report page had no
    row to show."""
    msg = server.build_mazda_scan_message('/scans/x.jpg', 'Freezer Scanner')
    assert 'NOT statement-only' in msg
    assert 'exact_duplicate_expense_id' in msg
    assert 'If duplicate → STILL run STEP 4 exactly once' in msg
    assert 'without --allow-duplicate' in msg
    assert 'receipt_archive_path' in msg


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


def test_report_source_document_view_renders_excel_for_browser(
        tmp_path, monkeypatch):
    source = tmp_path / 'statement.xlsx'
    source.write_bytes(b'workbook')
    rendered = tmp_path / 'statement.html'
    calls = []

    monkeypatch.setattr(server, '_source_document_path', lambda _url: str(source))

    def render(source_path, browser_path):
        calls.append((source_path, browser_path))
        return str(rendered)

    monkeypatch.setattr(server, 'render_excel_for_browser', render)

    result = server._report_source_document_view(
        '/rol_finances_reports/jan-2025/stub/report.html')

    assert result == str(rendered)
    assert calls[0][0] == str(source)
    assert calls[0][1].endswith('-statement.xlsx.html')


def test_report_source_document_view_rejects_generated_report(
        tmp_path, monkeypatch):
    generated_report = tmp_path / 'report.html'
    generated_report.write_text('<html></html>')
    monkeypatch.setattr(
        server, '_source_document_path', lambda _url: str(generated_report))

    assert server._report_source_document_view('/report.html') == ''


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
        'conversation_id': 'conv-intake-42',
        'dispatched_at': 123.5,
        'archive_paths': ['/receipts/2025/january/example.jpg'],
        'archive_years': [2025],
    })
    assert result == {'ok': True}

    events = server.get_stored_expense_events(0.0)
    assert len(events) == 1
    assert events[0]['expense_id'] == 42
    assert events[0]['vendor_key'] == 'goodwill_cascade'
    assert events[0]['conversation_id'] == 'conv-intake-42'
    assert events[0]['dispatched_at'] == 123.5
    assert events[0]['archive_paths'] == [
        '/receipts/2025/january/example.jpg']
    assert events[0]['archive_years'] == [2025]
    assert 'stored_at' in events[0]
    _clear_expense_events()


def test_duplicate_only_correction_replaces_superseded_expense_ids():
    intake = {
        'expense_ids': [1518, 1520],
        'duplicate_expense_ids': [],
        'stored': 1,
    }

    server._fold_event_into_intake(intake, {
        'stored': 0,
        'duplicate_expense_ids': [1518],
        'expense_id': None,
    })

    assert intake['expense_ids'] == [1518]
    assert intake['duplicate_expense_ids'] == [1518]
    assert intake['stored'] == 0


def test_fold_event_unions_scanned_statement_attached_ids():
    """A re-scan that only fortifies existing rows (EVIDENCE_ATTACHED) must
    still render those rows in Verified Transactions — the direct fix for the
    Country Inn & Suites $179.08 charge disappearing from the scanner tab."""
    intake = {'expense_ids': [], 'duplicate_expense_ids': [], 'stored': 0}

    server._fold_event_into_intake(intake, {
        'stored': 0,
        'duplicate_expense_ids': [1366, 1390],
        'scanned_statement_attached': [1366, 1390, 1434],
        'outcome': 'EVIDENCE_ATTACHED',
    })

    assert set(intake['expense_ids']) == {1366, 1390, 1434}


def test_intake_reports_rolled_back_row_count():
    intake = {'expense_ids': [], 'duplicate_expense_ids': []}

    server._fold_event_into_intake(intake, {
        'stored': 0,
        'parsed': 4,
        'rolled_back_row_count': 2,
    })

    assert intake['rolled_back_row_count'] == 2


def test_rolled_back_row_count_defaults_to_absent_when_not_reported():
    intake = {'expense_ids': [], 'duplicate_expense_ids': []}

    server._fold_event_into_intake(intake, {'stored': 0, 'parsed': 4})

    assert 'rolled_back_row_count' not in intake


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


# ── ROL Finance: recently-scanned queue + green/yellow month status ──────────
# A query-aware DB double: fetchall/fetchone dispatch on the executed SQL/params
# so one connection can serve the SELECT + COUNT (+ per-month) queries these
# helpers run.
class _RoutingCursor:
    def __init__(self, router):
        self._router = router
        self._sql = ''
        self._params = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params=None):
        self._sql = sql
        self._params = params

    def fetchall(self):
        return self._router(self._sql, self._params)

    def fetchone(self):
        return self._router(self._sql, self._params)


class _RoutingConnection:
    def __init__(self, router):
        self._router = router

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return _RoutingCursor(self._router)


def test_fetch_expenses_by_ids_expands_parent_to_line_item_children(monkeypatch):
    """A reported PARENT anchor is uncategorizable, so the intake view must
    substitute its LINE_ITEM children (which carry the real category)."""
    def router(sql, params):
        if 'FROM categories' in sql:
            return [{'id': 120, 'parent_id': None}]
        if "COLUMN_NAME IN ('id_light'" in sql:
            return [{'COLUMN_NAME': name} for name in (
                'id_light', 'receipt_url', 'document_url',
                'scanned_statement_url', 'moms_ledger')]
        if 'parent_expense_id IN' in sql:
            return [{
                'id': 1522, 'expense_date': '2025-01-23', 'amount': '222.65',
                'id_light': 'consumers_energy_01_23_25_222_65-item-1',
                'description': 'Amount Due', 'category_id': 120,
                'receipt_url': 'consumers_energy_01_23_25_222_65.jpg',
                'expense_role': 'LINE_ITEM', 'parent_expense_id': 1521,
            }]
        # The requested id resolves to the PARENT anchor.
        return [{
            'id': 1521, 'expense_date': '2025-01-23', 'amount': '222.65',
            'id_light': 'consumers_energy_01_23_25_222_65',
            'description': 'Consumers Energy', 'category_id': None,
            'receipt_url': '', 'expense_role': 'PARENT',
        }]

    monkeypatch.setattr(server, '_rol_get_connection',
                        lambda: _RoutingConnection(router))

    rows = server._fetch_expenses_by_ids([1521])
    # The anchor itself is gone; only the categorizable child is shown.
    assert [r['id'] for r in rows] == [1522]
    assert rows[0]['reporting_category'] == 'Church Utilities'
    # Vendor stays recognizable even though the child line said only "Amount Due".
    assert rows[0]['description'] == 'Consumers Energy — Amount Due'


def test_fetch_expenses_by_ids_supports_legacy_schema_without_roles(monkeypatch):
    def router(sql, params):
        if 'FROM categories' in sql:
            return [{'id': 3, 'parent_id': None}]
        if "COLUMN_NAME IN ('id_light'" in sql:
            return [{'COLUMN_NAME': name} for name in ('id_light', 'receipt_url')]
        if 'INFORMATION_SCHEMA.COLUMNS' in sql:
            return []
        assert 'expense_role' not in sql
        return [{
            'id': 1564, 'expense_date': '2025-03-31', 'amount': '94.41',
            'id_light': 'meijer_03_31_25_94_41',
            'description': 'meijer', 'category_id': 3,
            'receipt_url': 'meijer_03_31_25_94_41.jpg',
        }]

    monkeypatch.setattr(server, '_rol_get_connection',
                        lambda: _RoutingConnection(router))

    rows = server._fetch_expenses_by_ids([1564])

    assert [r['id'] for r in rows] == [1564]
    assert rows[0]['amount'] == '94.41'


def test_fetch_expenses_by_ids_supports_minimal_live_expenses_schema(monkeypatch):
    def router(sql, params):
        if 'FROM categories' in sql:
            return [{'id': 3, 'parent_id': None}]
        if "COLUMN_NAME = 'expense_role'" in sql:
            return []
        if "COLUMN_NAME IN ('id_light'" in sql:
            return [{'COLUMN_NAME': 'receipt_url'}]
        assert 'NULL AS id_light' in sql
        assert 'NULL AS document_url' in sql
        return [{
            'id': 7, 'expense_date': '2025-03-31', 'amount': '94.41',
            'id_light': None, 'description': 'Meijer', 'category_id': 3,
            'receipt_url': 'meijer.jpg', 'document_url': None,
            'scanned_statement_url': None, 'moms_ledger': None,
        }]

    monkeypatch.setattr(server, '_rol_get_connection',
                        lambda: _RoutingConnection(router))

    rows = server._fetch_expenses_by_ids([7])

    assert rows[0]['vendor_key'] == ''
    assert rows[0]['receipt_url'] == 'meijer.jpg'


def test_fetch_expenses_by_ids_omits_childless_parent(monkeypatch):
    """A PARENT with no LINE_ITEM children (a data anomaly) is dropped rather
    than surfaced as an uncategorizable dead row."""
    def router(sql, params):
        if 'FROM categories' in sql:
            return []
        if "COLUMN_NAME IN ('id_light'" in sql:
            return [{'COLUMN_NAME': name} for name in (
                'id_light', 'receipt_url', 'document_url',
                'scanned_statement_url', 'moms_ledger')]
        if 'parent_expense_id IN' in sql:
            return []
        return [{
            'id': 1521, 'expense_date': '2025-01-23', 'amount': '222.65',
            'id_light': 'x', 'description': 'Orphan', 'category_id': None,
            'receipt_url': '', 'expense_role': 'PARENT',
        }]

    monkeypatch.setattr(server, '_rol_get_connection',
                        lambda: _RoutingConnection(router))

    assert server._fetch_expenses_by_ids([1521]) == []


def test_fetch_expenses_by_ids_reports_each_child_once_when_parent_also_listed(
        monkeypatch):
    """STEP 8 reports the PARENT anchor *and* every child it created.

    The expansion pass drops the anchor and splices its children in, so a
    child that was already in the requested id list used to be emitted twice
    — once bare from the first query, once parent-prefixed from the expansion.
    That is what put 22 rows on a 12-expense Window report.  Each child must
    appear exactly once, keeping the prefixed copy so the vendor stays
    readable.
    """
    def router(sql, params):
        if 'FROM categories' in sql:
            return [{'id': 204, 'parent_id': None}]
        if 'parent_expense_id IN' in sql:
            return [
                {
                    'id': 1685, 'expense_date': '2025-12-22', 'amount': '25.00',
                    'id_light': 'rtl_12_22_25_247_70-item-1',
                    'description': '12/22/2025 Contribution', 'category_id': 204,
                    'receipt_url': '', 'document_url': '', 'moms_ledger': None,
                    'expense_role': 'LINE_ITEM', 'parent_expense_id': 1684,
                },
                {
                    'id': 1686, 'expense_date': '2025-12-22', 'amount': '25.00',
                    'id_light': 'rtl_12_22_25_247_70-item-2',
                    'description': '11/17/2025 Contribution', 'category_id': 204,
                    'receipt_url': '', 'document_url': '', 'moms_ledger': None,
                    'expense_role': 'LINE_ITEM', 'parent_expense_id': 1684,
                },
            ]
        return [
            {
                'id': 1684, 'expense_date': '2025-12-22', 'amount': '50.00',
                'id_light': 'rtl_12_22_25_247_70',
                'description': 'Right to Life of Michigan Educational Fund',
                'category_id': None, 'receipt_url': '', 'document_url': '',
                'moms_ledger': None, 'expense_role': 'PARENT',
            },
            {
                'id': 1685, 'expense_date': '2025-12-22', 'amount': '25.00',
                'id_light': 'rtl_12_22_25_247_70-item-1',
                'description': '12/22/2025 Contribution', 'category_id': 204,
                'receipt_url': '', 'document_url': '', 'moms_ledger': None,
                'expense_role': 'LINE_ITEM',
            },
            {
                'id': 1686, 'expense_date': '2025-12-22', 'amount': '25.00',
                'id_light': 'rtl_12_22_25_247_70-item-2',
                'description': '11/17/2025 Contribution', 'category_id': 204,
                'receipt_url': '', 'document_url': '', 'moms_ledger': None,
                'expense_role': 'LINE_ITEM',
            },
        ]

    monkeypatch.setattr(server, '_rol_get_connection',
                        lambda: _RoutingConnection(router))

    rows = server._fetch_expenses_by_ids([1684, 1685, 1686])

    assert [r['id'] for r in rows] == [1685, 1686]
    assert rows[0]['description'] == (
        'Right to Life of Michigan Educational Fund — 12/22/2025 Contribution')
    assert rows[1]['description'] == (
        'Right to Life of Michigan Educational Fund — 11/17/2025 Contribution')


def test_is_uncategorized_flags_null_and_legacy_ids():
    assert server._is_uncategorized(None) is True
    assert server._is_uncategorized(1) is True
    assert server._is_uncategorized(364) is True
    # A real reporting bucket is finished, not "work to do".
    assert server._is_uncategorized(100) is False
    assert server._is_uncategorized(190) is False


def test_receipt_only_rows_are_all_year_for_january_and_month_scoped_otherwise(
        monkeypatch):
    queries = []

    def router(sql, params):
        if 'FROM categories' in sql:
            return []
        queries.append((sql, params))
        return []

    monkeypatch.setattr(server, '_rol_get_connection',
                        lambda: _RoutingConnection(router))

    server._fetch_receipt_only_rows('jan-2025')
    server._fetch_receipt_only_rows('feb-2025')
    server._fetch_receipt_only_rows('mar-2025')
    server._fetch_receipt_only_rows('apr-2025')

    assert 'BETWEEN' not in queries[0][0]
    assert queries[0][1] == ()
    assert queries[1][1] == ('2025-02-01', '2025-02-28')
    assert queries[2][1] == ('2025-03-01', '2025-03-31')
    assert queries[3][1] == ('2025-04-01', '2025-04-30')


def test_fetch_recent_scans_returns_uncategorized_newest_first_with_total(monkeypatch):
    rows = [
        {'id': 42, 'id_light': 'meijer_01_22_25_18_40', 'description': 'MEIJER',
         'expense_date': '2025-01-22', 'amount': '18.40', 'category_id': None,
         'receipt_url': '', 'created_at': '2025-01-22 10:00:00'},
        {'id': 41, 'id_light': 'circle_k_09828_01_21_25_5_00', 'description': 'CIRCLE K',
         'expense_date': '2025-01-21', 'amount': '5.00', 'category_id': 364,
         'receipt_url': '', 'created_at': '2025-01-21 09:00:00'},
    ]

    def router(sql, _params):
        return {'n': 7} if 'COUNT(' in sql else rows

    monkeypatch.setattr(server, '_rol_get_connection',
                        lambda: _RoutingConnection(router))
    monkeypatch.setattr(server, '_resolve_expense_receipt_path',
                        lambda *_a: None)

    out = server._fetch_recent_scans(5)
    assert out['queue_total'] == 7
    assert out['limit'] == 5
    assert [r['id'] for r in out['rows']] == [42, 41]
    assert out['rows'][0]['vendor_key'] == 'meijer'
    assert out['rows'][0]['reporting_category'] == 'Uncategorized'
    assert out['rows'][0]['receipt_present'] is False
    # Every row carries a human-readable reason it landed in New Records.
    assert 'reason' in out['rows'][0] and out['rows'][0]['reason']


def test_fetch_recent_scans_reason_prefers_expense_notes(monkeypatch):
    rows = [
        {'id': 9, 'id_light': 'x_01_01_25_1_00', 'description': 'X',
         'expense_date': '2025-01-01', 'amount': '1.00', 'category_id': None,
         'receipt_url': '', 'created_at': '2025-01-01 00:00:00',
         'notes': 'Vendor not in the map — needs a manual rule'},
    ]

    def router(sql, _params):
        return {'n': 1} if 'COUNT(' in sql else rows

    monkeypatch.setattr(server, '_rol_get_connection',
                        lambda: _RoutingConnection(router))
    monkeypatch.setattr(server, '_resolve_expense_receipt_path', lambda *_a: None)
    out = server._fetch_recent_scans(5)
    assert out['rows'][0]['reason'] == 'Vendor not in the map — needs a manual rule'


def test_fetch_recent_scans_clamps_limit(monkeypatch):
    # Guards the ORDER BY ... LIMIT %s bind against absurd input (1..50).
    seen = {}

    def router(sql, params):
        if 'COUNT(' in sql:
            return {'n': 0}
        seen['limit'] = params[-1]  # trailing LIMIT bind
        return []

    monkeypatch.setattr(server, '_rol_get_connection',
                        lambda: _RoutingConnection(router))
    server._fetch_recent_scans(9999)
    assert seen['limit'] == 50
    server._fetch_recent_scans(-3)
    assert seen['limit'] == 1


def test_fetch_month_status_yellow_when_newest_scan_uncategorized(monkeypatch):
    # jan's newest scan is categorized (green); feb's newest is uncategorized (yellow).
    newest = {
        'jan-2025': {'id': 10, 'id_light': 'x_01_02_25_1_00', 'description': 'X',
                     'expense_date': '2025-01-02', 'amount': '1.00',
                     'category_id': 100, 'created_at': '2025-01-02 00:00:00'},
        'feb-2025': {'id': 20, 'id_light': 'y_02_02_25_2_00', 'description': 'Y',
                     'expense_date': '2025-02-02', 'amount': '2.00',
                     'category_id': None, 'created_at': '2025-02-02 00:00:00'},
    }

    def router(sql, params):
        month = 'jan-2025' if str(params[0]).startswith('2025-01') else 'feb-2025'
        if 'COUNT(' in sql:
            return {'n': 0 if month == 'jan-2025' else 4}
        return newest[month]

    monkeypatch.setattr(server, '_rol_get_connection',
                        lambda: _RoutingConnection(router))

    by = {m['month_key']: m for m in server._fetch_month_status()}
    assert by['jan-2025']['status'] == 'green'
    assert by['jan-2025']['uncategorized_count'] == 0
    assert by['feb-2025']['status'] == 'yellow'
    assert by['feb-2025']['uncategorized_count'] == 4
    assert by['feb-2025']['most_recent_unfinished']['uncategorized'] is True
    assert by['feb-2025']['most_recent_unfinished']['vendor_key'] == 'y'


def test_rol_finance_categories_match_recategorize_targets():
    cats = server._rol_finance_categories()
    names = [c['name'] for c in cats]
    # Every offered category must be a valid /api/recategorize-expense target,
    # and carry colors, so the dialog can't offer something the writer rejects.
    assert names, 'expected a non-empty category palette'
    assert 'Uncategorized' in names
    for c in cats:
        assert c['name'] in server.REPORTING_CATEGORY_DB_MAP
        assert c['cls'] and c['bg'] and c['fg']


def test_fetch_month_status_green_when_no_expenses(monkeypatch):
    def router(sql, _params):
        return {'n': 0} if 'COUNT(' in sql else None

    monkeypatch.setattr(server, '_rol_get_connection',
                        lambda: _RoutingConnection(router))
    for m in server._fetch_month_status():
        assert m['status'] == 'green'
        assert m['most_recent_unfinished'] is None


# ── Web terminal (Input Options → letta-code terminal) ────────────────────────

def test_ws_accept_key_matches_rfc6455_example():
    # The canonical example from RFC 6455 §1.3.
    assert server.ws_accept_key('dGhlIHNhbXBsZSBub25jZQ==') == \
        's3pPLMBiTxaQ9kYGzzhZRbK+xOo='


def test_ws_frame_roundtrip_unmasks_client_data():
    import io
    payload = b'{"t":"i","d":"ls\\n"}'
    mask = bytes([0x11, 0x22, 0x33, 0x44])
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    frame = bytes([0x81, 0x80 | len(payload)]) + mask + masked  # FIN+text, masked
    opcode, data = server.ws_read_frame(io.BytesIO(frame))
    assert opcode == 0x1
    assert data == payload


def test_ws_encode_frame_sets_fin_and_binary_opcode():
    out = server.ws_encode_frame(b'hello')
    assert out[0] == 0x82          # FIN + binary opcode
    assert out[1] == 5             # unmasked, len 5
    assert out[2:] == b'hello'


# ── Model usage: rate-of-change + slow-leak detector ─────────────────────────
# The rate is %-points of the primary quota window consumed per hour, expressed
# as a burn multiple of the window's replenish pace (100/window_hours per hour)
# — see the "Model usage" section comment in server.py. All thresholds are
# passed explicitly here so the tests don't depend on env-var config.

def _samples(pairs):
    """[(minutes_ago, pct), ...] → [(ts, pct), ...] anchored at t=10_000_000."""
    now = 10_000_000
    return now, [(now - m * 60, p) for m, p in sorted(pairs, reverse=True)]


def test_compute_usage_rate_needs_enough_history():
    now, s = _samples([(0, 50.0)])                     # single snapshot
    r = server.compute_usage_rate(s, 5.0, now=now)
    assert r['available'] is False and 'gathering' in r['reason']


def test_compute_usage_rate_burn_math_5h_window():
    # +10 %-points in 30 min = 20 %/hr; a 5h window replenishes at 20 %/hr,
    # so that's exactly burn 1.0× — sustainable, and right AT the default warn.
    now, s = _samples([(30, 50.0), (15, 55.0), (0, 60.0)])
    r = server.compute_usage_rate(s, 5.0, now=now, window_minutes=30,
                                  warn_multiple=1.0, full_scale=2.0)
    assert r['available'] is True
    assert r['pct_per_hour'] == 20.0
    assert r['burn_multiple'] == 1.0
    assert r['bar_percent'] == 50          # half bar == sustainable pace
    assert r['warn'] is True               # >= warn threshold → blink


def test_compute_usage_rate_under_threshold_no_warn():
    now, s = _samples([(30, 50.0), (0, 52.0)])         # 4 %/hr on a 5h window
    r = server.compute_usage_rate(s, 5.0, now=now, warn_multiple=1.0)
    assert r['warn'] is False and r['burn_multiple'] == 0.2


def test_compute_usage_rate_clamps_rolling_window_decay():
    # used_percent falling (old usage aging out of the rolling window) is not
    # negative spending — the rate clamps to 0 and must not warn.
    now, s = _samples([(30, 60.0), (0, 40.0)])
    r = server.compute_usage_rate(s, 5.0, now=now)
    assert r['pct_per_hour'] == 0.0 and r['warn'] is False


def test_detect_slow_leak_flags_steady_climb():
    # +1.5 %-points every 30-min bucket for 2h — the ping-loop signature.
    now, s = _samples([(m, 40.0 + (120 - m) * 0.05) for m in range(120, -1, -5)])
    leak = server.detect_slow_leak(s, now=now, bucket_minutes=30, lookback_minutes=120,
                                   min_rise_pct=0.5, min_rising_buckets=3)
    assert leak['suspected'] is True
    assert leak['consecutive_rising'] >= 3
    assert 'Slow token drain' in leak['text']


def test_detect_slow_leak_ignores_flat_usage():
    now, s = _samples([(m, 47.0) for m in range(120, -1, -5)])
    leak = server.detect_slow_leak(s, now=now, bucket_minutes=30, lookback_minutes=120,
                                   min_rise_pct=0.5, min_rising_buckets=3)
    assert leak['suspected'] is False and leak['text'] == ''


def test_detect_slow_leak_ignores_single_burst():
    # One busy half-hour (a real task) then flat — NOT a leak.
    now, s = _samples([(m, 40.0 if m > 30 else 55.0) for m in range(120, -1, -5)])
    leak = server.detect_slow_leak(s, now=now, bucket_minutes=30, lookback_minutes=120,
                                   min_rise_pct=0.5, min_rising_buckets=3)
    assert leak['suspected'] is False


def test_detect_slow_leak_data_gap_breaks_consecutive_run():
    # Two rising buckets, a gap with no samples, then one more rising bucket:
    # longest CONSECUTIVE run is 2 < 3 → not suspected.
    pairs = [(m, 40.0 + (120 - m) * 0.05) for m in range(120, -1, -5)
             if not (30 <= m < 60)]
    now, s = _samples(pairs)
    leak = server.detect_slow_leak(s, now=now, bucket_minutes=30, lookback_minutes=120,
                                   min_rise_pct=0.5, min_rising_buckets=3)
    assert leak['suspected'] is False


def test_model_stats_payload_carries_rate_and_leak(monkeypatch):
    # Seed 30 min of history rising fast (40 %/hr = burn 2.0× on the 5h window),
    # then one live fetch: the payload must expose rate + leak and escalate a
    # green source to 'concern' so the tab goes yellow.
    now = server.time.time()
    for minutes_ago, pct in ((30, 10.0), (15, 20.0)):
        server._record_usage_sample('w11-codex', pct, now=now - minutes_ago * 60)
    monkeypatch.setattr(_stats_reader, '_run_extractor', lambda *a, **k: _codex_usage(30.0, 11.0))
    d = server.model_stats('w11-codex')
    assert d['rate']['available'] is True
    assert d['rate']['warn'] is True
    assert d['rate']['window_label'] == '5-hour'
    assert d['leak']['suspected'] is False
    assert d['status'] == 'concern'        # early warning colors the tab


def test_model_stats_rate_gathering_when_no_history(monkeypatch):
    monkeypatch.setattr(_stats_reader, '_run_extractor', lambda *a, **k: _codex_usage(10.0, 11.0))
    d = server.model_stats('w11-codex')
    assert d['rate']['available'] is False
    assert d['leak']['suspected'] is False
    assert d['status'] == 'up'             # no history → no false alarms


def test_usage_history_persists_and_prunes(tmp_path, monkeypatch):
    monkeypatch.setattr(_usage_history_mod, 'MODEL_USAGE_HISTORY_FILE', str(tmp_path / 'h.json'))
    monkeypatch.setattr(_usage_history_mod, '_usage_history', None)   # force a disk load
    now = 10_000_000
    old = now - (server.MODEL_USAGE_HISTORY_KEEP_MINUTES + 5) * 60
    server._record_usage_sample('w11-codex', 5.0, now=old)
    kept = server._record_usage_sample('w11-codex', 6.0, now=now)
    assert [p for _, p in kept] == [6.0]                  # stale sample pruned
    monkeypatch.setattr(_usage_history_mod, '_usage_history', None)   # reload from disk
    again = server._record_usage_sample('w11-codex', 7.0, now=now + 60)
    assert [p for _, p in again] == [6.0, 7.0]            # survived "restart"


# ── PC Monitor (parse + metric builder + endpoint payload) ────────────────────

_PC_COLLECTOR_SAMPLE = """===MEM===
MemTotal:       16384000 kB
MemAvailable:    4096000 kB
===DISK===
Filesystem     1024-blocks      Used Available Capacity Mounted on
C:\\             500000000 400000000 100000000      80% /mnt/c
===NET===
Inter-|   Receive                                                |  Transmit
 face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed
    lo: 999999999    1000    0    0    0     0          0         0 999999999    1000    0    0    0     0       0          0
  eth0: 1000000    2000    0    0    0     0          0         0 2000000    3000    0    0    0     0       0          0
  eth1:  500000    100    0    0    0     0          0         0  500000    200    0    0    0     0       0          0
"""


def test_parse_pc_metrics_output_reads_all_three_sections():
    parsed = server.parse_pc_metrics_output(_PC_COLLECTOR_SAMPLE)
    assert parsed['mem_total_kb'] == 16384000
    assert parsed['mem_avail_kb'] == 4096000
    assert parsed['disk_total_kb'] == 500000000
    assert parsed['disk_used_kb'] == 400000000
    assert parsed['disk_avail_kb'] == 100000000
    assert parsed['disk_mount'] == '/mnt/c'
    # loopback excluded; eth0 + eth1 summed
    assert parsed['net_rx_bytes'] == 1500000
    assert parsed['net_tx_bytes'] == 2500000


def test_pc_metrics_collector_uses_powershell_for_windows_ram():
    command = server.pc_metrics_collector_command(server.PC_MONITORS['win11'])
    assert server._WINDOWS_POWERSHELL in command
    assert 'Get-CimInstance Win32_OperatingSystem' in command
    assert 'TotalVisibleMemorySize' in command
    assert 'FreePhysicalMemory' in command
    assert '/proc/meminfo' not in command


def test_pc_metrics_collector_keeps_proc_memory_for_linux():
    command = server.pc_metrics_collector_command(server.PC_MONITORS['moms46'])
    assert "grep -E 'MemTotal|MemAvailable' /proc/meminfo" in command
    assert 'Get-CimInstance' not in command


def test_parse_pc_metrics_output_falls_back_to_root_mount():
    # A box without /mnt/c (plain Linux): the collector's fallback df / row.
    sample = _PC_COLLECTOR_SAMPLE.replace(
        'C:\\             500000000 400000000 100000000      80% /mnt/c',
        '/dev/sdc         500000000 400000000 100000000      80% /')
    parsed = server.parse_pc_metrics_output(sample)
    assert parsed['disk_total_kb'] == 500000000
    assert parsed['disk_mount'] == '/'


_PC_TEST_THRESHOLDS = {'ram': 90.0, 'disk_free_warn_gb': 5.0,
                       'disk_free_crit_gb': 2.0, 'net': 80.0}
_GB_KB = 1024 * 1024


def test_build_pc_metrics_percentages_and_no_alert_under_threshold():
    parsed = server.parse_pc_metrics_output(_PC_COLLECTOR_SAMPLE)
    metrics, sample = server.build_pc_metrics(
        parsed, None, now=1000.0, thresholds=_PC_TEST_THRESHOLDS, net_capacity_mbps=100.0)
    by_key = {m['key']: m for m in metrics}
    assert by_key['ram']['percent'] == 75.0       # (16384000-4096000)/16384000
    assert by_key['disk']['percent'] == 80.0
    assert by_key['disk']['text'].startswith('C: ')       # labelled as the C: drive
    assert 'GB free' in by_key['disk']['text']            # ~95 GB free → ok
    assert all(m['level'] == 'ok' and not m['alert'] for m in metrics)
    # First sample: no rate yet, but the new cumulative sample is returned.
    assert by_key['net']['percent'] == 0
    assert sample == (1000.0, 4000000)


def test_build_pc_metrics_ram_alert_over_threshold():
    parsed = server.parse_pc_metrics_output(_PC_COLLECTOR_SAMPLE)
    parsed['mem_avail_kb'] = 819200               # 95% used
    metrics, _ = server.build_pc_metrics(
        parsed, None, now=1000.0, thresholds=_PC_TEST_THRESHOLDS, net_capacity_mbps=100.0)
    ram = next(m for m in metrics if m['key'] == 'ram')
    assert ram['percent'] == 95.0 and ram['alert'] is True
    assert ram['level'] == 'warn'


def test_build_pc_metrics_disk_warn_under_5gb_free():
    parsed = server.parse_pc_metrics_output(_PC_COLLECTOR_SAMPLE)
    parsed['disk_avail_kb'] = 4 * _GB_KB          # 4 GB free → yellow
    metrics, _ = server.build_pc_metrics(
        parsed, None, now=1000.0, thresholds=_PC_TEST_THRESHOLDS, net_capacity_mbps=100.0)
    disk = next(m for m in metrics if m['key'] == 'disk')
    assert disk['level'] == 'warn' and disk['alert'] is True
    assert '4.0 GB free' in disk['text']


def test_build_pc_metrics_disk_crit_at_2gb_free_or_less():
    parsed = server.parse_pc_metrics_output(_PC_COLLECTOR_SAMPLE)
    parsed['disk_avail_kb'] = 2 * _GB_KB          # exactly 2 GB free → red
    metrics, _ = server.build_pc_metrics(
        parsed, None, now=1000.0, thresholds=_PC_TEST_THRESHOLDS, net_capacity_mbps=100.0)
    disk = next(m for m in metrics if m['key'] == 'disk')
    assert disk['level'] == 'crit' and disk['alert'] is True


def test_build_pc_metrics_disk_ok_at_exactly_5gb_free():
    # Boundary: "under 5 GB" is exclusive — exactly 5 GB free stays green.
    parsed = server.parse_pc_metrics_output(_PC_COLLECTOR_SAMPLE)
    parsed['disk_avail_kb'] = 5 * _GB_KB
    metrics, _ = server.build_pc_metrics(
        parsed, None, now=1000.0, thresholds=_PC_TEST_THRESHOLDS, net_capacity_mbps=100.0)
    disk = next(m for m in metrics if m['key'] == 'disk')
    assert disk['level'] == 'ok' and disk['alert'] is False


def test_build_pc_metrics_network_rate_from_two_samples():
    parsed = server.parse_pc_metrics_output(_PC_COLLECTOR_SAMPLE)
    # 10s earlier the counters were 10 Mbit lower: 10e6 bits / 10s = 1 Mbit/s.
    prev = (990.0, 4000000 - 1250000)
    metrics, _ = server.build_pc_metrics(
        parsed, prev, now=1000.0, thresholds=_PC_TEST_THRESHOLDS, net_capacity_mbps=100.0)
    net = next(m for m in metrics if m['key'] == 'net')
    assert net['percent'] == 1.0                  # 1 of 100 Mbit/s
    assert not net['alert']
    assert 'Mbit/s' in net['text']


def test_build_pc_metrics_network_alert_and_percent_clamped():
    parsed = server.parse_pc_metrics_output(_PC_COLLECTOR_SAMPLE)
    # 200 Mbit in 1s on a 100 Mbit/s scale → clamp at 100%, alert at ≥80%.
    prev = (999.0, 4000000 - 25000000)
    metrics, _ = server.build_pc_metrics(
        parsed, prev, now=1000.0, thresholds=_PC_TEST_THRESHOLDS, net_capacity_mbps=100.0)
    net = next(m for m in metrics if m['key'] == 'net')
    assert net['percent'] == 100.0 and net['alert'] is True


def test_build_pc_metrics_counter_reset_falls_back_to_measuring():
    parsed = server.parse_pc_metrics_output(_PC_COLLECTOR_SAMPLE)
    # Reboot: cumulative counters went BACKWARDS — no bogus negative rate.
    prev = (990.0, 4000000 + 999999)
    metrics, _ = server.build_pc_metrics(
        parsed, prev, now=1000.0, thresholds=_PC_TEST_THRESHOLDS, net_capacity_mbps=100.0)
    net = next(m for m in metrics if m['key'] == 'net')
    assert net['percent'] == 0 and net['text'] == 'measuring…'


def test_pc_metrics_unknown_key():
    out = server.pc_metrics('atari-2600')
    assert out['ok'] is False and out['alert'] is False


def test_pc_metrics_payload_and_alert_rollup(monkeypatch):
    _pc._pc_metrics_cache.clear()
    _pc._pc_net_last.clear()

    class _R:
        returncode = 0
        stdout = _PC_COLLECTOR_SAMPLE
        stderr = ''

    monkeypatch.setattr(server.subprocess, 'run', lambda *a, **k: _R())
    monkeypatch.setattr(_pc, 'PC_ALERT_THRESHOLDS',
                        {'ram': 70.0, 'disk_free_warn_gb': 5.0,
                         'disk_free_crit_gb': 2.0, 'net': 80.0})
    out = server.pc_metrics('win11')
    assert out['ok'] is True and out['label'] == 'Windows 11'
    assert [m['key'] for m in out['metrics']] == ['ram', 'disk', 'net']
    assert out['alert'] is True                   # ram 75% ≥ lowered 70% threshold
    assert out['level'] == 'warn'
    # Cached: a second call must not re-run the collector.
    monkeypatch.setattr(server.subprocess, 'run',
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError('collector re-ran')))
    assert server.pc_metrics('win11') is out


def test_pc_metrics_crit_disk_rolls_up_red(monkeypatch):
    _pc._pc_metrics_cache.clear()
    _pc._pc_net_last.clear()
    # 1 GB free on C: → the whole PC payload escalates to level 'crit'.
    low_disk = _PC_COLLECTOR_SAMPLE.replace(
        'C:\\             500000000 400000000 100000000      80% /mnt/c',
        'C:\\             500000000 498951424   1048576      99% /mnt/c')

    class _R:
        returncode = 0
        stdout = low_disk
        stderr = ''

    monkeypatch.setattr(server.subprocess, 'run', lambda *a, **k: _R())
    out = server.pc_metrics('win11')
    assert out['ok'] is True and out['level'] == 'crit' and out['alert'] is True
    disk = next(m for m in out['metrics'] if m['key'] == 'disk')
    assert disk['level'] == 'crit'


def test_pc_metrics_collector_failure_is_reported(monkeypatch):
    _pc._pc_metrics_cache.clear()
    _pc._pc_last_good.clear()

    class _R:
        returncode = 255
        stdout = ''
        stderr = 'ssh: connect to host timed out'

    monkeypatch.setattr(server.subprocess, 'run', lambda *a, **k: _R())
    out = server.pc_metrics('moms46')
    assert out['ok'] is False and out['alert'] is False
    assert 'timed out' in out['error']


def test_pc_metrics_failure_after_success_serves_stale_last_good(monkeypatch):
    # Transient SSH stall (the Tailscale path drops the first attempt after
    # idle): the endpoint must serve the last good reading marked stale, not
    # a raw error page.
    _pc._pc_metrics_cache.clear()
    _pc._pc_net_last.clear()
    _pc._pc_last_good.clear()

    class _Good:
        returncode = 0
        stdout = _PC_COLLECTOR_SAMPLE
        stderr = ''

    monkeypatch.setattr(server.subprocess, 'run', lambda *a, **k: _Good())
    good = server.pc_metrics('win10')
    assert good['ok'] is True and 'stale' not in good

    _pc._pc_metrics_cache.clear()          # expire the cache, keep last-good

    def _boom(*a, **k):
        raise server.subprocess.TimeoutExpired(cmd='ssh', timeout=25)

    monkeypatch.setattr(server.subprocess, 'run', _boom)
    out = server.pc_metrics('win10')
    assert out['ok'] is True and out['stale'] is True
    assert 'timed out' in out['stale_error'] or 'timeout' in out['stale_error'].lower()
    assert [m['key'] for m in out['metrics']] == ['ram', 'disk', 'net']
    assert good.get('stale') is None           # the cached good payload wasn't mutated


# ── /api/agent-model dropdown options ─────────────────────────────────────────

def test_agent_model_options_default_list():
    opts = server.agent_model_options('chatgpt-plus-pro/gpt-5.6-sol')
    assert opts == server.AGENT_MODEL_OPTIONS
    assert not any('mini' in option.lower() or 'nano' in option.lower() for option in opts)


def test_agent_model_options_foreign_handle_prepended():
    opts = server.agent_model_options('lc-gemini/gemini-2.5-flash-lite')
    assert opts[0] == 'lc-gemini/gemini-2.5-flash-lite'
    assert opts[1:] == server.AGENT_MODEL_OPTIONS


def test_agent_model_options_empty_handle():
    assert server.agent_model_options('') == server.AGENT_MODEL_OPTIONS


def test_agent_model_options_only_vetted_codex_and_claude_handles():
    expected_by_prefix = {
        'chatgpt-plus-pro': {
            'gpt-5.6-sol',
            'gpt-5.6-terra',
            'gpt-5.6-luna',
        },
        'claude-pro-max': {
            'claude-haiku-4-5-20251001',
            'claude-sonnet-5',
            'claude-opus-5',
        },
    }
    for handle in server.AGENT_MODEL_OPTIONS:
        provider, model = handle.split('/', 1)
        assert provider in expected_by_prefix, handle
        assert model in expected_by_prefix[provider], handle
    for provider, expected_models in expected_by_prefix.items():
        actual = {handle.split('/', 1)[1] for handle in server.AGENT_MODEL_OPTIONS
                  if handle.startswith(f'{provider}/')}
        assert actual == expected_models, provider


# ── /api/agent-voice — dashboard TTS preference in Letta metadata ────────────

def test_agent_voice_from_metadata_validates_allowed_voice():
    assert server.agent_voice_from_metadata(
        {'metadata': {'dashboard_voice': 'en-GB-SoniaNeural'}}) == 'en-GB-SoniaNeural'
    assert server.agent_voice_from_metadata(
        {'metadata': {'dashboard_voice': 'en-US-JennyNeural'}}) == 'en-US-JennyNeural'
    assert server.agent_voice_from_metadata(
        {'metadata': {'dashboard_voice': '$(rm -rf /)'}}) == ''
    assert server.agent_voice_from_metadata({'metadata': None}) == ''


def test_patch_agent_voice_merges_metadata(monkeypatch):
    captured = {}

    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self):
            return json.dumps({
                'metadata': {
                    'existing': 'keep',
                    'dashboard_voice': 'en-US-JennyNeural',
                },
            }).encode()

    def fake_letta_get(path, **kwargs):
        assert path == '/v1/agents/agent-frita'
        return {'metadata': {'existing': 'keep'}}

    def fake_urlopen(req, timeout=0):
        captured['url'] = req.full_url
        captured['method'] = req.method
        captured['body'] = json.loads(req.data.decode())
        return _Resp()

    monkeypatch.setattr(server, 'letta_id_for', lambda agent: 'agent-frita')
    monkeypatch.setattr(server, 'letta_get', fake_letta_get)
    monkeypatch.setattr(server.urllib.request, 'urlopen', fake_urlopen)

    result = server.patch_agent_voice('agent-frita', 'en-US-JennyNeural')

    assert result == {'ok': True, 'voice': 'en-US-JennyNeural'}
    assert captured['method'] == 'PATCH'
    assert captured['url'].endswith('/v1/agents/agent-frita')
    assert captured['body'] == {
        'metadata': {
            'existing': 'keep',
            'dashboard_voice': 'en-US-JennyNeural',
        },
    }


def test_patch_agent_voice_empty_removes_metadata_key(monkeypatch):
    captured = {}

    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b'{"metadata":{"existing":"keep"}}'

    monkeypatch.setattr(server, 'letta_id_for', lambda agent: 'agent-frita')
    monkeypatch.setattr(
        server,
        'letta_get',
        lambda path, **kwargs: {
            'metadata': {
                'existing': 'keep',
                'dashboard_voice': 'en-US-JennyNeural',
            },
        },
    )
    def fake_urlopen(req, timeout=0):
        captured['body'] = json.loads(req.data.decode())
        return _Resp()

    monkeypatch.setattr(server.urllib.request, 'urlopen', fake_urlopen)

    result = server.patch_agent_voice('agent-frita', '')

    assert result == {'ok': True, 'voice': ''}
    assert captured['body'] == {'metadata': {'existing': 'keep'}}


def test_patch_agent_voice_rejects_unlisted_voice(monkeypatch):
    monkeypatch.setattr(server, 'letta_id_for', lambda agent: 'agent-frita')
    result = server.patch_agent_voice('agent-frita', 'en-US-NopeNeural')
    assert result['ok'] is False
    assert 'allowed list' in result['error']


# ── ChatGPT provider auto-failover gate ───────────────────────────────────────

def test_failover_triggers_on_rate_limit_after_cooldown():
    assert server.failover_should_trigger(
        'llm_rate_limit: 5h window 100% used, resets in 1h',
        now_ts=10_000, last_swap_ts=0, min_interval=1800)


def test_failover_respects_cooldown():
    assert not server.failover_should_trigger(
        'llm_rate_limit: 5h window 100% used, resets in 1h',
        now_ts=1000, last_swap_ts=0, min_interval=1800)


def test_failover_ignores_non_rate_limit_errors():
    # Auth/network failures must NOT trigger a swap — the standby token would
    # inherit the same problem and the swap burns the cooldown window.
    for text in ('HTTP 401: unauthorized', 'probe timed out', ''):
        assert not server.failover_should_trigger(
            text, now_ts=10_000, last_swap_ts=0, min_interval=1800)


def test_standby_verdict_separates_a_capped_account_from_a_stale_token():
    assert server.standby_probe_verdict({'ok': True, 'text': '5h 12%'}) == 'headroom'
    assert server.standby_probe_verdict(
        {'ok': False, 'text': 'llm_rate_limit: 5h window 100% used'}) == 'limited'
    # The bug this fixes: an expired parked token used to read as "also limited",
    # so a healable standby looked like a genuinely exhausted second account.
    assert server.standby_probe_verdict(
        {'ok': False, 'text': 'provider OAuth token rejected (HTTP 401)'}) == 'stale'


def test_codex_refresh_candidates_prefers_standby_then_matching_local_logins():
    standby = {'account_id': 'acct-a', 'refresh_token': 'rt-standby'}
    bundles = [
        {'tokens': {'account_id': 'acct-a', 'refresh_token': 'rt-live'}},
        {'tokens': {'account_id': 'acct-b', 'refresh_token': 'rt-other-account'}},
        {'tokens': {'account_id': 'acct-a', 'refresh_token': 'rt-standby'}},  # dup
        {'tokens': {'account_id': 'acct-a'}},                                 # no token
    ]
    assert server.codex_refresh_candidates(standby, bundles) == ['rt-standby', 'rt-live']


def test_codex_refresh_candidates_never_parks_another_accounts_token():
    standby = {'account_id': 'acct-a', 'refresh_token': None}
    bundles = [{'tokens': {'account_id': 'acct-b', 'refresh_token': 'rt-other-account'}}]
    assert server.codex_refresh_candidates(standby, bundles) == []


def test_process_pdf_document_arms_problem_only_trainer(monkeypatch, tmp_path):
    """PDF intake is watched without launching a Trainer during normal work."""
    pdf_dir = tmp_path / 'rol'
    pdf_dir.mkdir()
    pdf = pdf_dir / 'statement.pdf'
    pdf.write_bytes(b'%PDF-fake')
    monkeypatch.setattr(server, 'ROL_FINANCES_DIR', str(pdf_dir))
    monkeypatch.setattr(server, 'run_intake_facade',
                        lambda path, org_id=1, engine='gemini': {'ok': True})
    pdf_dispatch = {}

    def fake_thread(*args, **kwargs):
        pdf_dispatch['target'] = kwargs.get('target')
        pdf_dispatch['args'] = kwargs.get('args')
        return type('T', (), {'start': lambda s: None})()

    monkeypatch.setattr(server.threading, 'Thread', fake_thread)
    seen = {}

    def fake_watch(path, name, facade, conversation_id, dispatched_at):
        seen['args'] = (path, name, facade, conversation_id, dispatched_at)
        return True

    monkeypatch.setattr(server, '_watch_intake_for_problems', fake_watch)
    result = server.process_pdf_document(str(pdf), label='Jan Statement')
    assert result['trainer_dispatched'] is False
    path, name, facade, conversation_id, dispatched_at = seen['args']
    assert path == str(pdf)
    assert 'Jan Statement' in name
    assert facade == {'ok': True}
    assert conversation_id == 'conv-test-isolated'
    assert dispatched_at > 0
    assert pdf_dispatch['target'] is server._notify_mazda_of_pdf
    assert pdf_dispatch['args'][4] == {'ok': True}


# ── Recent Report (/recent_report.html) ─────────────────────────────────────


def _recent_report_env(tmp_path, monkeypatch, docs=('doc_a', 'doc_b')):
    """Point the ROL report registry at a tmp tree with the given report dirs
    (report.html written for each), and isolate the recent-report pointer."""
    parent = tmp_path / 'reports'
    for d in docs:
        (parent / 'january' / d).mkdir(parents=True)
        (parent / 'january' / d / 'report.html').write_text(
            f'<html><head><title>{d}</title></head>'
            f'<body><h1>{d}</h1></body></html>')
    monkeypatch.setattr(server, 'ROL_FINANCES_REPORTS_PARENT', str(parent))
    monkeypatch.setattr(server, 'ROL_FINANCES_REPORTS_MONTHS', {'jan-2025': 'january'})
    monkeypatch.setattr(server, 'ROL_FINANCE_REPORTS', [
        {'key': d, 'label': d, 'dir': d} for d in docs])
    monkeypatch.setattr(server, 'RECENT_REPORT_POINTER_FILE',
                        str(tmp_path / 'recent_report.json'))
    # The intake page derives the canonical bank_statements archive copy by
    # searching READABLE_DOCS_BASE. Left unisolated it searches the LIVE
    # ~/rol_finances tree, so these tests pass or fail based on which real
    # statements happen to be filed on the machine running them.
    readable_docs = tmp_path / 'readable_documents'
    readable_docs.mkdir(exist_ok=True)
    monkeypatch.setattr(server, 'READABLE_DOCS_BASE', str(readable_docs))
    return parent


def test_recent_report_pointer_roundtrip(tmp_path, monkeypatch):
    _recent_report_env(tmp_path, monkeypatch)
    url = '/rol_finances_reports/jan-2025/doc_a/report.html'
    assert server.set_recent_report_pointer(url) is True
    assert server._load_recent_report_pointer()['report_path'] == url
    # A URL that doesn't resolve to a real report is rejected and not stored.
    assert server.set_recent_report_pointer(
        '/rol_finances_reports/jan-2025/nope/report.html') is False
    assert server._load_recent_report_pointer()['report_path'] == url


def test_resolve_recent_report_prefers_newer_of_pointer_and_mtime(
        tmp_path, monkeypatch):
    parent = _recent_report_env(tmp_path, monkeypatch)
    a_url = '/rol_finances_reports/jan-2025/doc_a/report.html'
    server.set_recent_report_pointer(a_url)
    # Pointer is newest → doc_a wins even if doc_b's file exists.
    old = time.time() - 3600
    os.utime(parent / 'january' / 'doc_b' / 'report.html', (old, old))
    assert server.resolve_recent_report()['url'] == a_url
    # Mazda rewrites doc_b on disk (mtime in the future of the pointer) →
    # doc_b becomes the most recently processed document, no callback needed.
    new = time.time() + 3600
    os.utime(parent / 'january' / 'doc_b' / 'report.html', (new, new))
    resolved = server.resolve_recent_report()
    assert resolved['url'] == '/rol_finances_reports/jan-2025/doc_b/report.html'
    assert resolved['file'].endswith('doc_b/report.html')


def test_build_recent_report_html_injects_base_href(tmp_path, monkeypatch):
    _recent_report_env(tmp_path, monkeypatch)
    server.set_recent_report_pointer(
        '/rol_finances_reports/jan-2025/doc_a/report.html')
    html = server.build_recent_report_html()
    assert '<base href="/rol_finances_reports/jan-2025/doc_a/">' in html
    assert '<h1>doc_a</h1>' in html
    # <base> must land inside <head> so it applies to the whole document.
    assert html.index('<head>') < html.index('<base href=')


def test_build_recent_report_html_placeholder_when_nothing_processed(
        tmp_path, monkeypatch):
    _recent_report_env(tmp_path, monkeypatch, docs=())
    html = server.build_recent_report_html()
    assert 'No document has been processed yet' in html


def test_record_stored_expense_updates_recent_report_pointer(
        tmp_path, monkeypatch):
    _recent_report_env(tmp_path, monkeypatch)
    url = '/rol_finances_reports/jan-2025/doc_b/report.html'
    server.record_stored_expense({
        'kind': 'receipt', 'expense_id': 7, 'expense_date': '2025-01-05',
        'amount': '12.34', 'report_path': url,
    })
    assert server._load_recent_report_pointer()['report_path'] == url


def test_record_stored_expense_does_not_hijack_pointer_on_coincidental_match(
        tmp_path, monkeypatch):
    # A stored expense whose (date, amount) happens to also match a row in
    # some unrelated existing report must NOT move the recent-report pointer
    # there — only an event that explicitly names its own report_path should.
    # Otherwise a scanned receipt's dispatch (which is genuinely the most
    # recent thing processed) gets shadowed by that unrelated report's full
    # transaction table. See dashboard_recent_report_pointer_hijack fix.
    parent = _recent_report_env(tmp_path, monkeypatch)
    (parent / 'january' / 'doc_a' / 'report.html').write_text(
        '<html><head></head><body><table><tr data-vendor-key="kum_go">'
        '<td>2025-01-05</td><td>Kum & Go</td><td>12.34</td></tr>'
        '</table></body></html>')
    assert server._load_recent_report_pointer() is None
    server.record_stored_expense({
        'kind': 'receipt', 'expense_id': 8, 'expense_date': '2025-01-05',
        'amount': '12.34', 'vendor_key': 'kum_go',
    })
    assert server._load_recent_report_pointer() is None


def test_resolve_report_path_alias_translates_recent_report(tmp_path, monkeypatch):
    _recent_report_env(tmp_path, monkeypatch)
    url = '/rol_finances_reports/jan-2025/doc_a/report.html'
    server.set_recent_report_pointer(url)
    # The picker inside /recent_report.html posts location.pathname — translate.
    assert server._resolve_report_path_alias('/recent_report.html') == url
    # Real report paths and blanks pass through untouched.
    assert server._resolve_report_path_alias(url) == url
    assert server._resolve_report_path_alias('') == ''


# ── Recent Report: intake mode (documents with no report.html) ──────────────


def test_process_scanned_document_records_recent_intake(tmp_path, monkeypatch):
    scan_dir = tmp_path / 'scans'
    scan_dir.mkdir()
    write_scan_image(scan_dir / 'window_scan.jpg')
    monkeypatch.setattr(server, 'SCAN_TOOLS_DIR', str(scan_dir))
    monkeypatch.setattr(server, 'SCANNERS', {
        'window': {'name': 'Window Scanner', 'script': 'x.sh', 'output': 'window_scan.jpg'},
    })
    monkeypatch.setattr(server, 'run_intake_facade',
                        lambda *a, **kw: {'ok': True, 'doc_kind': 'unknown', 'confidence': 0})
    monkeypatch.setattr(server, 'document_vision_health', lambda *a, **kw: {'ok': True})
    monkeypatch.setattr(server, 'inspect_scan_image_quality',
                        lambda _path: {'ok': True})
    staged = '/home/adamsl/rol_finances/tools/receipt_scanning_tools/incoming_scans/window_scan.jpg'
    monkeypatch.setattr(server, '_stage_scan_for_mazda', lambda p: staged)
    monkeypatch.setattr(server.threading, 'Thread',
                        lambda *a, **k: type('T', (), {'start': lambda s: None})())

    result = server.process_scanned_document('window')
    assert result['mazda_dispatched'] is True
    intake = server._read_recent_pointer_file().get('intake')
    assert intake['document'] == 'window_scan.jpg'
    assert intake['image_path'] == staged
    assert intake['label'] == 'Window Scanner'
    assert intake['kind'] == 'scan'
    # The intake (no report.html for a scan) is what /recent_report.html shows.
    resolved = server.resolve_recent_report()
    assert resolved['mode'] == 'intake'
    assert resolved['intake']['document'] == 'window_scan.jpg'


def test_process_scanned_document_second_call_does_not_redispatch(
        tmp_path, monkeypatch):
    """Server auto-dispatch + the frontend's process-document POST both land in
    process_scanned_document; the second must not send Mazda the same image."""
    scan_dir = tmp_path / 'scans'
    scan_dir.mkdir()
    write_scan_image(scan_dir / 'window_scan.jpg')
    monkeypatch.setattr(server, 'SCAN_TOOLS_DIR', str(scan_dir))
    monkeypatch.setattr(server, 'SCANNERS', {
        'window': {'name': 'Window Scanner', 'script': 'x.sh', 'output': 'window_scan.jpg'},
    })
    monkeypatch.setattr(server, 'run_intake_facade',
                        lambda *a, **kw: {'ok': True, 'doc_kind': 'unknown', 'confidence': 0})
    monkeypatch.setattr(server, 'document_vision_health', lambda *a, **kw: {'ok': True})
    monkeypatch.setattr(server, '_stage_scan_for_mazda', lambda p: '/staged/window_scan.jpg')
    dispatches = []

    def _fake_thread(target, args, daemon):
        dispatches.append(args)
        return type('T', (), {'start': lambda s: None})()

    monkeypatch.setattr(server.threading, 'Thread', _fake_thread)

    first = server.process_scanned_document('window')
    second = server.process_scanned_document('window')
    assert first['mazda_dispatched'] is True
    assert 'already_dispatched' not in first
    assert len(dispatches) == 1
    assert second['already_dispatched'] is True
    assert second['mazda_dispatched'] is True  # frontend still renders delegated stages


def test_failed_scan_fingerprint_can_be_retried_after_restart(
        tmp_path, monkeypatch):
    """Duplicate suppression must not permanently burn a failed document."""
    scan = tmp_path / 'window_scan.jpg'
    scan.write_bytes(b'legitimate-statement')
    digest = server._scan_content_sha256(str(scan))
    monkeypatch.setattr(server, 'SCANNERS', {
        'window': {'name': 'Window Scanner', 'output': scan.name},
    })
    monkeypatch.setattr(server, 'get_scanner_intake', lambda key: {
        'content_sha256': digest,
        'status': 'fail',
    })
    server._scan_dispatch_claims.clear()

    assert server._claim_scan_dispatch('window', str(scan), digest) is True


def test_completed_scan_fingerprint_remains_suppressed(tmp_path, monkeypatch):
    scan = tmp_path / 'window_scan.jpg'
    scan.write_bytes(b'already-processed-statement')
    digest = server._scan_content_sha256(str(scan))
    monkeypatch.setattr(server, 'SCANNERS', {
        'window': {'name': 'Window Scanner', 'output': scan.name},
    })
    monkeypatch.setattr(server, 'get_scanner_intake', lambda key: {
        'content_sha256': digest,
        'status': 'complete',
    })
    server._scan_dispatch_claims.clear()

    assert server._claim_scan_dispatch('window', str(scan), digest) is False


def test_failed_staging_releases_the_dispatch_claim(tmp_path, monkeypatch):
    """A staging failure must not burn the claim — the retry has to dispatch."""
    scan_dir = tmp_path / 'scans'
    scan_dir.mkdir()
    write_scan_image(scan_dir / 'window_scan.jpg')
    monkeypatch.setattr(server, 'SCAN_TOOLS_DIR', str(scan_dir))
    monkeypatch.setattr(server, 'SCANNERS', {
        'window': {'name': 'Window Scanner', 'script': 'x.sh', 'output': 'window_scan.jpg'},
    })
    monkeypatch.setattr(server, 'run_intake_facade',
                        lambda *a, **kw: {'ok': True, 'doc_kind': 'unknown', 'confidence': 0})
    monkeypatch.setattr(server, 'document_vision_health', lambda *a, **kw: {'ok': True})
    monkeypatch.setattr(server.threading, 'Thread',
                        lambda *a, **k: type('T', (), {'start': lambda s: None})())

    monkeypatch.setattr(server, '_stage_scan_for_mazda', lambda p: None)
    failed = server.process_scanned_document('window')
    assert failed['mazda_dispatched'] is False

    monkeypatch.setattr(server, '_stage_scan_for_mazda', lambda p: '/staged/window_scan.jpg')
    retried = server.process_scanned_document('window')
    assert retried['mazda_dispatched'] is True
    assert 'already_dispatched' not in retried


def test_run_scanner_auto_dispatches_intake_when_ready(monkeypatch):
    """The SERVER fires intake after a ready scan — a closed browser can no
    longer lose the document (2026-07-12 lesson)."""
    monkeypatch.setattr(server, '_invoke_scanner', lambda key: {'status': 'ready'})
    spawned = []

    def _fake_thread(target, args, daemon):
        spawned.append((target, args))
        return type('T', (), {'start': lambda s: None})()

    monkeypatch.setattr(server.threading, 'Thread', _fake_thread)
    result = server.run_scanner('window')
    assert result['ok'] is True
    assert spawned == [(server.process_scanned_document, ('window',))]


def test_run_scanner_does_not_dispatch_on_busy(monkeypatch):
    monkeypatch.setattr(server, '_invoke_scanner', lambda key: {'status': 'busy'})
    spawned = []
    monkeypatch.setattr(server.threading, 'Thread',
                        lambda *a, **k: spawned.append(a) or type('T', (), {'start': lambda s: None})())
    result = server.run_scanner('window')
    assert result['ok'] is False
    assert spawned == []


def test_classify_scan_result_explains_empty_successful_output():
    result = server.classify_scan_result(0, '', False)

    assert result['status'] == 'error'
    assert result['empty_output'] is True
    assert 'missing or empty' in result['error']


def test_run_scanner_publishes_empty_output_as_failed_intake(monkeypatch):
    monkeypatch.setattr(server, 'SCANNERS', {
        'window': {'name': 'Window Scanner', 'output': 'window_scan.jpg'},
    })
    monkeypatch.setattr(server, '_scanner_intake_in_progress', lambda _key: False)
    monkeypatch.setattr(server, '_invoke_scanner', lambda _key: {
        'status': 'error',
        'error': 'scanner output is missing or empty',
        'empty_output': True,
    })
    recorded = []
    monkeypatch.setattr(
        server, 'record_recent_intake',
        lambda *args, **kwargs: recorded.append((args, kwargs)) or True,
    )

    result = server.run_scanner('window')

    assert result['ok'] is False
    assert recorded[0][0][1] == 'Window Scanner'
    assert recorded[0][1]['status'] == 'fail'
    assert recorded[0][1]['status_detail'] == result['error']


def test_scanner_status_is_read_only(monkeypatch):
    monkeypatch.setattr(server, 'SCANNERS', {'freezer': {'name': 'Freezer Scanner'}})
    monkeypatch.setattr(server, '_scanner_intake_in_progress', lambda _key: False)
    monkeypatch.setattr(
        server, '_invoke_scanner',
        lambda _key: (_ for _ in ()).throw(AssertionError('status GET started a scan')))
    server._scanner_runtime_status.clear()

    assert server.scanner_status('freezer') == {'status': 'idle', 'ok': True}


def test_scanner_status_exposes_active_intake_lock_without_scanning(monkeypatch):
    monkeypatch.setattr(server, 'SCANNERS', {'freezer': {'name': 'Freezer Scanner'}})
    monkeypatch.setattr(server, '_scanner_intake_in_progress', lambda _key: True)
    monkeypatch.setattr(
        server, '_invoke_scanner',
        lambda _key: (_ for _ in ()).throw(AssertionError('status GET started a scan')))

    result = server.scanner_status('freezer')

    assert result['status'] == 'intake_busy'
    assert result['ok'] is False
    assert 'still being verified' in result['error']


def test_run_scanner_blocks_while_previous_intake_is_being_verified(monkeypatch):
    monkeypatch.setattr(server, '_scanner_intake_in_progress', lambda _key: True)
    monkeypatch.setattr(
        server, '_invoke_scanner',
        lambda _key: (_ for _ in ()).throw(AssertionError('started overlapping scan')))

    result = server.run_scanner('freezer')

    assert result['status'] == 'intake_busy'
    assert result['ok'] is False


def test_clear_scanner_verification_lock_marks_exact_intake_stalled(monkeypatch):
    intake = {
        'conversation_id': 'conv-window-stuck',
        'image_path': '/staged/window_scan.jpg',
        'dispatched_at': 1234.5,
        'status': 'processing',
    }
    captured = []
    monkeypatch.setattr(server, 'SCANNERS', {'window': {'name': 'Window Scanner'}})
    monkeypatch.setattr(server, 'get_scanner_intake', lambda _key: intake)
    monkeypatch.setattr(server, '_scanner_intake_in_progress', lambda _key: True)
    monkeypatch.setattr(
        server, 'merge_recent_intake_status',
        lambda update: captured.append(update) or True)

    result = server.clear_scanner_verification_lock('window')

    assert result == {'ok': True, 'cleared': True, 'status': 'idle'}
    assert captured == [{
        'conversation_id': 'conv-window-stuck',
        'document_path': '/staged/window_scan.jpg',
        'dispatched_at': 1234.5,
        'status': 'stalled',
        'detail': ('Verification lock cleared manually from the scanner view; '
                   'the scan and financial records were left unchanged.'),
    }]
    assert server._scanner_runtime_status['window'] == {
        'status': 'idle', 'ok': True}


def test_clear_scanner_verification_lock_is_noop_without_active_lock(monkeypatch):
    monkeypatch.setattr(server, 'SCANNERS', {'freezer': {'name': 'Freezer Scanner'}})
    monkeypatch.setattr(server, 'get_scanner_intake', lambda _key: {'status': 'pass'})
    monkeypatch.setattr(server, '_scanner_intake_in_progress', lambda _key: False)
    monkeypatch.setattr(
        server, 'merge_recent_intake_status',
        lambda _update: (_ for _ in ()).throw(AssertionError('changed intake')))

    result = server.clear_scanner_verification_lock('freezer')

    assert result['ok'] is True
    assert result['cleared'] is False


def test_persisted_content_fingerprint_prevents_restart_redispatch(
        tmp_path, monkeypatch):
    scan = tmp_path / 'window_scan.jpg'
    scan.write_bytes(b'same-physical-scan')
    digest = server._scan_content_sha256(scan)
    monkeypatch.setattr(server, 'SCANNERS', {
        'window': {'name': 'Window Scanner', 'output': 'window_scan.jpg'},
    })
    monkeypatch.setattr(server, 'get_scanner_intake', lambda _key: {
        'content_sha256': digest,
    })
    server._scan_dispatch_claims.clear()

    assert server._claim_scan_dispatch('window', scan, digest) is False


def test_merge_recent_intake_event_folds_ids_and_counts(tmp_path, monkeypatch):
    _recent_report_env(tmp_path, monkeypatch, docs=())
    server.record_recent_intake('/staged/scan_freezer.jpg', 'Freezer Scanner')
    server.record_stored_expense({
        'kind': 'statement', 'expense_id': 101, 'expense_ids': [101, 102],
        'parsed': 10, 'stored': 2,
        'expense_date': '2025-06-01', 'amount': '12.34',
    })
    intake = server._read_recent_pointer_file()['intake']
    assert intake['expense_ids'] == [101, 102]
    assert intake['parsed'] == 10
    assert intake['stored'] == 2
    assert intake['reported_at'] > 0


def _reader_visible_html(html):
    """`html` minus the manual-entry mount point.

    The Save-by-hand / review form is on every report page since 2026-08-19,
    and it carries the staged image path in a data attribute because both
    "Show Image" and "Mazda Fill" need to know which file this page is about.
    That is form state the browser reads, not something the page shows anyone.

    The rule these assertions protect — the temporary staging directory is
    never advertised to the reader — is about rendered text, so it is checked
    against the page with that one element removed rather than weakened. Any
    staged path appearing anywhere else is still a failure.
    """
    return re.sub(r'<div id="manual-entry-root"[^>]*></div>', '', html)

def test_recent_intake_html_lists_expenses_with_picker(tmp_path, monkeypatch):
    _recent_report_env(tmp_path, monkeypatch, docs=())
    server.record_recent_intake('/staged/scan_freezer.jpg', 'Freezer Scanner')
    server.merge_recent_intake_event({'expense_ids': [7], 'parsed': 1, 'stored': 1})
    monkeypatch.setattr(server, '_fetch_expenses_by_ids', lambda ids: [{
        'date': '2025-06-01', 'amount': '-12.34', 'vendor_key': 'kum_go',
        'description': 'Kum & Go', 'reporting_category': 'Travel & Vehicle',
        'cat_class': 'cat-travel-and-vehicle',
    }])
    monkeypatch.setattr(server, '_receipt_only_picker_assets',
                        lambda: ('/*css*/', '<div id="rol-category-picker"></div>', '/*rowcss*/'))
    html = server.build_recent_report_html()
    # The staging directory a document is being processed in is never exposed.
    assert '/staged/' not in _reader_visible_html(html)
    assert 'verified-transactions' in html
    assert 'data-vendor-key="kum_go"' in html
    assert 'rol-category-picker' in html
    assert 'openCategoryPicker' in html


def test_recent_intake_html_seeds_the_review_dialog_with_stored_findings(
        tmp_path, monkeypatch):
    """An automatic scan's STEP 8 findings must reach the review dialog, not
    just Verified Transactions — the operator needs something to check/correct
    without pressing Mazda Fill again. Two non-duplicate rows also means
    Prev/Next has something to walk (see manual-entry-form.js's _navigate)."""
    _recent_report_env(tmp_path, monkeypatch, docs=())
    server.record_recent_intake('/staged/scan_freezer.jpg', 'Freezer Scanner')
    server.merge_recent_intake_event({'expense_ids': [7, 8], 'parsed': 2, 'stored': 2})
    monkeypatch.setattr(server, '_fetch_expenses_by_ids', lambda ids: [
        {'id': 7, 'date': '2025-06-01', 'amount': '-12.34', 'vendor_key': 'kum_go',
         'description': 'Kum & Go', 'reporting_category': 'Travel & Vehicle',
         'cat_class': 'cat-travel-and-vehicle'},
        {'id': 8, 'date': '2025-06-02', 'amount': '-45.00', 'vendor_key': 'meijer',
         'description': 'Meijer', 'reporting_category': 'Household',
         'cat_class': 'cat-household'},
    ])
    monkeypatch.setattr(server, '_receipt_only_picker_assets',
                        lambda: ('/*css*/', '<div id="rol-category-picker"></div>', '/*rowcss*/'))
    html = server.build_recent_report_html()
    assert 'data-mazda-findings="' in html
    assert '&quot;merchant_name&quot;: &quot;Kum &amp; Go&quot;' in html
    assert '&quot;merchant_name&quot;: &quot;Meijer&quot;' in html


def test_picker_module_imports_for_real():
    """Regression: _picker_module() only added VERIFICATION_LIB to sys.path,
    so restructure_verified_transactions' own `from tools.python_tasks...`
    import had nowhere to find the `tools` package — every report.html 500'd
    with ModuleNotFoundError. It only appeared to work when some unrelated
    request had already put ROL_FINANCES_DIR on this (process-global,
    restart-cleared) sys.path first. Every other test exercising this path
    monkeypatches _picker_module/_receipt_only_picker_assets away, so none of
    them would have caught it — this one calls the real import."""
    module = server._picker_module()
    assert hasattr(module, 'add_category_picker')


def test_default_statement_account_directory_imports_for_real():
    """Same sys.path shape as _picker_module (see _ensure_sys_path): a
    real, unpatched call must resolve `tools.receipt_scanning_tools...`."""
    workbook = server._default_statement_account_directory()
    assert workbook is not None


def test_recent_intake_html_duplicates_note_when_nothing_stored(
        tmp_path, monkeypatch):
    _recent_report_env(tmp_path, monkeypatch, docs=())
    server.record_recent_intake('/staged/scan_freezer.jpg', 'Freezer Scanner')
    server.merge_recent_intake_event({'expense_ids': [], 'parsed': 10, 'stored': 0})
    monkeypatch.setattr(server, '_receipt_only_picker_assets',
                        lambda: ('', '', ''))
    html = server.build_recent_report_html()
    assert 'already in the' in html and 'duplicates' in html
    # The Verified Transactions section always renders after a scan so a human
    # can verify it — even a duplicate-only run with no resolvable rows shows
    # the table (with an empty-state placeholder), never an omitted section.
    assert '<table id="verified-transactions"' in html
    assert 'nothing to verify' in html


def test_recent_intake_html_empty_scan_still_shows_verified_section(
        tmp_path, monkeypatch):
    # A scan that parsed 0 transactions (e.g. a non-financial "other" document)
    # must still render the Verified Transactions section for human review,
    # rather than the section vanishing entirely.
    _recent_report_env(tmp_path, monkeypatch, docs=())
    server.record_recent_intake('/staged/window_scan.jpg', 'Window Scanner')
    server.merge_recent_intake_event({'expense_ids': [], 'parsed': 0, 'stored': 0})
    monkeypatch.setattr(server, '_receipt_only_picker_assets', lambda: ('', '', ''))
    data = server._read_recent_pointer_file()
    html = server.build_recent_intake_html(data['scanner_intakes']['Window Scanner'])
    assert '<h2>Verified Transactions</h2>' in html
    assert '<table id="verified-transactions"' in html
    assert 'nothing to verify' in html
    # Reported back → no auto-refresh spinner state.
    assert 'http-equiv="refresh"' not in html


def test_recent_intake_html_pending_refreshes(tmp_path, monkeypatch):
    _recent_report_env(tmp_path, monkeypatch, docs=())
    server.record_recent_intake('/staged/window_scan.jpg', 'Window Scanner')
    monkeypatch.setattr(server, '_receipt_only_picker_assets',
                        lambda: ('', '', ''))
    monkeypatch.setattr(server, 'mazda_intake_progress', lambda _intake: {
        'steps': [
            {'label': 'STEP 1 — Load learned wrapper', 'status': 'done'},
            {'label': 'STEP 2 — Check vendor and duplicates', 'status': 'active'},
        ],
        'completed': 1,
        'required': 2,
        'percent': 50,
    })
    html = server.build_recent_report_html()
    assert 'Dispatched to Mazda' in html
    assert 'http-equiv="refresh"' in html
    assert '<div class="mazda-working"' in html
    assert 'Mazda Working' in html
    assert '1 of 2 required steps complete' in html
    assert 'STEP 1 — Load learned wrapper' in html
    assert 'STEP 2 — Check vendor and duplicates' in html
    assert 'class="mazda-progress-bar" style="width:50%"' in html


def test_recent_intake_html_finished_hides_mazda_working_panel(
        tmp_path, monkeypatch):
    _recent_report_env(tmp_path, monkeypatch, docs=())
    server.record_recent_intake('/staged/window_scan.jpg', 'Window Scanner')
    server.merge_recent_intake_event({'expense_ids': [], 'parsed': 0, 'stored': 0})
    monkeypatch.setattr(server, '_receipt_only_picker_assets',
                        lambda: ('', '', ''))

    html = server.build_recent_report_html()

    assert '<div class="mazda-working"' not in html
    assert 'nothing to verify' in html


def test_late_expense_callback_does_not_relock_trainer_pass(
        tmp_path, monkeypatch):
    _recent_report_env(tmp_path, monkeypatch, docs=())
    server.record_recent_intake(
        '/staged/window_scan.jpg', 'Window Scanner',
        conversation_id='conv-window', dispatched_at=100.0)
    assert server.record_intake_status({
        'status': 'PASS', 'conversation_id': 'conv-window',
        'document_path': '/staged/window_scan.jpg', 'dispatched_at': 100.0,
    })['ok'] is True

    server.merge_recent_intake_event({
        'document_path': '/staged/window_scan.jpg',
        'conversation_id': 'conv-window', 'dispatched_at': 100.0,
        'parsed': 0, 'stored': 0,
    })

    intake = server.get_scanner_intake('window')
    assert intake['status'] == 'pass'
    assert server._scanner_intake_in_progress('window') is False


def test_completed_intake_does_not_keep_scanner_locked(tmp_path, monkeypatch):
    _recent_report_env(tmp_path, monkeypatch, docs=())
    server.record_recent_intake(
        '/staged/window_scan.jpg', 'Window Scanner', dispatched_at=time.time())
    assert server._scanner_intake_in_progress('window') is True

    server.merge_recent_intake_event({
        'document_path': '/staged/window_scan.jpg',
        'parsed': 1,
        'stored': 1,
    })

    intake = server.get_scanner_intake('window')
    assert intake['status'] == 'complete'
    assert server._scanner_intake_in_progress('window') is False


def test_intake_halt_record_read_and_acknowledge(tmp_path, monkeypatch):
    monkeypatch.setattr(server, 'INTAKE_HALT_FILE', str(tmp_path / 'intake_halt.json'))

    # Nothing recorded yet.
    assert server.read_intake_halt() == {'ok': True, 'active': False}

    # rol_finances' DashboardIntakeHaltNotifier POSTs a halt.
    assert server.record_intake_halt({
        'step': 'source-counterpart-lookup',
        'cause': 'not enough arguments for format string',
        'exception_type': 'TypeError',
        'document_path': '/scan.jpg',
        'repo_path': '/home/adamsl/rol_finances',
        'metadata': {'amount': '100.00'},
    }) == {'ok': True, 'active': True}

    state = server.read_intake_halt()
    assert state['active'] is True
    assert state['event']['step'] == 'source-counterpart-lookup'
    assert state['event']['exception_type'] == 'TypeError'
    assert state['event']['metadata'] == {'amount': '100.00'}

    # A human acknowledges — the alert clears but the record persists.
    assert server.acknowledge_intake_halt() == {'ok': True, 'active': False}
    assert server.read_intake_halt() == {'ok': True, 'active': False}


def test_intake_halt_acknowledge_with_no_record_is_safe(tmp_path, monkeypatch):
    monkeypatch.setattr(server, 'INTAKE_HALT_FILE', str(tmp_path / 'missing.json'))
    assert server.acknowledge_intake_halt() == {'ok': True, 'active': False}


def test_mazda_progress_uses_successful_tool_returns_not_calls():
    def call(call_id, name, arguments=None):
        return {
            'message_type': 'tool_call_message',
            'tool_call': {
                'tool_call_id': call_id,
                'name': name,
                'arguments': arguments or {},
            },
        }

    def returned(call_id, content='{}', status='success'):
        return {
            'message_type': 'tool_return_message',
            'tool_call_id': call_id,
            'status': status,
            'tool_return': content,
        }

    messages = [
        returned('wrapper'),
        call('wrapper', 'load_wrapper_revision'),
        # This call has no return and must not advance STEP 2.
        call('vendor', 'check_vendor_key'),
        returned('classify', json.dumps({
            'returncode': 0,
            'stdout': '{"doc_type":"receipt","confidence":0.98}',
        })),
        call('classify', 'executor_run', {
            'command': 'python tools/classify_scan.py /scan.jpg',
        }),
        returned('parse', json.dumps({'returncode': 0, 'stdout': '{}'})),
        call('parse', 'executor_run', {
            'command': 'python parse_and_categorize.py -f /scan.jpg --json',
        }),
    ]

    progress = server._mazda_progress_from_messages(
        {'doc_kind': 'unknown'}, messages)

    by_label = {step['label']: step['status'] for step in progress['steps']}
    assert by_label['STEP 0 — Load learned wrapper'] == 'done'
    assert by_label['STEP 1 — Classify and parse document'] == 'done'
    assert by_label['STEP 2 — Check vendor and duplicates'] == 'active'
    assert progress['completed'] == 2
    assert progress['percent'] == 22


def test_mazda_progress_marks_pass_only_improvement_step_skipped():
    messages = [
        {
            'message_type': 'tool_call_message',
            'tool_call': {
                'tool_call_id': 'judge',
                'name': 'judge_trace',
                'arguments': {'trace_id': 10},
            },
        },
        {
            'message_type': 'tool_return_message',
            'tool_call_id': 'judge',
            'status': 'success',
            'tool_return': '{"verdict":"PASS"}',
        },
    ]

    progress = server._mazda_progress_from_messages(
        {'doc_kind': 'receipt'}, messages)

    improvement = next(
        step for step in progress['steps'] if step['label'].startswith('STEP 7'))
    assert improvement['status'] == 'skipped'
    # STEP 0 was supplied by the facade and STEP 7 was unnecessary on PASS.
    assert progress['required'] == 7


def test_mazda_statement_progress_counts_validated_preflight_as_done():
    progress = server._mazda_progress_from_messages(
        {'doc_kind': 'statement'}, [])

    preflight = next(
        step for step in progress['steps'] if step['label'].startswith('STEP 2'))
    assert preflight['status'] == 'done'


def test_statement_review_success_publishes_ids_to_recent_report(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        server, 'merge_recent_intake_event',
        lambda event: seen.update(event) or True,
    )

    assert server.merge_statement_review_result({
        'report': {
            'ok': True,
            'source_file': '/scans/statement.jpg',
            'transactions_parsed': 1,
            'stored': 0,
            'expense_ids': [],
            'duplicate_expense_ids': [1541],
            'bank_name': 'Chase',
        },
    }) is True

    assert seen['document_path'] == '/scans/statement.jpg'
    assert seen['duplicate_expense_ids'] == [1541]
    assert seen['doc_kind'] == 'statement'


def test_trainer_fail_status_targets_exact_conversation_and_stops_refresh(
        tmp_path, monkeypatch):
    _recent_report_env(tmp_path, monkeypatch, docs=())
    server.record_recent_intake(
        '/staged/window_scan.jpg', 'Window Scanner', conversation_id='conv-window',
        dispatched_at=100.0)
    server.record_recent_intake(
        '/staged/scan_freezer.jpg', 'Freezer Scanner', conversation_id='conv-freezer',
        dispatched_at=101.0)

    assert server.record_intake_status({
        'status': 'FAIL', 'detail': 'invoice branch stopped before storage',
        'conversation_id': 'conv-window', 'document_path': '/staged/window_scan.jpg',
        'dispatched_at': 100.0, 'report_path': '/reports/window.md',
    })['ok'] is True

    data = server._read_recent_pointer_file()
    window = data['scanner_intakes']['Window Scanner']
    freezer = data['scanner_intakes']['Freezer Scanner']
    assert window['status'] == 'fail'
    assert freezer['status'] == 'processing'
    monkeypatch.setattr(server, '_receipt_only_picker_assets', lambda: ('', '', ''))
    html = server.build_recent_intake_html(window)
    assert 'Trainer reported FAILED' in html
    assert 'invoice branch stopped before storage' in html
    assert 'http-equiv="refresh"' not in html


def test_trainer_status_without_exact_match_does_not_clobber_latest(
        tmp_path, monkeypatch):
    _recent_report_env(tmp_path, monkeypatch, docs=())
    server.record_recent_intake(
        '/staged/window_scan.jpg', 'Window Scanner', conversation_id='conv-current',
        dispatched_at=200.0)
    assert server.record_intake_status({
        'status': 'FAIL', 'conversation_id': 'conv-old',
        'document_path': '/staged/window_scan.jpg', 'dispatched_at': 100.0,
    })['ok'] is False
    assert server._read_recent_pointer_file()['intake']['status'] == 'processing'


# ── Per-scanner reports (/scanner_report.html) ──────────────────────────────


def _scanner_registry(monkeypatch):
    monkeypatch.setattr(server, 'SCANNERS', {
        'window': {'name': 'Window Scanner', 'script': 'w.sh', 'output': 'window_scan.jpg'},
        'freezer': {'name': 'Freezer Scanner', 'script': 'f.sh',
                    'output': 'scan_freezer.jpg'},
    })


def test_record_recent_intake_keeps_per_scanner_records(tmp_path, monkeypatch):
    _recent_report_env(tmp_path, monkeypatch, docs=())
    server.record_recent_intake('/staged/window_scan.jpg', 'Window Scanner')
    server.record_recent_intake('/staged/scan_freezer.jpg', 'Freezer Scanner')
    data = server._read_recent_pointer_file()
    # Shared record = last dispatch of any kind (the Recent Report tab).
    assert data['intake']['label'] == 'Freezer Scanner'
    # Each scanner's record survives the other scanner's dispatch.
    assert data['scanner_intakes']['Window Scanner']['image_path'] == '/staged/window_scan.jpg'
    assert (data['scanner_intakes']['Freezer Scanner']['image_path']
            == '/staged/scan_freezer.jpg')
    # A PDF/reprocess intake updates the shared record only.
    server.record_recent_intake('/docs/stmt.pdf', 'Reprocess', kind='pdf')
    data = server._read_recent_pointer_file()
    assert data['intake']['label'] == 'Reprocess'
    assert set(data['scanner_intakes']) == {'Window Scanner', 'Freezer Scanner'}


def test_blank_scan_publishes_failed_intake_to_its_own_scanner(
        tmp_path, monkeypatch):
    """A blank/unreadable capture must replace that scanner's own last intake.

    Without this the rejection is invisible to the pointer file, so Last Window
    Scan keeps rendering the PREVIOUS document and a failed capture reads as a
    stuck scanner rather than a failed one. The other scanner's tab must be
    untouched.
    """
    _recent_report_env(tmp_path, monkeypatch, docs=())
    scan_dir = tmp_path / 'scans'
    scan_dir.mkdir()
    # A genuinely blank page: uniform white, nothing to read.
    from PIL import Image
    Image.new('L', (600, 800), color=255).save(
        str(scan_dir / 'window_scan.jpg'), format='JPEG')
    monkeypatch.setattr(server, 'SCAN_TOOLS_DIR', str(scan_dir))
    monkeypatch.setattr(server, 'SCANNERS', {
        'window': {'name': 'Window Scanner', 'script': 'window.sh',
                   'output': 'window_scan.jpg'},
        'freezer': {'name': 'Freezer Scanner', 'script': 'freezer.sh',
                    'output': 'scan_freezer.jpg'},
    })
    monkeypatch.setattr(server, 'run_intake_facade', _unexpected_facade_call)
    server.record_recent_intake('/staged/prior_window.jpg', 'Window Scanner')
    server.record_recent_intake('/staged/scan_freezer.jpg', 'Freezer Scanner')

    result = server.process_scanned_document('window')

    assert result['ok'] is False
    assert result['mazda_dispatched'] is False
    window = server.get_scanner_intake('window')
    assert window['status'] == 'fail'
    assert window['image_path'].endswith('window_scan.jpg')
    assert 'blank' in window['status_detail'].lower()
    # The Freezer tab is a different physical scanner and must not move.
    assert (server.get_scanner_intake('freezer')['image_path']
            == '/staged/scan_freezer.jpg')


def _unexpected_facade_call(*_args, **_kwargs):
    raise AssertionError('a blank scan must be rejected before the facade runs')


def test_merge_routes_event_to_matching_scanner_intake(tmp_path, monkeypatch):
    """Two scanners running concurrently: a STEP 8 event carrying its source
    document path folds ONLY into the scan it belongs to, even after the other
    scanner's dispatch overwrote the shared intake record."""
    _recent_report_env(tmp_path, monkeypatch, docs=())
    server.record_recent_intake('/staged/window_scan.jpg', 'Window Scanner')
    server.record_recent_intake('/staged/scan_freezer.jpg', 'Freezer Scanner')
    server.merge_recent_intake_event({
        'document_path': '/staged/window_scan.jpg', 'expense_ids': [11],
        'parsed': 1, 'stored': 1})
    data = server._read_recent_pointer_file()
    assert data['scanner_intakes']['Window Scanner']['expense_ids'] == [11]
    assert data['scanner_intakes']['Freezer Scanner']['expense_ids'] == []
    # The shared record is the freezer's scan — the window event must not touch it.
    assert data['intake']['expense_ids'] == []
    # receipt_url doubles as the document path (older STEP 8 template).
    server.merge_recent_intake_event({
        'receipt_url': '/staged/scan_freezer.jpg', 'expense_ids': [22],
        'parsed': 1, 'stored': 1})
    data = server._read_recent_pointer_file()
    assert data['scanner_intakes']['Freezer Scanner']['expense_ids'] == [22]
    assert data['scanner_intakes']['Window Scanner']['expense_ids'] == [11]
    # The shared record IS the freezer's scan, so it folds too.
    assert data['intake']['expense_ids'] == [22]


def test_duplicate_callback_amount_mismatch_does_not_show_old_receipt(
        tmp_path, monkeypatch):
    _recent_report_env(tmp_path, monkeypatch, docs=())
    server.record_recent_intake(
        '/staged/scan_freezer_current.jpg', 'Freezer Scanner',
        conversation_id='conv-freezer-current', dispatched_at=100.0)
    monkeypatch.setattr(server, '_duplicate_event_rows', lambda _ids: [{
        'id': 1567, 'expense_date': '2025-03-11', 'amount': '22.89',
    }])

    assert server.merge_recent_intake_event({
        'document_path': '/staged/scan_freezer_current.jpg',
        'conversation_id': 'conv-freezer-current',
        'dispatched_at': 100.0,
        'expense_date': '2025-03-11',
        'amount': '25.56',
        'parsed': 1,
        'stored': 0,
        'duplicate_expense_ids': [1567],
    }) is True

    intake = server.get_scanner_intake('freezer')
    assert intake['expense_ids'] == []
    assert intake['duplicate_expense_ids'] == []
    assert intake['status'] == 'fail'
    assert 'current parse is 2025-03-11 $25.56' in intake['integrity_error']
    assert 'expense 1567 is 2025-03-11 $22.89' in intake['integrity_error']

    # A late false-PASS Trainer verdict cannot put the mismatched row back.
    assert server.record_intake_status({
        'status': 'PASS',
        'conversation_id': 'conv-freezer-current',
        'document_path': '/staged/scan_freezer_current.jpg',
        'dispatched_at': 100.0,
    })['ok'] is True
    assert server.get_scanner_intake('freezer')['status'] == 'fail'


def test_merge_identified_late_event_cannot_clobber_reused_scanner_path(
        tmp_path, monkeypatch):
    _recent_report_env(tmp_path, monkeypatch, docs=())
    path = '/staged/scan_freezer.jpg'
    server.record_recent_intake(
        path, 'Freezer Scanner', conversation_id='conv-new', dispatched_at=200)
    assert server.merge_recent_intake_event({
        'document_path': path, 'conversation_id': 'conv-old',
        'dispatched_at': 100, 'expense_ids': [1514], 'stored': 1,
    }) is False
    intake = server._read_recent_pointer_file()['scanner_intakes']['Freezer Scanner']
    assert intake['conversation_id'] == 'conv-new'
    assert intake['expense_ids'] == []


def test_record_stored_expense_preserves_identity_for_late_callback_routing(
        tmp_path, monkeypatch):
    """The event-bus adapter must not discard the identifiers that make the
    reused scanner path safe.  This was the direct cause of an older Freezer
    callback being folded into the next Freezer report."""
    _recent_report_env(tmp_path, monkeypatch, docs=())
    _clear_expense_events()
    path = '/staged/scan_freezer.jpg'
    server.record_recent_intake(
        path, 'Freezer Scanner', conversation_id='conv-new', dispatched_at=200)

    server.record_stored_expense({
        'document_path': path,
        'conversation_id': 'conv-old',
        'dispatched_at': 100,
        'expense_ids': [1518],
        'stored': 1,
    })

    intake = server._read_recent_pointer_file()['scanner_intakes']['Freezer Scanner']
    assert intake['conversation_id'] == 'conv-new'
    assert intake['expense_ids'] == []
    event = server.get_stored_expense_events(0)[-1]
    assert event['conversation_id'] == 'conv-old'
    assert event['dispatched_at'] == 100
    _clear_expense_events()


def test_merge_identified_event_routes_by_conversation_and_dispatch(
        tmp_path, monkeypatch):
    _recent_report_env(tmp_path, monkeypatch, docs=())
    path = '/staged/scan_freezer.jpg'
    server.record_recent_intake(
        path, 'Freezer Scanner', conversation_id='conv-current', dispatched_at=200)
    assert server.merge_recent_intake_event({
        'document_path': path, 'conversation_id': 'conv-current',
        'dispatched_at': 200, 'expense_ids': [1507], 'stored': 1,
    }) is True
    intake = server._read_recent_pointer_file()['scanner_intakes']['Freezer Scanner']
    assert intake['expense_ids'] == [1507]


def test_merge_dispatch_only_event_does_not_cross_concurrent_scanners(
        tmp_path, monkeypatch):
    """Window and Freezer dispatched inside the 2s window; a STEP 8 callback
    that carries dispatched_at but no conversation_id (older message template)
    must land only on the scanner whose document it names — otherwise Last
    Window Scan shows the Freezer's transactions."""
    _recent_report_env(tmp_path, monkeypatch, docs=())
    server.record_recent_intake(
        '/staged/window_scan.jpg', 'Window Scanner',
        conversation_id='conv-window', dispatched_at=100.0)
    server.record_recent_intake(
        '/staged/scan_freezer.jpg', 'Freezer Scanner',
        conversation_id='conv-freezer', dispatched_at=101.0)

    assert server.merge_recent_intake_event({
        'document_path': '/staged/scan_freezer.jpg',
        'dispatched_at': 101.0,
        'expense_ids': [4242], 'parsed': 1, 'stored': 1,
    }) is True

    assert server.get_scanner_intake('freezer')['expense_ids'] == [4242]
    assert server.get_scanner_intake('window')['expense_ids'] == []


def test_merge_dispatch_only_event_keeps_mirror_when_path_is_unrecognized(
        tmp_path, monkeypatch):
    """The document path is a tie-breaker, never a filter. A callback naming a
    renamed/archived copy still updates the dispatch it was correlated to."""
    _recent_report_env(tmp_path, monkeypatch, docs=())
    server.record_recent_intake(
        '/staged/scan_freezer.jpg', 'Freezer Scanner',
        conversation_id='conv-freezer', dispatched_at=300.0)

    assert server.merge_recent_intake_event({
        'document_path': '/archive/2025/03/consumers_energy_03_11_25.jpg',
        'conversation_id': 'conv-freezer',
        'dispatched_at': 300.0,
        'expense_ids': [4243], 'parsed': 1, 'stored': 1,
    }) is True

    assert server.get_scanner_intake('freezer')['expense_ids'] == [4243]
    data = server._read_recent_pointer_file()
    assert data['intake']['expense_ids'] == [4243]


def test_merge_without_document_path_updates_intake_and_its_mirror(
        tmp_path, monkeypatch):
    _recent_report_env(tmp_path, monkeypatch, docs=())
    server.record_recent_intake('/staged/window_scan.jpg', 'Window Scanner')
    server.merge_recent_intake_event({'expense_ids': [7], 'parsed': 1, 'stored': 1})
    data = server._read_recent_pointer_file()
    assert data['intake']['expense_ids'] == [7]
    assert data['scanner_intakes']['Window Scanner']['expense_ids'] == [7]


def test_get_scanner_intake_reads_per_scanner_then_legacy(tmp_path, monkeypatch):
    _recent_report_env(tmp_path, monkeypatch, docs=())
    _scanner_registry(monkeypatch)
    assert server.get_scanner_intake('window') is None
    server.record_recent_intake('/staged/window_scan.jpg', 'Window Scanner')
    server.record_recent_intake('/staged/scan_freezer.jpg', 'Freezer Scanner')
    assert server.get_scanner_intake('window')['image_path'] == '/staged/window_scan.jpg'
    assert (server.get_scanner_intake('freezer')['image_path']
            == '/staged/scan_freezer.jpg')
    assert server.get_scanner_intake('nope') is None
    # Legacy pointer file (pre-per-scanner records): fall back to the shared
    # intake when it belongs to this scanner.
    server._write_recent_pointer_file({'intake': {
        'document': 'window_scan.jpg', 'image_path': '/staged/window_scan.jpg',
        'label': 'Window Scanner', 'kind': 'scan', 'dispatched_at': 1.0,
    }})
    assert server.get_scanner_intake('window')['image_path'] == '/staged/window_scan.jpg'
    assert server.get_scanner_intake('freezer') is None


def test_build_scanner_report_html_placeholder_and_content(tmp_path, monkeypatch):
    _recent_report_env(tmp_path, monkeypatch, docs=())
    _scanner_registry(monkeypatch)
    monkeypatch.setattr(server, '_receipt_only_picker_assets',
                        lambda: ('', '<div id="rol-category-picker"></div>', ''))
    monkeypatch.setattr(server, '_intake_source_document',
                        lambda intake: intake.get('image_path', ''))
    monkeypatch.setattr(server, '_intake_source_document',
                        lambda intake: intake.get('image_path', ''))
    monkeypatch.setattr(server, '_intake_source_document',
                        lambda intake: intake.get('image_path', ''))
    assert 'Unknown scanner' in server.build_scanner_report_html('nope')
    html = server.build_scanner_report_html('window')
    assert 'No document has been scanned on the Window Scanner yet' in html
    server.record_recent_intake('/staged/window_scan.jpg', 'Window Scanner')
    server.merge_recent_intake_event({
        'document_path': '/staged/window_scan.jpg', 'expense_ids': [7],
        'parsed': 1, 'stored': 1})
    monkeypatch.setattr(server, '_fetch_expenses_by_ids', lambda ids: [{
        'id': 7, 'date': '2025-06-01', 'amount': '-12.34', 'vendor_key': 'kum_go',
        'description': 'Kum & Go', 'reporting_category': 'Travel & Vehicle',
        'cat_class': 'cat-travel-and-vehicle', 'receipt_url': '',
    }])
    html = server.build_scanner_report_html('window')
    assert '/staged/' not in _reader_visible_html(html)
    assert 'verified-transactions' in html
    assert 'data-vendor-key="kum_go"' in html
    assert 'class="cat-travel-and-vehicle has-receipt"' in html
    assert 'data-source-document="/api/intake-document?scanner=window"' in html
    # The freezer tab still shows its own placeholder — window's scan is not its.
    assert ('No document has been scanned on the Freezer Scanner yet'
            in server.build_scanner_report_html('freezer'))


def test_scanner_statement_report_uses_duplicate_ids_when_expense_ids_empty(
        tmp_path, monkeypatch):
    _recent_report_env(tmp_path, monkeypatch, docs=('choice_7580_year',))
    _scanner_registry(monkeypatch)
    report_file = (tmp_path / 'reports' / 'january' / 'choice_7580_year'
                   / 'report.html')
    report_file.write_text(
        '<html><head><title>choice</title></head><body>'
        '<table id="verified-transactions"><tbody>'
        '<tr data-expense-id="1674" data-vendor-key="country_inn">'
        '<td>COUNTRY INN</td><td>-179.08</td><td>2025-08-15</td></tr>'
        '</tbody></table></body></html>')
    server.record_recent_intake('/staged/scan_freezer.jpg', 'Freezer Scanner')
    server.merge_recent_intake_event({
        'document_path': '/staged/scan_freezer.jpg',
        'expense_ids': [],
        'duplicate_expense_ids': [1674],
        'parsed': 4,
        'stored': 0,
        'doc_kind': 'statement',
        'vendor': 'Choice Privileges Mastercard',
    })

    html = server.build_scanner_report_html('freezer')

    assert '<base href="/rol_finances_reports/jan-2025/choice_7580_year/">' in html
    assert 'COUNTRY INN' in html


def test_scanner_statement_report_prefers_canonical_archived_report(
        tmp_path, monkeypatch):
    _recent_report_env(tmp_path, monkeypatch, docs=('choice_7580_year',))
    _scanner_registry(monkeypatch)
    report_url = '/rol_finances_reports/jan-2025/choice_7580_year/report.html'
    report_file = (tmp_path / 'reports' / 'january' / 'choice_7580_year'
                   / 'report.html')
    report_file.write_text(
        '<html><head><title>choice</title></head><body>'
        '<table id="verified-transactions"><tbody>'
        '<tr data-expense-id="1366" data-vendor-key="kfc">'
        '<td>KFC</td><td>-6.24</td><td>2025-07-31</td></tr>'
        '<tr data-expense-id="1390" data-vendor-key="mr_burger">'
        '<td>MR BURGER</td><td>-16.99</td><td>2025-08-15</td></tr>'
        '<tr data-expense-id="1674" data-vendor-key="country_inn">'
        '<td>COUNTRY INN</td><td>-179.08</td><td>2025-08-15</td></tr>'
        '</tbody></table></body></html>')
    server.record_recent_intake('/staged/scan_freezer.jpg', 'Freezer Scanner')
    server.merge_recent_intake_event({
        'document_path': '/staged/scan_freezer.jpg',
        'expense_ids': [1366, 1390],
        'duplicate_expense_ids': [1366, 1390],
        'parsed': 4,
        'stored': 0,
        'doc_kind': 'statement',
        'vendor': 'Choice Privileges Mastercard',
    })

    html = server.build_scanner_report_html('freezer')

    assert '<base href="/rol_finances_reports/jan-2025/choice_7580_year/">' in html
    assert 'COUNTRY INN' in html
    assert 'data-expense-id="1674"' in html
    assert 'Most Recent Document:' not in html


def test_scanner_statement_report_falls_back_to_synthetic_when_no_archive_match(
        tmp_path, monkeypatch):
    _recent_report_env(tmp_path, monkeypatch, docs=())
    _scanner_registry(monkeypatch)
    monkeypatch.setattr(server, '_receipt_only_picker_assets',
                        lambda: ('', '<div id="rol-category-picker"></div>', ''))
    server.record_recent_intake('/staged/scan_freezer.jpg', 'Freezer Scanner')
    server.merge_recent_intake_event({
        'document_path': '/staged/scan_freezer.jpg',
        'expense_ids': [1366, 1390],
        'duplicate_expense_ids': [1366, 1390],
        'parsed': 4,
        'stored': 0,
        'doc_kind': 'statement',
        'vendor': 'Choice Privileges Mastercard',
    })
    monkeypatch.setattr(server, '_fetch_expenses_by_ids', lambda ids: [{
        'id': 1366, 'date': '2025-07-31', 'amount': '6.24',
        'vendor_key': 'kfc_07_31_25_6_24',
        'description': 'KFC K980120 GRAND RAPIDS ,MI',
        'reporting_category': 'Personal / Non-Church — Review Required',
        'cat_class': 'cat-personal', 'receipt_url': '',
    }])

    html = server.build_scanner_report_html('freezer')

    assert 'KFC K980120 GRAND RAPIDS ,MI' in html


def test_scanner_report_stalled_scan_still_reads_clearly(tmp_path, monkeypatch):
    """A stalled scan (the Last Freezer/Window Scan pages' worst case) must
    still name its document, flag the failure loudly, and explain the empty
    Verified Transactions table instead of rendering a wall of '--'."""
    _recent_report_env(tmp_path, monkeypatch, docs=())
    server.record_recent_intake(
        '/incoming_scans/scan_freezer_1786536321_7340d041.jpg',
        'Freezer Scanner')
    server.merge_recent_intake_event({
        'expense_ids': [], 'parsed': None, 'stored': None,
        'doc_kind': 'unknown', 'vendor': 'unknown', 'status': 'stalled',
        'status_detail': 'Verification lock cleared manually.',
    })
    monkeypatch.setattr(server, '_fetch_expenses_by_ids', lambda ids: [])
    monkeypatch.setattr(server, '_receipt_only_picker_assets',
                        lambda: ('', '', ''))

    html = server.build_scanner_report_html('freezer')

    # Never replaced by an "unavailable" sentence, and the staging directory
    # stays private.
    assert 'unavailable' not in html
    assert '/incoming_scans/' not in html
    # No dash-filled metadata rows.
    assert 'Month Range' not in html
    assert 'Associated PDF' not in html
    # The failure is a banner, and the empty table says why it is empty.
    assert 'class="status-banner status-bad"' in html
    assert 'Mazda Trainer reported STALLED' in html
    assert 'stopped before any transactions were stored' in html


def test_scanner_report_path_resolves_as_synthetic_db_backed_page():
    assert server._resolve_report_path_alias('/scanner_report.html') == ''
    # The picker now posts location.search as well, so the alias must match on
    # the path alone — otherwise recategorize would treat the querystring page
    # as a real report.html on disk and fail to find it.
    assert server._resolve_report_path_alias(
        '/scanner_report.html?scanner=freezer') == ''
    assert server._resolve_report_path_alias(
        server.RECEIPT_ONLY_REPORT_PATH + '?month=january'
    ) == server.RECEIPT_ONLY_REPORT_PATH


def test_scanner_intake_document_path_prefers_recorded_scan(tmp_path, monkeypatch):
    staging = tmp_path / 'incoming_scans'
    staging.mkdir()
    recorded = staging / 'scan_unique.jpg'
    recorded.write_bytes(b'jpeg')
    monkeypatch.setattr(server, 'SCAN_STAGING_REMOTE_DIR', str(staging))
    monkeypatch.setattr(server, 'SCAN_TOOLS_DIR', str(tmp_path / 'scanner_tools'))
    _scanner_registry(monkeypatch)
    monkeypatch.setattr(server, 'get_scanner_intake', lambda key: {
        'image_path': str(recorded),
    })
    assert server.scanner_intake_document_path('window') == str(recorded)
    assert server.scanner_intake_document_path('nope') == ''


def test_document_type_label():
    assert server._document_type_label('statement', 'chase') == 'Chase Bank Statement'
    assert server._document_type_label('receipt', 'kum_go') == 'Kum Go Receipt'


def test_known_statement_dispatch_is_statement_only():
    message = server.build_mazda_scan_message(
        '/staged/scan_freezer.jpg', 'Freezer Scanner',
        {'ok': True, 'doc_kind': 'statement', 'routing_key': 'statement.vision',
         'vendor': 'Chase', 'confidence': 1.0, 'recommended_action': 'auto'},
        conversation_id='conv-statement', dispatched_at=123.5)
    assert 'parse_statement_scan.py' in message
    assert 'store_statement_transactions.py' in message
    assert 'conversation_id="conv-statement"' in message
    assert 'dispatched_at=123.5' in message
    assert 'parse_and_categorize.py' not in message
    assert 'check_vendor_key' not in message
    assert server._document_type_label('unknown', None) == 'Not yet identified'
    assert server._document_type_label(None, 'chase') == 'Chase'


def test_format_month_range():
    rows = [{'date': '2025-06-23'}, {'date': '2025-05-30'}]
    assert server._format_month_range(rows) == 'May 30, 2025 >>---> June 23, 2025'
    assert server._format_month_range([{'date': '2025-06-01'}]) == 'June 1, 2025'
    assert server._format_month_range([]) == '--'


def test_associated_source_paths_finds_pdf_and_receipt(monkeypatch):
    monkeypatch.setattr(server, '_find_matching_report_row', lambda d, a, v: (
        ReportRowMatch(report_path='/rol_finances_reports/jan-2025/doc_a/report.html',
                       label='Doc A', row_vendor_key='kum_go')
        if d == '2025-06-01' else None))
    monkeypatch.setattr(server, '_source_document_path',
                        lambda rp: '/home/adamsl/rol_finances/readable_documents/'
                                    'bank_statements/january/doc_a/doc_a.pdf')
    monkeypatch.setattr(server, '_resolve_expense_receipt_path',
                        lambda d, a, ru: '/receipts/kum_go_06_01_25_12_34.jpg' if ru else None)
    rows = [{'date': '2025-06-01', 'amount': '12.34', 'vendor_key': 'kum_go',
             'receipt_url': 'kum_go_06_01_25_12_34.jpg'}]
    pdf_path, receipt_path = server._associated_source_paths(rows)
    assert pdf_path.endswith('doc_a.pdf')
    assert receipt_path.endswith('.jpg')


def test_associated_source_paths_none_found(monkeypatch):
    monkeypatch.setattr(server, '_find_matching_report_row', lambda d, a, v: None)
    rows = [{'date': '2025-06-01', 'amount': '12.34', 'vendor_key': 'kum_go', 'receipt_url': ''}]
    pdf_path, receipt_path = server._associated_source_paths(rows)
    assert pdf_path == '' and receipt_path == ''


def test_recent_intake_collapses_check_evidence_row_into_real_expense(tmp_path, monkeypatch):
    _recent_report_env(tmp_path, monkeypatch, docs=())
    server.record_recent_intake('/staged/freezer_scan.jpg', 'Freezer Scanner')
    server.merge_recent_intake_event({
        'expense_ids': [101, 102],
        'duplicate_expense_ids': [102],
        'parsed': 1,
        'stored': 0,
        'doc_kind': 'receipt',
        'vendor': 'Tikun International',
    })
    monkeypatch.setattr(server, '_fetch_expenses_by_ids', lambda ids: [
        {
            'id': 101,
            'date': '2025-03-18',
            'amount': '300.00',
            'vendor_key': 'tikun_international_03_18_25_300_00',
            'description': 'Tikun International',
            'reporting_category': 'Gifts & Love Offerings',
            'cat_class': 'cat-gifts-and-love-offerings',
            'receipt_url': '/receipts/tikun_03_18_25_300_00.jpg',
            'document_url': '',
            'scanned_statement_url': '',
            'moms_ledger': '',
        },
        {
            'id': 102,
            'date': '2025-03-18',
            'amount': '300.00',
            'vendor_key': 'check_11049_03_18_25_300_00',
            'description': 'Check 11049',
            'reporting_category': 'Gifts & Love Offerings',
            'cat_class': 'cat-gifts-and-love-offerings',
            'receipt_url': '',
            'document_url': '/docs/tikun-check.pdf',
            'scanned_statement_url': '',
            'moms_ledger': '',
        },
    ])
    monkeypatch.setattr(server, '_receipt_only_picker_assets',
                        lambda: ('', '<div id="rol-category-picker"></div>', ''))
    monkeypatch.setattr(server, '_associated_source_paths',
                        lambda rows: ('/docs/tikun-check.pdf', '/receipts/tikun_03_18_25_300_00.jpg'))
    monkeypatch.setattr(server, '_associated_evidence_paths', lambda rows: ('', ''))

    html = server.build_recent_report_html()

    assert html.count('data-expense-id="101"') == 1
    assert 'data-expense-id="102"' not in html
    assert 'data-description="Tikun International"' in html
    assert '<td>Tikun International' in html
    assert 'data-description="Check 11049"' not in html
    assert '<td>Check 11049' not in html


def test_recent_intake_html_omits_document_metadata(tmp_path, monkeypatch):
    """The Most Recent Document headline and Document Type / Month Range /
    Associated PDF / Associated Receipt block were removed from the top of
    the dialog by request -- this guards against them silently coming back."""
    _recent_report_env(tmp_path, monkeypatch, docs=())
    server.record_recent_intake('/staged/scan_freezer.jpg', 'Freezer Scanner')
    server.merge_recent_intake_event({
        'expense_ids': [], 'duplicate_expense_ids': [7], 'parsed': 10, 'stored': 0,
        'doc_kind': 'statement', 'vendor': 'chase',
    })
    monkeypatch.setattr(server, '_fetch_expenses_by_ids', lambda ids: [
        {'date': '2025-05-30', 'amount': '-12.34', 'vendor_key': 'kum_go',
         'description': 'Kum & Go', 'reporting_category': 'Travel & Vehicle',
         'cat_class': 'cat-travel-and-vehicle', 'receipt_url': ''},
        {'date': '2025-06-23', 'amount': '-9.00', 'vendor_key': 'amazon_com',
         'description': 'AMAZON.COM', 'reporting_category': 'Uncategorized',
         'cat_class': 'cat-uncategorized', 'receipt_url': ''},
    ])
    monkeypatch.setattr(server, '_find_matching_report_row', lambda d, a, v: None)
    monkeypatch.setattr(server, '_receipt_only_picker_assets',
                        lambda: ('', '<div id="rol-category-picker"></div>', ''))
    html = server.build_recent_report_html()
    assert 'Most Recent Document' not in html
    assert 'Document Type' not in html
    assert 'Month Range' not in html
    assert 'Associated PDF' not in html
    assert 'Associated Receipt' not in html
    assert 'Archived Scan Image' not in html


def test_statement_archive_path_finds_canonically_named_copy(tmp_path, monkeypatch):
    """A scanned statement's canonically-named bank_statements/ archive copy
    (bank_statements/<year>/<month>/<vendor>_<slug>/<vendor>_<slug>.jpg) is
    findable from the statement's own date range even though scanned_statement_url
    never points at it — a duplicate rescan's DB rows still only carry the raw
    scan filename from whichever run first stored them."""
    base = tmp_path / 'readable_documents'
    folder = (base / 'bank_statements' / '2025' / 'july'
              / 'choice_privileges_mastercard_7580_july_31__august_15')
    folder.mkdir(parents=True)
    (folder / 'choice_privileges_mastercard_7580_july_31__august_15.jpg').write_bytes(b'x')
    monkeypatch.setattr(server, 'READABLE_DOCS_BASE', str(base))
    rows = [
        {'date': '2025-07-31', 'amount': '6.24', 'vendor_key': 'choice_privileges_7580'},
        {'date': '2025-08-15', 'amount': '16.99', 'vendor_key': 'choice_privileges_7580'},
        {'date': '2025-08-15', 'amount': '179.08', 'vendor_key': 'choice_privileges_7580'},
    ]
    found = server._statement_archive_path(rows, vendor_key='choice_privileges_7580')
    assert found == str(
        folder / 'choice_privileges_mastercard_7580_july_31__august_15.jpg')


def test_statement_archive_path_no_match_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(server, 'READABLE_DOCS_BASE', str(tmp_path / 'readable_documents'))
    rows = [{'date': '2025-07-31', 'amount': '6.24', 'vendor_key': 'choice_privileges_7580'}]
    assert server._statement_archive_path(rows) == ''
    assert server._statement_archive_path([]) == ''


def test_recent_intake_prefers_statement_archive_over_raw_scan_url(
        tmp_path, monkeypatch):
    """An intake resolves to the canonically-named bank_statements/ archive
    copy, not the stale raw scan filename recorded in scanned_statement_url --
    and the page never prints that raw filename.

    The rest of that metadata block was removed from the dialog by request
    (see test_recent_intake_html_omits_document_metadata); this one line stayed
    because it is the filing evidence checked before paper goes to the attic."""
    _recent_report_env(tmp_path, monkeypatch, docs=())
    base = tmp_path / 'readable_documents'
    folder = (base / 'bank_statements' / '2025' / 'july'
              / 'choice_privileges_mastercard_7580_july_31__august_15')
    folder.mkdir(parents=True)
    archive_file = folder / 'choice_privileges_mastercard_7580_july_31__august_15.jpg'
    archive_file.write_bytes(b'x')
    monkeypatch.setattr(server, 'READABLE_DOCS_BASE', str(base))
    monkeypatch.setattr(server, '_supporting_document_roots', lambda: [str(base)])
    server.record_recent_intake('/staged/scan_freezer.jpg', 'Freezer Scanner')
    server.merge_recent_intake_event({
        'expense_ids': [], 'duplicate_expense_ids': [1, 2, 3], 'parsed': 5, 'stored': 0,
    })
    raw_scan = base / 'scanned_statements' / '2025' / 'window_scan_raw.jpg'
    raw_scan.parent.mkdir(parents=True)
    raw_scan.write_bytes(b'x')
    monkeypatch.setattr(server, '_fetch_expenses_by_ids', lambda ids: [
        {'date': '2025-07-31', 'amount': '6.24', 'vendor_key': 'choice_privileges_7580',
         'description': 'KFC', 'reporting_category': 'Uncategorized',
         'cat_class': 'cat-uncategorized', 'receipt_url': '',
         'scanned_statement_url': str(raw_scan)},
        {'date': '2025-08-15', 'amount': '16.99', 'vendor_key': 'choice_privileges_7580',
         'description': 'MR BURGER', 'reporting_category': 'Uncategorized',
         'cat_class': 'cat-uncategorized', 'receipt_url': '',
         'scanned_statement_url': str(raw_scan)},
        {'date': '2025-08-15', 'amount': '179.08', 'vendor_key': 'choice_privileges_7580',
         'description': 'COUNTRY INN', 'reporting_category': 'Uncategorized',
         'cat_class': 'cat-uncategorized', 'receipt_url': '',
         'scanned_statement_url': str(raw_scan)},
    ])
    monkeypatch.setattr(server, '_find_matching_report_row', lambda *a, **k: None)
    monkeypatch.setattr(server, '_receipt_only_picker_assets',
                        lambda: ('', '<div id="rol-category-picker"></div>', ''))
    intake = server._read_recent_pointer_file()['intake']
    rows = server._fetch_expenses_by_ids([])
    # doc_kind was never recorded (a duplicates-only intake records none), so
    # the rows themselves have to identify the document.
    assert not intake.get('doc_kind')
    assert server._recent_intake_archive_path(intake, rows) == str(archive_file)

    html = server.build_recent_report_html()
    # The archive copy is the one scan-image path the page prints; the stale
    # raw scanned_statement_url must not appear anywhere.
    assert f'Archived Scan Image: {archive_file}' in html
    assert str(raw_scan) not in html


def test_recent_intake_html_shows_archived_scan_copy_from_callback(tmp_path, monkeypatch):
    base = _recent_report_env(tmp_path, monkeypatch, docs=())
    archived = ('/home/adamsl/rol_finances/readable_documents/bank_statements/'
                '2025/march/chase_6285_march_18__march_18/'
                'chase_6285_march_18__march_18.jpg')
    # The staged path must exist: _intake_source_document deliberately drops a
    # staged path it cannot resolve, so that "View Source Document" can never
    # offer an image that is gone.
    staged = tmp_path / 'incoming_scans' / 'window_scan.jpg'
    staged.parent.mkdir(parents=True, exist_ok=True)
    write_scan_image(staged)
    monkeypatch.setattr(server, '_supporting_document_roots',
                        lambda: [str(tmp_path), str(base)])
    server.record_recent_intake(str(staged), 'Window Scanner')
    server.merge_recent_intake_event({
        'expense_ids': [7], 'parsed': 1, 'stored': 1,
        'doc_kind': 'statement', 'vendor': 'chase',
        'archive_paths': [archived],
        'archive_years': [2025],
    })
    monkeypatch.setattr(server, '_fetch_expenses_by_ids', lambda ids: [{
        'date': '2025-03-18', 'amount': '-30.50', 'vendor_key': 'check_11051',
        'description': 'Check 11051', 'reporting_category': 'Gifts & Love Offerings',
        'cat_class': 'cat-gifts-and-love-offerings', 'receipt_url': '',
        'document_url': '', 'scanned_statement_url': '', 'moms_ledger': '',
    }])
    monkeypatch.setattr(server, '_receipt_only_picker_assets',
                        lambda: ('', '<div id="rol-category-picker"></div>', ''))
    html = server.build_recent_report_html()
    assert 'Staged Scan Image' not in html
    assert str(staged) not in _reader_visible_html(html)


def test_recent_receipt_uses_canonical_archive_name_and_not_statement_slot(
        tmp_path, monkeypatch):
    _recent_report_env(tmp_path, monkeypatch, docs=())
    archived = (
        '/home/adamsl/rol_finances/readable_documents/receipts/2025/march/'
        'march_18/intercessors_for_america_03_18_25_30_50.jpg')
    server.record_recent_intake('/staged/window_scan.jpg', 'Window Scanner')
    server.merge_recent_intake_event({
        'expense_ids': [], 'duplicate_expense_ids': [1547],
        'parsed': 1, 'stored': 0, 'doc_kind': 'receipt',
        'vendor': 'Intercessors for America',
        'archive_paths': [archived], 'archive_years': [2025],
    })
    monkeypatch.setattr(server, '_fetch_expenses_by_ids', lambda ids: [{
        'id': 1547, 'date': '2025-03-18', 'amount': '30.50',
        'vendor_key': 'check_11051_03_18_25_30_50',
        'description': 'Check 11051',
        'reporting_category': 'Gifts & Love Offerings',
        'cat_class': 'cat-gifts-and-love-offerings',
        'receipt_url': archived, 'document_url': '/docs/statement.pdf',
        'scanned_statement_url': '', 'moms_ledger': '',
    }])
    monkeypatch.setattr(
        server, '_associated_source_paths', lambda rows: ('', archived))
    monkeypatch.setattr(
        server, '_intake_source_document',
        lambda intake: '/staged/window_scan.jpg')
    monkeypatch.setattr(server, '_receipt_only_picker_assets',
                        lambda: ('', '<div id="rol-category-picker"></div>', ''))

    html = server.build_recent_report_html()

    assert 'Staged Scan Image' not in html
    assert '/staged/window_scan.jpg' not in _reader_visible_html(html)


def test_scanner_report_hides_staged_image_when_archive_is_missing(
        tmp_path, monkeypatch):
    """A scanner report must not advertise its temporary processing image."""
    _recent_report_env(tmp_path, monkeypatch, docs=())
    _scanner_registry(monkeypatch)
    server.record_recent_intake('/staged/scan_freezer.jpg', 'Freezer Scanner')
    server.merge_recent_intake_event({
        'expense_ids': [], 'parsed': 0, 'stored': 0, 'doc_kind': 'statement',
    })
    monkeypatch.setattr(server, '_fetch_expenses_by_ids', lambda ids: [])
    monkeypatch.setattr(server, '_receipt_only_picker_assets',
                        lambda: ('', '<div id="rol-category-picker"></div>', ''))

    html = server.build_scanner_report_html('freezer')

    assert 'Archived Scan Image' not in html
    assert 'Staged Scan Image:' not in html
    assert '/staged/scan_freezer.jpg' not in _reader_visible_html(html)


def test_report_pointer_newer_than_intake_wins(tmp_path, monkeypatch):
    """Reprocess sets the report pointer AFTER the intake record — report mode
    must win so a reprocessed document shows its real report.html."""
    _recent_report_env(tmp_path, monkeypatch)
    server.record_recent_intake('/pdf/statement.pdf', 'PDF intake', kind='pdf')
    url = '/rol_finances_reports/jan-2025/doc_a/report.html'
    server.set_recent_report_pointer(url)
    resolved = server.resolve_recent_report()
    assert resolved['mode'] == 'report'
    assert resolved['url'] == url


def test_alias_returns_empty_in_intake_mode(tmp_path, monkeypatch):
    """In intake mode the picker's location.pathname must translate to '' so
    recategorize takes the search-all-reports / DB-only path."""
    _recent_report_env(tmp_path, monkeypatch, docs=())
    server.record_recent_intake('/staged/window_scan.jpg', 'Window Scanner')
    assert server._resolve_report_path_alias('/recent_report.html') == ''


def test_merge_recent_intake_event_includes_duplicate_ids(tmp_path, monkeypatch):
    """A duplicates-only re-scan still lists its rows: duplicate_expense_ids
    from STEP 8 fold into the intake exactly like newly-stored ids."""
    _recent_report_env(tmp_path, monkeypatch, docs=())
    server.record_recent_intake('/staged/scan_freezer.jpg', 'Freezer Scanner')
    server.record_stored_expense({
        'kind': 'statement', 'expense_ids': [],
        'duplicate_expense_ids': [1490, 1491, 1492],
        'parsed': 10, 'stored': 0,
    })
    intake = server._read_recent_pointer_file()['intake']
    assert intake['expense_ids'] == [1490, 1491, 1492]


def test_duplicate_only_event_without_ids_recovers_row_from_db(tmp_path, monkeypatch):
    """A receipt/invoice duplicate callback that names no ids at all still
    yields a listable row: the (date, amount) it matched on resolves the
    pre-existing expense, so Verified Transactions renders instead of the bare
    "already in the database" sentence."""
    _recent_report_env(tmp_path, monkeypatch, docs=())
    monkeypatch.setattr(
        server, '_rol_get_connection', lambda: _FakeConnection([{'id': 1521}]))
    server.record_recent_intake('/staged/scan_freezer.jpg', 'Freezer Scanner')
    server.merge_recent_intake_event({
        'expense_ids': [], 'duplicate_expense_ids': [], 'expense_id': None,
        'parsed': 1, 'stored': 0,
        'expense_date': '2025-01-23', 'amount': '222.65',
        'vendor_key': 'consumers_7996',
    })
    intake = server._read_recent_pointer_file()['intake']
    assert intake['expense_ids'] == [1521]
    assert intake['duplicate_expense_ids'] == [1521]


def test_duplicate_recovery_skips_ambiguous_date_amount(tmp_path, monkeypatch):
    """Too many rows share the (date, amount) pair → show nothing rather than
    rows that may belong to an unrelated document."""
    _recent_report_env(tmp_path, monkeypatch, docs=())
    monkeypatch.setattr(server, '_rol_get_connection', lambda: _FakeConnection(
        [{'id': i} for i in (10, 11, 12, 13)]))
    server.record_recent_intake('/staged/scan_freezer.jpg', 'Freezer Scanner')
    server.merge_recent_intake_event({
        'parsed': 1, 'stored': 0,
        'expense_date': '2025-01-23', 'amount': '20.00'})
    intake = server._read_recent_pointer_file()['intake']
    assert intake['expense_ids'] == []
    assert intake['duplicate_expense_ids'] == []


def test_duplicate_recovery_needs_date_and_amount(monkeypatch):
    """No date/amount to match on → no DB query, no guess."""
    def _boom():
        raise AssertionError('must not query without a date/amount')
    monkeypatch.setattr(server, '_rol_get_connection', _boom)
    assert server._resolve_duplicate_expense_ids('', '222.65') == []
    assert server._resolve_duplicate_expense_ids('2025-01-23', '') == []
    assert server._resolve_duplicate_expense_ids('2025-01-23', 'n/a') == []


def test_duplicate_recovery_leaves_reported_ids_alone(tmp_path, monkeypatch):
    """Recovery is a last resort: when STEP 8 did name its duplicates, the DB
    is never consulted and the reported ids stand."""
    def _boom():
        raise AssertionError('must not query when the callback named ids')
    _recent_report_env(tmp_path, monkeypatch, docs=())
    monkeypatch.setattr(server, '_rol_get_connection', _boom)
    server.record_recent_intake('/staged/scan_freezer.jpg', 'Freezer Scanner')
    server.merge_recent_intake_event({
        'duplicate_expense_ids': [1490], 'parsed': 1, 'stored': 0,
        'expense_date': '2025-01-23', 'amount': '222.65'})
    intake = server._read_recent_pointer_file()['intake']
    assert intake['expense_ids'] == [1490]


def test_recent_intake_html_duplicates_run_still_lists_rows(tmp_path, monkeypatch):
    _recent_report_env(tmp_path, monkeypatch, docs=())
    server.record_recent_intake('/staged/scan_freezer.jpg', 'Freezer Scanner')
    server.merge_recent_intake_event({
        'duplicate_expense_ids': [1490], 'parsed': 10, 'stored': 0})
    monkeypatch.setattr(server, '_fetch_expenses_by_ids', lambda ids: [{
        'date': '2025-05-30', 'amount': '26.32', 'id_light': 'amazon_com_05_30_25_26_32',
        'description': 'AMAZON.COM', 'reporting_category': 'Uncategorized',
        'cat_class': 'cat-uncategorized',
    }])
    monkeypatch.setattr(server.manual_entry, 'resolve_vendor_match',
                        lambda _description: {'vendor_key': 'amazon_com'})
    monkeypatch.setattr(server, '_receipt_only_picker_assets',
                        lambda: ('', '<div id="rol-category-picker"></div>', ''))
    html = server.build_recent_report_html()
    assert '<table id="verified-transactions"' in html
    assert 'data-vendor-key="amazon_com"' in html
    assert 'already in the' in html and 'shown below' in html


def test_recent_intake_html_collapses_equivalent_duplicate_ids(tmp_path, monkeypatch):
    _recent_report_env(tmp_path, monkeypatch, docs=())
    server.record_recent_intake('/staged/window_scan.jpg', 'Window Scanner')
    server.merge_recent_intake_event({
        'duplicate_expense_ids': [561, 1519], 'parsed': 1, 'stored': 0})
    monkeypatch.setattr(server, '_fetch_expenses_by_ids', lambda ids: [
        {
            'id': 561, 'date': '2025-02-20', 'amount': '33.13',
            'vendor_key': 'mr_burger', 'description': 'MR BURGER RESTAURANT 1',
            'reporting_category': 'Food & Hospitality',
            'cat_class': 'cat-food-and-hospitality', 'receipt_url': 'canonical.jpg',
        },
        {
            'id': 1519, 'date': '2025-02-20', 'amount': '33.13',
            'vendor_key': 'mr_burger_restaurant', 'description': 'MR BURGER RESTAURANT',
            'reporting_category': 'Food & Hospitality',
            'cat_class': 'cat-food-and-hospitality', 'receipt_url': 'duplicate.png',
        },
    ])
    monkeypatch.setattr(server, '_receipt_only_picker_assets',
                        lambda: ('', '<div id="rol-category-picker"></div>', ''))

    html = server.build_recent_report_html()

    assert html.count('data-expense-id="561"') == 1
    assert 'data-expense-id="1519"' not in html


def test_compute_server_status_hard_failure_stays_red():
    """A health result flagged hard:True (e.g. dead provider OAuth token) must be
    red even when a restart handler exists — a restart click can't fix it alone."""
    from server import compute_server_status
    assert compute_server_status({'ok': False, 'hard': True}, restartable=True) == 'down'
    assert compute_server_status({'ok': False}, restartable=True) == 'concern'
    assert compute_server_status({'ok': True}, restartable=True) == 'up'


# ---------------------------------------------------------------------------
# /api/tts — edge-tts voice synthesis (the pickle_cpp en-GB-SoniaNeural voice)
# ---------------------------------------------------------------------------

def _tts_env(monkeypatch, tmp_path):
    """Point the TTS cache at a tmp dir and fake an existing edge-tts binary."""
    fake_bin = tmp_path / 'edge-tts'
    fake_bin.write_text('#!/bin/sh\n')
    monkeypatch.setattr(server, 'EDGE_TTS_BIN', str(fake_bin))
    monkeypatch.setattr(server, 'TTS_CACHE_DIR', str(tmp_path / 'cache'))
    return fake_bin


def test_synthesize_speech_rejects_empty_and_bad_voice(monkeypatch, tmp_path):
    _tts_env(monkeypatch, tmp_path)
    assert server.synthesize_speech('')['ok'] is False
    assert server.synthesize_speech('   ')['ok'] is False
    bad = server.synthesize_speech('hi', voice='$(rm -rf /)')
    assert bad['ok'] is False and 'invalid voice' in bad['error']


def test_synthesize_speech_runs_edge_tts_and_caches(monkeypatch, tmp_path):
    fake_bin = _tts_env(monkeypatch, tmp_path)
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        # edge-tts writes the media file itself; emulate that.
        out = cmd[cmd.index('--write-media') + 1]
        with open(out, 'wb') as f:
            f.write(b'ID3fakeaudio')
        return types.SimpleNamespace(returncode=0, stdout='', stderr='')

    first = server.synthesize_speech('hello there', runner=fake_run)
    assert first['ok'] is True and first['cached'] is False
    assert calls[0][0] == str(fake_bin)
    assert calls[0][calls[0].index('--voice') + 1] == server.EDGE_TTS_VOICE
    assert open(first['path'], 'rb').read() == b'ID3fakeaudio'

    second = server.synthesize_speech('hello there', runner=fake_run)
    assert second['ok'] is True and second['cached'] is True
    assert len(calls) == 1  # cache hit — no second subprocess


def test_synthesize_speech_reports_edge_tts_failure(monkeypatch, tmp_path):
    _tts_env(monkeypatch, tmp_path)

    def failing_run(cmd, **kwargs):
        return types.SimpleNamespace(returncode=1, stdout='', stderr='boom')

    result = server.synthesize_speech('hello', runner=failing_run)
    assert result['ok'] is False and 'boom' in result['error']


def test_synthesize_speech_missing_binary(monkeypatch, tmp_path):
    monkeypatch.setattr(server, 'EDGE_TTS_BIN', str(tmp_path / 'nope'))
    monkeypatch.setattr(server, 'TTS_CACHE_DIR', str(tmp_path / 'cache'))
    result = server.synthesize_speech('hello')
    assert result['ok'] is False and 'not found' in result['error']


# ── run_statement_preflight vs parse_statement_scan.py's output shape ───────
# 2026-07-22: the parser switched to a multi-statement envelope
# ({'statements': [...]}) while the preflight still read the old top-level
# bank_name/account_number/transactions. Every field came back None, so each
# statement scan was rejected as "no complete transaction" before dispatch and
# the Window Scanner report silently kept showing the previous document.

_STMT_FACADE = {'ok': True, 'doc_kind': 'statement', 'confidence': .99}
_STMT_ROWS = [{'date': '2025-01-04', 'description': 'AMAZON MKTPL', 'amount': -60.0}]


def _stub_statement_parser(monkeypatch, payload):
    def fake_run(command, **kwargs):
        return types.SimpleNamespace(
            returncode=0, stdout=json.dumps(payload), stderr='')

    monkeypatch.setattr(server.subprocess, 'run', fake_run)


def test_statement_preflight_reads_multi_statement_envelope(monkeypatch):
    _stub_statement_parser(monkeypatch, {
        'ok': True, 'doc_kind': 'statement', 'statement_count': 1,
        'statements': [{'bank_name': 'Chase Amazon',
                        'account_number': '1234',
                        'transactions': _STMT_ROWS}],
    })

    result = server.run_statement_preflight('/scan.jpg', _STMT_FACADE)

    assert result['ok'] is True
    assert result['bank_name'] == 'Chase Amazon'
    assert result['account_last4'] == '1234'
    assert result['transaction_count'] == 1


def test_statement_preflight_still_reads_legacy_flat_shape(monkeypatch):
    _stub_statement_parser(monkeypatch, {
        'ok': True, 'doc_kind': 'statement', 'bank_name': 'Wells Fargo',
        'account_number': '7580', 'transactions': _STMT_ROWS,
    })

    result = server.run_statement_preflight('/scan.jpg', _STMT_FACADE)

    assert result['ok'] is True
    assert result['bank_name'] == 'Wells Fargo'
    assert result['account_last4'] == '7580'


def test_statement_preflight_omits_engine_flag_for_auto(monkeypatch):
    """Mazda's own automatic dispatch never passes `engine` -- the constructed
    command must stay textually identical to before the flag existed, since
    'auto' is parse_statement_scan.py's own default."""
    captured = {}

    def fake_run(command, **kwargs):
        captured['command'] = command
        return types.SimpleNamespace(
            returncode=0, stdout=json.dumps({
                'ok': True, 'doc_kind': 'statement', 'statement_count': 1,
                'statements': [{'bank_name': 'Chase', 'account_number': '1234',
                                'transactions': _STMT_ROWS}],
            }), stderr='')

    monkeypatch.setattr(server.subprocess, 'run', fake_run)
    server.run_statement_preflight('/scan.jpg', _STMT_FACADE)
    assert '--engine' not in captured['command']


def test_statement_preflight_passes_the_chosen_engine_flag(monkeypatch):
    """The dashboard's "Read with Haiku"/"Read with Gemini" buttons must reach
    parse_statement_scan.py's own --engine flag exactly, with no fallback."""
    captured = {}

    def fake_run(command, **kwargs):
        captured['command'] = command
        return types.SimpleNamespace(
            returncode=0, stdout=json.dumps({
                'ok': True, 'doc_kind': 'statement', 'statement_count': 1,
                'statements': [{'bank_name': 'Chase', 'account_number': '1234',
                                'transactions': _STMT_ROWS}],
            }), stderr='')

    monkeypatch.setattr(server.subprocess, 'run', fake_run)
    server.run_statement_preflight(
        '/scan.jpg', _STMT_FACADE, engine='haiku-only')
    command = captured['command']
    assert '--engine' in command
    assert command[command.index('--engine') + 1] == 'haiku-only'


def test_statement_preflight_uses_last_four_of_full_printed_account(monkeypatch):
    """Vision may return the complete printed account despite the last4 schema."""
    _stub_statement_parser(monkeypatch, {
        'ok': True,
        'statements': [{
            'bank_name': 'Fifth Third',
            'account_number': '3686285',
            'transactions': _STMT_ROWS,
        }],
    })

    result = server.run_statement_preflight('/scan.jpg', _STMT_FACADE)

    assert result['ok'] is True
    assert result['account_last4'] == '6285'
    assert result['last4_source'] == 'statement'


class _FakeAccountDirectory:
    """Offline stand-in for KnownCardsWorkbook (see known_accounts.py)."""

    def __init__(self, last4=None, ambiguous=()):
        self._last4 = last4
        self._ambiguous = tuple(ambiguous)

    def lookup_last4(self, bank_name):
        return types.SimpleNamespace(
            last4=self._last4, ambiguous_last4=self._ambiguous, matched_names=())


def test_statement_preflight_asks_for_metadata_when_envelope_lacks_last4(
        monkeypatch):
    _stub_statement_parser(monkeypatch, {
        'ok': True, 'statements': [{'bank_name': 'Chase Amazon',
                                    'account_number': None,
                                    'transactions': _STMT_ROWS}],
    })

    # No workbook match: the last four is unknowable, so preflight must still
    # fail closed and ask for metadata rather than guess.
    result = server.run_statement_preflight(
        '/scan.jpg', _STMT_FACADE, account_directory=_FakeAccountDirectory())

    assert result['ok'] is False
    assert result['needs_statement_metadata'] is True
    assert result['missing_fields'] == ['account_last4']
    assert result['bank_name'] == 'Chase Amazon'


def test_statement_preflight_resolves_missing_last4_from_workbook(monkeypatch):
    # The account number isn't on the scanned band, but the bank is a known card
    # in Known_Credit_Cards_and_Banks.xlsx — resolve it and proceed to dispatch
    # instead of stalling (the Chase -> 5783 case that reached EG on 2026-07-23).
    _stub_statement_parser(monkeypatch, {
        'ok': True, 'statements': [{'bank_name': 'Chase',
                                    'account_number': None,
                                    'transactions': _STMT_ROWS}],
    })

    result = server.run_statement_preflight(
        '/scan.jpg', _STMT_FACADE,
        account_directory=_FakeAccountDirectory(last4='5783'))

    assert result['ok'] is True
    assert result['account_last4'] == '5783'
    assert result['last4_source'] == 'known_cards_workbook'
    assert result.get('needs_statement_metadata') is not True


def test_statement_preflight_prefers_unique_letterhead_workbook_match_over_vision_digits(
        monkeypatch):
    """A branded card letterhead is safer than obscured account-number OCR.

    The Choice Privileges scan on 2026-07-27 was visibly branded Choice but
    vision guessed 4884 from marked-over digits.  The workbook has exactly one
    Choice row (7580), so preflight must use that authoritative match rather
    than archive and dispatch the statement under the guessed digits.
    """
    _stub_statement_parser(monkeypatch, {
        'ok': True, 'statements': [{
            'bank_name': 'Wells Fargo',
            'account_number': '4884',
            'transactions': _STMT_ROWS,
        }],
    })

    class ChoiceDirectory:
        def lookup_last4(self, name):
            if name == 'Choice Privileges Mastercard':
                return types.SimpleNamespace(
                    last4='7580', ambiguous_last4=(),
                    matched_names=('choice_7580',))
            return types.SimpleNamespace(
                last4=None, ambiguous_last4=(), matched_names=())

    result = server.run_statement_preflight(
        '/scan.jpg',
        dict(_STMT_FACADE, vendor='Choice Privileges Mastercard'),
        account_directory=ChoiceDirectory())

    assert result['ok'] is True
    assert result['bank_name'] == 'Choice Privileges Mastercard'
    assert result['account_last4'] == '7580'
    assert result['last4_source'] == 'known_cards_workbook'
    assert result['workbook_matched_names'] == ['choice_7580']
    message = server.build_mazda_scan_message(
        '/staged/choice.jpg', 'Window Scanner',
        {
            'ok': True,
            'doc_kind': 'statement',
            'vendor': result['bank_name'],
            'confidence': 1.0,
            'statement_preflight': result,
        })
    assert "--bank-name 'Choice Privileges Mastercard'" in message
    assert '--account-last4 7580' in message
    assert '--account-last4-source known_cards_workbook' in message
    assert '4884' not in message


def test_statement_preflight_fails_closed_on_ambiguous_workbook_match(
        monkeypatch):
    # A bank with several cards on file must NOT be resolved to one of them —
    # surface the ambiguity and keep asking for metadata.
    _stub_statement_parser(monkeypatch, {
        'ok': True, 'statements': [{'bank_name': 'Fifth Third Bank',
                                    'account_number': None,
                                    'transactions': _STMT_ROWS}],
    })

    result = server.run_statement_preflight(
        '/scan.jpg', _STMT_FACADE,
        account_directory=_FakeAccountDirectory(
            ambiguous=('5938', '6285', '3119')))

    assert result['ok'] is False
    assert result['needs_statement_metadata'] is True
    assert result['account_last4'] is None
    assert result['workbook_ambiguous_last4'] == ['5938', '6285', '3119']
    assert '5938' in result['error']


def test_statement_preflight_halts_on_two_statements_in_one_scan(monkeypatch):
    _stub_statement_parser(monkeypatch, {
        'ok': True, 'statement_count': 2,
        'statements': [
            {'bank_name': 'Chase', 'account_number': '1234',
             'transactions': _STMT_ROWS},
            {'bank_name': 'American Express', 'account_number': '5678',
             'transactions': _STMT_ROWS},
        ],
    })

    result = server.run_statement_preflight('/scan.jpg', _STMT_FACADE)

    assert result['ok'] is False and result['rejected'] is True
    assert result['needs_statement_metadata'] is False
    assert 'Chase 1234' in result['error']
    assert 'American Express 5678' in result['error']


def test_statement_preflight_rejects_envelope_with_no_transactions(monkeypatch):
    _stub_statement_parser(monkeypatch, {
        'ok': True, 'statement_count': 1,
        'statements': [{'bank_name': 'Chase', 'account_number': '1234',
                        'transactions': []}],
    })

    result = server.run_statement_preflight('/scan.jpg', _STMT_FACADE)

    assert result['ok'] is False and result['rejected'] is True
    assert 'no complete transaction' in result['error']


# ── Keyboard-free deploy (resilience path) ────────────────────────────────────
# deploy_dashboard() is the "never dead in the water" path: Frita (or EG from a
# phone) triggers a git fast-forward + self-restart over HTTP, no keyboard/SSH.
# The load-bearing guarantee is fail-loud: a bad pull must NOT restart the box.

def _fake_git(monkeypatch, results):
    """Drive server.deploy_dashboard's inner `git -C REPO_ROOT <args>` calls.

    `results` maps a git subcommand (the first arg after -C REPO_ROOT) to a
    (returncode, stdout, stderr) tuple. rev-parse is disambiguated by its flag.
    """
    def run(cmd, capture_output=True, text=True, timeout=None):
        sub = cmd[3]  # ['git', '-C', REPO_ROOT, <sub>, ...]
        if sub == 'rev-parse':
            key = 'branch' if '--abbrev-ref' in cmd else 'sha'
        else:
            key = sub
        rc, out, err = results[key]
        return types.SimpleNamespace(returncode=rc, stdout=out, stderr=err)
    monkeypatch.setattr(server.subprocess, 'run', run)


def test_deploy_dashboard_fast_forwards_then_restarts(monkeypatch):
    shas = iter(['aaaaaaa', 'bbbbbbb'])  # before, after
    monkeypatch.setattr(server.subprocess, 'run', lambda *a, **k: None)
    _fake_git(monkeypatch, {
        'branch': (0, 'main\n', ''),
        'sha': (0, '', ''),   # overridden below
        'fetch': (0, '', ''),
        'pull': (0, 'Updating aaaaaaa..bbbbbbb\n', ''),
    })
    # rev-parse --short returns before then after
    orig = server.subprocess.run
    def run(cmd, **k):
        r = orig(cmd, **k)
        if cmd[3] == 'rev-parse' and '--short' in cmd:
            return types.SimpleNamespace(returncode=0, stdout=next(shas) + '\n', stderr='')
        return r
    monkeypatch.setattr(server.subprocess, 'run', run)

    called = {}
    def fake_restart():
        called['restart'] = True
        return {'ok': True, 'text': 'Restarting…'}
    monkeypatch.setattr(server, 'restart_dashboard_server', fake_restart)

    result = server.deploy_dashboard()
    assert called.get('restart') is True
    assert result['ok'] is True
    assert 'aaaaaaa -> bbbbbbb' in result['text']


def test_deploy_dashboard_fails_loud_and_skips_restart_on_non_ff(monkeypatch):
    _fake_git(monkeypatch, {
        'branch': (0, 'main\n', ''),
        'sha': (0, 'aaaaaaa\n', ''),
        'fetch': (0, '', ''),
        'pull': (1, '', 'fatal: Not possible to fast-forward, aborting.'),
    })
    called = {}
    monkeypatch.setattr(server, 'restart_dashboard_server',
                        lambda: called.setdefault('restart', True))

    result = server.deploy_dashboard()
    assert 'restart' not in called          # a dirty/divergent tree is never activated
    assert result['ok'] is False
    assert 'NOT restarted' in result['text']
    assert 'fast-forward' in result['text']


def test_deploy_dashboard_fails_loud_when_fetch_fails(monkeypatch):
    _fake_git(monkeypatch, {
        'branch': (0, 'main\n', ''),
        'sha': (0, 'aaaaaaa\n', ''),
        'fetch': (1, '', 'fatal: could not read from remote'),
        'pull': (0, '', ''),
    })
    called = {}
    monkeypatch.setattr(server, 'restart_dashboard_server',
                        lambda: called.setdefault('restart', True))

    result = server.deploy_dashboard()
    assert 'restart' not in called
    assert result['ok'] is False
    assert 'git fetch' in result['text'] and 'NOT restarted' in result['text']


# ── provider-health fallback classification ──────────────────────────────────

def _fallback_state(*, cat_last_success=0, vision_last_success=0):
    """provider_health.json shape: one categorizer + one vision fallback at t=100."""
    return {
        'chatgpt-oauth-categorizer:eg': {
            'last_success': cat_last_success, 'last_failure': 99},
        'chatgpt-oauth-vision:eg': {
            'last_success': vision_last_success, 'last_failure': 99},
        'chatgpt-oauth-categorizer:_fallbacks': {
            'events': [{'time': 100, 'from': 'eg', 'to': 'moms', 'error': '429'}]},
        'chatgpt-oauth-vision:_fallbacks': {
            'events': [{'time': 100, 'from': 'eg', 'to': 'moms', 'error': '429'}]},
    }


def test_split_provider_health_state_separates_accounts_from_fallbacks():
    accounts, fallbacks = server.split_provider_health_state(_fallback_state())
    assert set(accounts) == {
        'chatgpt-oauth-categorizer:eg', 'chatgpt-oauth-vision:eg'}
    assert set(fallbacks) == {
        'chatgpt-oauth-categorizer', 'chatgpt-oauth-vision'}
    assert len(fallbacks['chatgpt-oauth-vision']) == 1


def test_unresolved_fallbacks_skips_events_the_account_recovered_from():
    # primary succeeded at t=150, after the t=100 fallback → resolved, no alert
    accounts, fallbacks = server.split_provider_health_state(
        _fallback_state(cat_last_success=150))
    assert server.unresolved_fallbacks(
        accounts, fallbacks, cutoff=0, want_vision=False) == []


def test_unresolved_fallbacks_keeps_events_with_no_later_success():
    accounts, fallbacks = server.split_provider_health_state(
        _fallback_state(cat_last_success=50))
    events = server.unresolved_fallbacks(
        accounts, fallbacks, cutoff=0, want_vision=False)
    assert [p for p, _ in events] == ['chatgpt-oauth-categorizer']


def test_unresolved_fallbacks_honours_the_time_window():
    accounts, fallbacks = server.split_provider_health_state(_fallback_state())
    assert server.unresolved_fallbacks(
        accounts, fallbacks, cutoff=500, want_vision=False) == []


def test_unresolved_fallbacks_separates_vision_from_categorizer():
    """Each chain belongs to its own tile — they must not bleed into each other."""
    accounts, fallbacks = server.split_provider_health_state(_fallback_state())
    cat = server.unresolved_fallbacks(
        accounts, fallbacks, cutoff=0, want_vision=False)
    vis = server.unresolved_fallbacks(
        accounts, fallbacks, cutoff=0, want_vision=True)
    assert [p for p, _ in cat] == ['chatgpt-oauth-categorizer']
    assert [p for p, _ in vis] == ['chatgpt-oauth-vision']


def test_categorizer_tile_ignores_vision_fallbacks(monkeypatch, tmp_path):
    """A vision-only fallback must leave the Categorizer tile green."""
    path = tmp_path / 'provider_health.json'
    state = {
        'chatgpt-oauth-categorizer:eg': {'last_success': 200, 'last_failure': 99},
        'chatgpt-oauth-vision:_fallbacks': {
            'events': [{'time': time.time(), 'from': 'eg', 'to': 'moms',
                        'error': '429'}]},
    }
    path.write_text(json.dumps(state))
    monkeypatch.setattr(_docvision, 'MAZDA_PROVIDER_HEALTH_PATH', str(path))

    health = server.mazda_categorizer_fallback_health()
    assert health['ok'] is True
    assert not health.get('concern')


def test_categorizer_tile_flags_its_own_unrecovered_fallback(monkeypatch, tmp_path):
    path = tmp_path / 'provider_health.json'
    state = {
        'chatgpt-oauth-categorizer:eg': {'last_success': 0, 'last_failure': 99},
        # a healthy tier, so this exercises the yellow path rather than the
        # "every tier is failing" red path
        'chatgpt-oauth-categorizer:moms': {'last_success': 200, 'last_failure': 0},
        'chatgpt-oauth-categorizer:_fallbacks': {
            'events': [{'time': time.time(), 'from': 'eg', 'to': 'moms',
                        'error': '429'}]},
    }
    path.write_text(json.dumps(state))
    monkeypatch.setattr(_docvision, 'MAZDA_PROVIDER_HEALTH_PATH', str(path))

    health = server.mazda_categorizer_fallback_health()
    assert health.get('concern') is True
    assert 'unrecovered' in health['text']


def test_vision_provider_fallbacks_survives_a_missing_event_log(monkeypatch, tmp_path):
    """A missing log must never be the thing that colours the vision tile."""
    monkeypatch.setattr(_docvision, 'MAZDA_PROVIDER_HEALTH_PATH',
                        str(tmp_path / 'nope.json'))
    assert server.vision_provider_fallbacks() == ''


def test_vision_tile_flags_unrecovered_vision_fallback(monkeypatch, tmp_path):
    """Credential checks pass but real calls keep failing over — the Document
    Vision tile (not the Categorizer tile) must be the one that says so."""
    path = tmp_path / 'provider_health.json'
    path.write_text(json.dumps({
        'chatgpt-oauth-vision:eg': {'last_success': 0, 'last_failure': 99},
        'chatgpt-oauth-vision:_fallbacks': {
            'events': [{'time': time.time(), 'from': 'eg', 'to': 'moms',
                        'error': '429'}]},
    }))
    monkeypatch.setattr(_docvision, 'MAZDA_PROVIDER_HEALTH_PATH', str(path))

    summary = server.vision_provider_fallbacks()
    assert 'unrecovered vision fallback' in summary


def test_scanner_report_stalled_scan_still_reads_clearly(tmp_path, monkeypatch):
    """A stalled scan (the Last Freezer/Window Scan pages' worst case) must
    still name its document, flag the failure loudly, and explain the empty
    Verified Transactions table instead of rendering a wall of '--'."""
    _recent_report_env(tmp_path, monkeypatch, docs=())
    _scanner_registry(monkeypatch)
    server.record_recent_intake(
        '/staged/scan_freezer_1786536321_7340d041.jpg', 'Freezer Scanner')
    server.merge_recent_intake_event({
        'expense_ids': [], 'parsed': None, 'stored': None,
        'doc_kind': 'unknown', 'vendor': 'unknown', 'status': 'stalled',
        'status_detail': 'Verification lock cleared manually.',
    })
    monkeypatch.setattr(server, '_fetch_expenses_by_ids', lambda ids: [])
    monkeypatch.setattr(server, '_receipt_only_picker_assets',
                        lambda: ('', '', ''))

    html = server.build_scanner_report_html('freezer')

    assert 'unavailable' not in html
    assert '/staged/' not in _reader_visible_html(html)
    assert 'class="status-banner status-bad"' in html
    assert 'Mazda Trainer reported STALLED' in html
    assert 'stopped before any transactions were stored' in html


# ── MAZDA_DECISION_MODE=human_only / manual-entry form (2026-08-16) ────────
def test_resolve_execution_mode_unset_defaults_to_auto(monkeypatch):
    monkeypatch.delenv('MAZDA_DECISION_MODE', raising=False)
    assert server.resolve_execution_mode() == 'auto'


def test_resolve_execution_mode_parses_auto_and_human_only():
    assert server.resolve_execution_mode('auto') == 'auto'
    assert server.resolve_execution_mode('human_only') == 'human_only'


@pytest.mark.parametrize('bad', [
    'Auto', 'HUMAN_ONLY', 'human-only', 'humanonly', 'llm_only', '',
    ' auto', 'auto ', 'None',
])
def test_resolve_execution_mode_fails_closed_on_invalid_value(bad):
    """A typo must never silently fall back to 'auto' (could spend tokens
    unexpectedly) or silently disable Mazda — it must fail startup instead."""
    with pytest.raises(server.InvalidExecutionMode):
        server.resolve_execution_mode(bad)


def test_process_scanned_document_human_only_mode_never_dispatches_mazda_or_trainer(
        tmp_path, monkeypatch):
    """The single fork point: human_only must construct neither Mazda nor
    register a Trainer-escalation watch, and must leave the document visible
    as needing a human instead of silently dropping it."""
    scan_dir = tmp_path / 'scans'
    scan_dir.mkdir()
    write_scan_image(scan_dir / 'window_scan.jpg')
    monkeypatch.setattr(server, 'SCAN_TOOLS_DIR', str(scan_dir))
    monkeypatch.setattr(server, 'SCANNERS', {
        'window': {'name': 'Window Scanner', 'script': 'run_scan_window.sh',
                   'output': 'window_scan.jpg'},
    })
    monkeypatch.setattr(server, 'run_intake_facade',
                        lambda *a, **kw: {'ok': True, 'doc_kind': 'unknown', 'confidence': 0})
    monkeypatch.setattr(server, 'document_vision_health', lambda *a, **kw: {'ok': True})
    monkeypatch.setattr(server, '_stage_scan_for_mazda',
                        lambda local_path: '/staged/window_scan.jpg')
    monkeypatch.setattr(server, 'EXECUTION_MODE', 'human_only')
    threads_started = []
    monkeypatch.setattr(
        server.threading, 'Thread',
        lambda *a, **k: threads_started.append((a, k)) or _NoopThread())
    watch_calls = []
    monkeypatch.setattr(server, '_watch_intake_for_problems',
                        lambda *a, **k: watch_calls.append((a, k)))

    result = server.process_scanned_document('window')

    assert threads_started == []
    assert watch_calls == []
    assert result['mazda_dispatched'] is False
    assert result['trainer_dispatched'] is False
    assert result['execution_mode'] == 'human_only'
    assert result['conversation_id'] == 'conv-test-isolated'
    assert 'human_only' in result['stage_error']
    pointer = server._read_recent_pointer_file()
    intake = pointer['scanner_intakes']['Window Scanner']
    assert intake['status'] == 'needs_human_review'
    assert intake['status_source'] == 'human_only_mode'
    assert intake['execution_mode'] == 'human_only'


def test_process_pdf_document_human_only_mode_never_dispatches_mazda_or_trainer(
        tmp_path, monkeypatch):
    pdf_dir = tmp_path / 'rol'
    pdf_dir.mkdir()
    pdf = pdf_dir / 'statement.pdf'
    pdf.write_bytes(b'%PDF-fake')
    monkeypatch.setattr(server, 'ROL_FINANCES_DIR', str(pdf_dir))
    monkeypatch.setattr(server, 'run_intake_facade',
                        lambda path, org_id=1, engine='gemini': {'ok': True})
    monkeypatch.setattr(server, 'document_vision_health', lambda: {'ok': True})
    monkeypatch.setattr(server, 'EXECUTION_MODE', 'human_only')
    threads_started = []
    monkeypatch.setattr(
        server.threading, 'Thread',
        lambda *a, **k: threads_started.append((a, k)) or _NoopThread())
    watch_calls = []
    monkeypatch.setattr(server, '_watch_intake_for_problems',
                        lambda *a, **k: watch_calls.append((a, k)))

    result = server.process_pdf_document(str(pdf), label='Jan Statement')

    assert threads_started == []
    assert watch_calls == []
    assert result['mazda_dispatched'] is False
    assert result['trainer_dispatched'] is False
    assert result['execution_mode'] == 'human_only'
    assert result['conversation_id'] == 'conv-test-isolated'
    pointer = server._read_recent_pointer_file()
    assert pointer['intake']['status'] == 'needs_human_review'
    assert pointer['intake']['status_source'] == 'human_only_mode'

def test_submit_manual_receipt_entry_populates_expense_ids(tmp_path, monkeypatch):
    """A successful save must fold a STEP-8-shaped event, not just flip a
    status string -- expense_ids is what the Verified Transactions table and
    the archive-verification terminal both key off."""
    monkeypatch.setattr(
        server, 'RECENT_REPORT_POINTER_FILE', str(tmp_path / 'recent_report.json'))
    server.record_recent_intake(
        '/staged/scan_freezer.jpg', 'Freezer Scanner', kind='scan',
        conversation_id='conv-freezer-1', dispatched_at=100.0)
    monkeypatch.setattr(
        server.manual_entry, 'submit_manual_receipt_entry',
        lambda entry: (True, {'report': {'success': True, 'expense_id': 9001,
                                         'duplicate': False}}))

    result = server.submit_manual_receipt_entry({
        'image_path': '/staged/scan_freezer.jpg',
        'conversation_id': 'conv-freezer-1',
        'merchant_name': 'Kroger',
        'transaction_date': '2026-08-15',
        'total_amount': 12.34,
    })

    assert result == {'ok': True, 'expense_id': 9001, 'duplicate': False,
                       'vendor_remembered': None}
    pointer = server._read_recent_pointer_file()
    intake = pointer['scanner_intakes']['Freezer Scanner']
    assert intake['expense_ids'] == [9001]
    assert intake['status'] == 'complete'
    assert intake['doc_kind'] == 'receipt'
    assert intake['vendor'] == 'Kroger'


def test_submit_manual_receipt_entry_surfaces_vendor_remembered(tmp_path, monkeypatch):
    """When parse_and_categorize.py's --save persisted a brand-new vendor_key
    (see remember_new_vendor / VendorCategoryLookup.remember), that result
    must reach the client -- otherwise "+ Add new vendor" looks like it did
    nothing even when the yaml write actually succeeded."""
    monkeypatch.setattr(
        server, 'RECENT_REPORT_POINTER_FILE', str(tmp_path / 'recent_report.json'))
    server.record_recent_intake(
        '/staged/scan.jpg', 'Freezer Scanner', kind='scan',
        conversation_id='conv-new-vendor', dispatched_at=100.0)
    monkeypatch.setattr(
        server.manual_entry, 'submit_manual_receipt_entry',
        lambda entry: (True, {'report': {
            'success': True, 'expense_id': 55, 'duplicate': False,
            'vendor_remembered': {'remembered': True, 'vendor_key': 'samaritans_purse',
                                   'reason': None},
        }}))

    result = server.submit_manual_receipt_entry({
        'image_path': '/staged/scan.jpg',
        'conversation_id': 'conv-new-vendor',
        'merchant_name': 'Samaritans Purse',
        'transaction_date': '2026-08-16',
        'total_amount': 50.0,
    })

    assert result['vendor_remembered'] == {
        'remembered': True, 'vendor_key': 'samaritans_purse', 'reason': None,
    }


def test_submit_manual_receipt_entry_invalidates_receipt_index_on_success(
        tmp_path, monkeypatch):
    """The --save subprocess files a receipt to disk out-of-process -- the
    in-memory receipt index must be dropped so the archive-verification
    terminal and View Receipt button (which both query it immediately after
    this call returns) see the new file instead of a stale cached index.
    Regression for 'Archive path not found' right after a manual save."""
    monkeypatch.setattr(
        server, 'RECENT_REPORT_POINTER_FILE', str(tmp_path / 'recent_report.json'))
    monkeypatch.setattr(
        server.manual_entry, 'submit_manual_receipt_entry',
        lambda entry: (True, {'report': {'success': True, 'expense_id': 1,
                                         'duplicate': False}}))
    calls = []
    monkeypatch.setattr(server, '_invalidate_receipt_index', lambda: calls.append(1))

    result = server.submit_manual_receipt_entry({
        'image_path': '/staged/x.jpg', 'conversation_id': 'c',
        'merchant_name': 'Kroger', 'transaction_date': '2026-08-15',
        'total_amount': 1.0,
    })

    assert result['ok'] is True
    assert calls == [1]


def test_submit_manual_receipt_entry_does_not_invalidate_index_on_failure(
        monkeypatch):
    """A failed save wrote nothing new to disk -- no cache to drop."""
    monkeypatch.setattr(
        server.manual_entry, 'submit_manual_receipt_entry',
        lambda entry: (False, {'error': 'store failed'}))
    calls = []
    monkeypatch.setattr(server, '_invalidate_receipt_index', lambda: calls.append(1))

    result = server.submit_manual_receipt_entry({
        'image_path': '/staged/x.jpg', 'conversation_id': 'c',
        'merchant_name': 'Kroger', 'transaction_date': '2026-08-15',
        'total_amount': 1.0,
    })

    assert result['ok'] is False
    assert calls == []


def test_submit_manual_receipt_entry_duplicate_does_not_double_enter(
        tmp_path, monkeypatch):
    monkeypatch.setattr(
        server, 'RECENT_REPORT_POINTER_FILE', str(tmp_path / 'recent_report.json'))
    server.record_recent_intake(
        '/staged/scan_freezer.jpg', 'Freezer Scanner', kind='scan',
        conversation_id='conv-freezer-2', dispatched_at=100.0)
    monkeypatch.setattr(
        server.manual_entry, 'submit_manual_receipt_entry',
        lambda entry: (True, {'report': {'success': True, 'expense_id': 42,
                                         'duplicate': True}}))

    result = server.submit_manual_receipt_entry({
        'image_path': '/staged/scan_freezer.jpg',
        'conversation_id': 'conv-freezer-2',
        'merchant_name': 'Kroger',
        'transaction_date': '2026-08-15',
        'total_amount': 12.34,
    })

    assert result == {'ok': True, 'expense_id': 42, 'duplicate': True,
                       'vendor_remembered': None}
    pointer = server._read_recent_pointer_file()
    intake = pointer['scanner_intakes']['Freezer Scanner']
    assert intake['duplicate_expense_ids'] == [42]
    assert intake['stored'] == 0


def test_submit_manual_receipt_entry_resolves_category_name(monkeypatch):
    captured = {}

    def fake_submit(entry):
        captured['category_id'] = entry.category_id
        return True, {'report': {'success': True, 'expense_id': 1, 'duplicate': False}}

    monkeypatch.setattr(
        server, '_resolve_reporting_category',
        lambda name: (77, 'cat-food') if name == 'Food' else (None, None))
    monkeypatch.setattr(server.manual_entry, 'submit_manual_receipt_entry', fake_submit)
    monkeypatch.setattr(server, 'merge_recent_intake_event', lambda event: True)

    result = server.submit_manual_receipt_entry({
        'image_path': '/staged/x.jpg', 'conversation_id': 'c',
        'merchant_name': 'Kroger', 'transaction_date': '2026-08-15',
        'total_amount': 1.0, 'category_name': 'Food',
    })

    assert result['ok'] is True
    assert captured['category_id'] == 77


def test_submit_manual_receipt_entry_rejects_unknown_category_name(monkeypatch):
    monkeypatch.setattr(
        server, '_resolve_reporting_category', lambda name: (None, None))
    result = server.submit_manual_receipt_entry({
        'image_path': '/staged/x.jpg', 'conversation_id': 'c',
        'merchant_name': 'Kroger', 'transaction_date': '2026-08-15',
        'total_amount': 1.0, 'category_name': 'Not A Real Category',
    })
    assert result['ok'] is False
    assert 'category' in result['error'].lower()


def test_submit_manual_receipt_entry_save_failure_leaves_intake_pending(
        tmp_path, monkeypatch):
    """A failed save must not flip needs_human_review to complete -- the
    form has to reappear, same as the statement review dialog's contract."""
    monkeypatch.setattr(
        server, 'RECENT_REPORT_POINTER_FILE', str(tmp_path / 'recent_report.json'))
    server.record_recent_intake(
        '/staged/scan_freezer.jpg', 'Freezer Scanner', kind='scan',
        conversation_id='conv-freezer-3', dispatched_at=100.0)
    server.merge_recent_intake_status({
        'conversation_id': 'conv-freezer-3', 'status': 'needs_human_review',
        'status_source': 'human_only_mode',
    })
    monkeypatch.setattr(
        server.manual_entry, 'submit_manual_receipt_entry',
        lambda entry: (False, {'error': 'A verified merchant/counterparty is required'}))

    result = server.submit_manual_receipt_entry({
        'image_path': '/staged/scan_freezer.jpg',
        'conversation_id': 'conv-freezer-3',
        'merchant_name': 'receipt', 'transaction_date': '2026-08-15',
        'total_amount': 1.0,
    })

    assert result['ok'] is False
    pointer = server._read_recent_pointer_file()
    assert pointer['scanner_intakes']['Freezer Scanner']['status'] == 'needs_human_review'


def test_preview_manual_entry_archive_path_receipt_is_a_real_destination():
    result = server.preview_manual_entry_archive_path({
        'image_path': '/staged/scan.jpg', 'merchant_name': 'Kroger',
        'transaction_date': '2026-08-15', 'total_amount': 12.34,
        'archive_kind': 'receipt',
    })
    assert result['ok'] is True
    assert result['is_real_destination'] is True
    assert result['path'].endswith(
        'readable_documents/receipts/2026/august/august_15/kroger_08_15_26_12_34.jpg')


def test_preview_manual_entry_archive_path_scanned_document_is_preview_only():
    result = server.preview_manual_entry_archive_path({
        'image_path': '/staged/scan.jpg', 'merchant_name': 'Kroger',
        'transaction_date': '2026-08-15', 'total_amount': 12.34,
        'archive_kind': 'scanned_document',
    })
    assert result['ok'] is True
    assert result['is_real_destination'] is False


def test_preview_manual_entry_archive_path_rejects_non_numeric_amount():
    result = server.preview_manual_entry_archive_path({
        'image_path': '/staged/scan.jpg', 'merchant_name': 'Kroger',
        'transaction_date': '2026-08-15', 'total_amount': 'not-a-number',
    })
    assert result['ok'] is False


def test_preview_manual_entry_archive_path_rejects_bad_date():
    result = server.preview_manual_entry_archive_path({
        'image_path': '/staged/scan.jpg', 'merchant_name': 'Kroger',
        'transaction_date': 'not-a-date', 'total_amount': 12.34,
    })
    assert result['ok'] is False


# ---------------------------------------------------------------------------
# Edit Expense handlers (/api/expense-search, /api/expense-edit)
# ---------------------------------------------------------------------------

class _StubEditRepository:
    """Stands in for MySqlExpenseRecordRepository so the handlers can be tested
    without a finance DB -- the repository's own behaviour is covered by
    tests/test_expense_edit.py."""

    def __init__(self, records=(), result=None, error=None):
        self._records = list(records)
        self._result = result
        self._error = error
        self.edits = []

    def search(self, criteria):
        if self._error:
            raise self._error
        self.criteria = criteria
        return self._records

    def apply_edit(self, edit):
        if self._error:
            raise self._error
        self.edits.append(edit)
        return self._result


class _StubNamer:
    def __init__(self, mapping=None):
        self._mapping = mapping or {'Office': 140}

    def name_for(self, category_id):
        for name, cid in self._mapping.items():
            if cid == category_id:
                return name
        return ''

    def id_for(self, category_name):
        name = (category_name or '').strip()
        if not name:
            return None
        if name not in self._mapping:
            raise ValueError(f'Unknown category: {name!r}')
        return self._mapping[name]


def _stub_record(**overrides):
    from finance.expense_edit_model import ExpenseRecord
    fields = dict(id=501, transaction_date='2026-08-15', total_amount=12.34,
                  description='Kroger', id_light='kroger_08_15_26_12_34',
                  category_id=140, category_name='Office')
    fields.update(overrides)
    return ExpenseRecord(**fields)


def test_expense_search_returns_records_as_json():
    repo = _StubEditRepository(records=[_stub_record()])
    out = server.search_stored_expenses({'merchant': 'Kroger'}, repository=repo)
    assert out['ok'] is True
    assert out['records'][0]['id'] == 501
    assert out['records'][0]['category_name'] == 'Office'


def test_expense_search_reports_an_empty_criteria_set_as_a_message():
    repo = _StubEditRepository()
    out = server.search_stored_expenses({}, repository=repo)
    assert out['ok'] is False
    assert 'merchant' in out['error']


def test_expense_search_surfaces_a_database_failure_verbatim():
    repo = _StubEditRepository(error=RuntimeError('connection refused'))
    out = server.search_stored_expenses({'merchant': 'Kroger'}, repository=repo)
    assert out['ok'] is False
    assert 'connection refused' in out['error']


def _edit_body(**overrides):
    body = dict(expense_id=501, merchant_name='Kroger Fuel',
                transaction_date='2026-08-15', total_amount=20.0,
                category_name='Office')
    body.update(overrides)
    return body


def _edit_result(**overrides):
    from finance.expense_edit_model import ExpenseEditResult
    fields = dict(record=_stub_record(description='Kroger Fuel',
                                      total_amount=20.0),
                  changed_fields=('description', 'amount'),
                  warnings=('vendor key is stale',))
    fields.update(overrides)
    return ExpenseEditResult(**fields)


def test_expense_edit_resolves_the_category_name_to_an_id(monkeypatch):
    monkeypatch.setattr(server, '_invalidate_receipt_index', lambda: None)
    repo = _StubEditRepository(result=_edit_result())
    out = server.edit_stored_expense(
        _edit_body(), repository=repo, namer=_StubNamer())
    assert out['ok'] is True
    assert repo.edits[0].category_id == 140
    assert out['changed_fields'] == ['description', 'amount']
    assert out['warnings'] == ['vendor key is stale']


def test_expense_edit_learns_new_vendor_before_updating_description(monkeypatch):
    monkeypatch.setattr(server, '_invalidate_receipt_index', lambda: None)
    remembered = []

    class _Remembered:
        def model_dump(self):
            return {'remembered': True, 'vendor_key': 'cracker_barrel'}

    monkeypatch.setattr(
        server.vendor_lookup,
        'remember_vendor',
        lambda description, category_id, vendor_key: (
            remembered.append((description, category_id, vendor_key)) or _Remembered()),
    )
    repo = _StubEditRepository(result=_edit_result())

    out = server.edit_stored_expense(_edit_body(
        merchant_name='CRACKER BARREL #428 CA CAVE CITY KY',
        vendor_key='cracker_barrel', learn_vendor=True,
    ), repository=repo, namer=_StubNamer())

    assert out['ok'] is True
    assert remembered == [(
        'CRACKER BARREL #428 CA CAVE CITY KY', 140, 'cracker_barrel')]
    assert repo.edits[0].merchant_name == 'CRACKER BARREL #428 CA CAVE CITY KY'
    assert out['vendor_remembered']['vendor_key'] == 'cracker_barrel'


def test_expense_edit_learns_new_four_digit_dte_account(monkeypatch):
    monkeypatch.setattr(server, '_invalidate_receipt_index', lambda: None)
    remembered = []

    class _Remembered:
        def model_dump(self):
            return {
                'remembered': True,
                'vendor_key': 'dte_energy_1854',
                'reason': None,
            }

    monkeypatch.setattr(
        server.vendor_lookup, 'remember_vendor',
        lambda description, category_id, vendor_key: (
            remembered.append((description, category_id, vendor_key))
            or _Remembered()))
    repo = _StubEditRepository(result=_edit_result())

    out = server.edit_stored_expense(_edit_body(
        merchant_name='DTE Energy', vendor_key='dte_energy_1854',
        learn_vendor=True,
    ), repository=repo, namer=_StubNamer())

    assert out['ok'] is True
    assert remembered == [('DTE Energy', 140, 'dte_energy_1854')]
    assert len(repo.edits) == 1
    assert out['vendor_remembered']['vendor_key'] == 'dte_energy_1854'


def test_expense_edit_updates_when_selected_vendor_is_already_known(monkeypatch):
    monkeypatch.setattr(server, '_invalidate_receipt_index', lambda: None)

    class _AlreadyKnown:
        def model_dump(self):
            return {
                'remembered': False,
                'vendor_key': 'dte_energy_0544',
                'reason': 'vendor_key already known',
            }

    monkeypatch.setattr(
        server.vendor_lookup, 'remember_vendor', lambda *_args: _AlreadyKnown())
    repo = _StubEditRepository(result=_edit_result())

    out = server.edit_stored_expense(_edit_body(
        merchant_name='DTE Energy', vendor_key='dte_energy_0544',
        learn_vendor=True,
    ), repository=repo, namer=_StubNamer())

    assert out['ok'] is True
    assert len(repo.edits) == 1
    assert repo.edits[0].merchant_name == 'DTE Energy'
    assert out['vendor_remembered'] == {
        'remembered': False,
        'vendor_key': 'dte_energy_0544',
        'reason': 'vendor_key already known',
    }


def test_expense_edit_accepts_existing_key_for_broad_vendor_entry(monkeypatch):
    monkeypatch.setattr(server, '_invalidate_receipt_index', lambda: None)

    class _CanonicalAlreadyKnown:
        def model_dump(self):
            return {
                'remembered': False,
                'vendor_key': 'apple_com_bill',
                'reason': 'vendor_key already known',
            }

    monkeypatch.setattr(
        server.vendor_lookup, 'remember_vendor',
        lambda *_args: _CanonicalAlreadyKnown())
    repo = _StubEditRepository(result=_edit_result())

    out = server.edit_stored_expense(_edit_body(
        merchant_name='APPLE.COM/BILL', vendor_key='apple',
        learn_vendor=True,
    ), repository=repo, namer=_StubNamer())

    assert out['ok'] is True
    assert len(repo.edits) == 1
    assert out['vendor_remembered']['vendor_key'] == 'apple_com_bill'


def test_expense_edit_rejects_already_known_result_without_vendor_key(monkeypatch):
    class _MissingCanonicalKey:
        def model_dump(self):
            return {
                'remembered': False,
                'vendor_key': None,
                'reason': 'vendor_key already known',
            }

    monkeypatch.setattr(
        server.vendor_lookup, 'remember_vendor',
        lambda *_args: _MissingCanonicalKey())
    repo = _StubEditRepository(result=_edit_result())

    out = server.edit_stored_expense(_edit_body(
        merchant_name='APPLE.COM/BILL', vendor_key='apple',
        learn_vendor=True,
    ), repository=repo, namer=_StubNamer())

    assert out['ok'] is False
    assert 'Could not learn vendor' in out['error']
    assert repo.edits == []


def test_expense_edit_does_not_update_when_vendor_learning_fails(monkeypatch):
    monkeypatch.setattr(
        server.vendor_lookup, 'remember_vendor',
        lambda *_args: (_ for _ in ()).throw(OSError('read-only vendor map')),
    )
    repo = _StubEditRepository(result=_edit_result())

    out = server.edit_stored_expense(_edit_body(
        vendor_key='cracker_barrel', learn_vendor=True,
    ), repository=repo, namer=_StubNamer())

    assert out['ok'] is False
    assert 'read-only vendor map' in out['error']
    assert repo.edits == []


def test_expense_edit_does_not_update_on_ambiguous_vendor_learning(monkeypatch):
    class _NotRemembered:
        def model_dump(self):
            return {
                'remembered': False,
                'vendor_key': None,
                'reason': 'several stored vendor_keys match this name',
            }

    monkeypatch.setattr(
        server.vendor_lookup, 'remember_vendor', lambda *_args: _NotRemembered())
    repo = _StubEditRepository(result=_edit_result())
    out = server.edit_stored_expense(_edit_body(
        vendor_key='dte_energy', learn_vendor=True,
    ), repository=repo, namer=_StubNamer())
    assert out['ok'] is False
    assert 'several stored vendor_keys' in out['error']
    assert repo.edits == []


def test_expense_edit_refuses_new_vendor_without_category():
    repo = _StubEditRepository(result=_edit_result())
    out = server.edit_stored_expense(_edit_body(
        category_name='', vendor_key='cracker_barrel', learn_vendor=True,
    ), repository=repo, namer=_StubNamer())
    assert out['ok'] is False
    assert 'requires vendor_key and category' in out['error']
    assert repo.edits == []


def test_expense_edit_rejects_an_unknown_category():
    repo = _StubEditRepository(result=_edit_result())
    out = server.edit_stored_expense(
        _edit_body(category_name='Not A Category'),
        repository=repo, namer=_StubNamer())
    assert out['ok'] is False
    assert 'Unknown category' in out['error']
    assert repo.edits == []


def test_expense_edit_coerces_a_string_amount_at_the_boundary(monkeypatch):
    monkeypatch.setattr(server, '_invalidate_receipt_index', lambda: None)
    repo = _StubEditRepository(result=_edit_result())
    out = server.edit_stored_expense(
        _edit_body(total_amount='20.00'), repository=repo, namer=_StubNamer())
    assert out['ok'] is True
    assert repo.edits[0].total_amount == 20.0


@pytest.mark.parametrize('overrides', [
    {'expense_id': 'abc'},
    {'total_amount': 'twenty'},
    {'merchant_name': '   '},
    {'transaction_date': '08/15/2026'},
])
def test_expense_edit_refuses_a_malformed_body_without_writing(overrides):
    repo = _StubEditRepository(result=_edit_result())
    out = server.edit_stored_expense(
        _edit_body(**overrides), repository=repo, namer=_StubNamer())
    assert out['ok'] is False
    assert repo.edits == []


def test_expense_edit_reports_a_missing_row_as_a_message():
    from finance.expense_edit_model import ExpenseNotFound
    repo = _StubEditRepository(error=ExpenseNotFound('no expense with id 501'))
    out = server.edit_stored_expense(
        _edit_body(), repository=repo, namer=_StubNamer())
    assert out['ok'] is False
    assert 'no expense with id 501' in out['error']


def test_expense_edit_invalidates_the_receipt_index(monkeypatch):
    calls = []
    monkeypatch.setattr(server, '_invalidate_receipt_index',
                        lambda: calls.append(1))
    repo = _StubEditRepository(result=_edit_result())
    server.edit_stored_expense(_edit_body(), repository=repo, namer=_StubNamer())
    assert calls == [1]


# ---------------------------------------------------------------------------
# Boolean coercion at the HTTP boundary (found 2026-08-17)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('field', ['expense_id', 'total_amount'])
def test_expense_edit_refuses_a_json_boolean_as_a_number(field):
    # bool subclasses int, so int(True) == 1: {"expense_id": true} used to be
    # accepted and went on to edit expense row 1.
    repo = _StubEditRepository(result=_edit_result())
    out = server.edit_stored_expense(
        _edit_body(**{field: True}), repository=repo, namer=_StubNamer())
    assert out['ok'] is False
    assert 'boolean' in out['error']
    assert repo.edits == []


def test_expense_search_refuses_a_json_boolean_amount():
    repo = _StubEditRepository(records=[])
    out = server.search_stored_expenses({'amount': True}, repository=repo)
    assert out['ok'] is False
    assert 'boolean' in out['error']


def test_expense_search_refuses_a_json_boolean_limit():
    repo = _StubEditRepository(records=[])
    out = server.search_stored_expenses(
        {'merchant': 'Kroger', 'limit': True}, repository=repo)
    assert out['ok'] is False
    assert 'boolean' in out['error']


def test_manual_receipt_entry_refuses_a_json_boolean_amount():
    out = server.submit_manual_receipt_entry({
        'image_path': '/staged/scan.jpg', 'merchant_name': 'Kroger',
        'transaction_date': '2026-08-15', 'total_amount': True,
    })
    assert out['ok'] is False
    assert 'boolean' in out['error']


def test_archive_preview_refuses_a_json_boolean_amount():
    out = server.preview_manual_entry_archive_path({
        'image_path': '/staged/scan.jpg', 'merchant_name': 'Kroger',
        'transaction_date': '2026-08-15', 'total_amount': True,
    })
    assert out['ok'] is False
    assert 'boolean' in out['error']


def test_a_numeric_string_is_still_accepted_after_the_boolean_guard():
    # The guard must not have tightened the ordinary string coercion the
    # strict Pydantic models depend on.
    repo = _StubEditRepository(result=_edit_result())
    out = server.edit_stored_expense(
        _edit_body(expense_id='501', total_amount='20.00'),
        repository=repo, namer=_StubNamer())
    assert out['ok'] is True
    assert repo.edits[0].expense_id == 501
