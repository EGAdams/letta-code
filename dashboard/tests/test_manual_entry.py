"""Tests for the human_only-mode manual receipt entry form's backing logic.

The store subprocess is injected (`runner=`) so these run offline -- the real
finance DB and venv live on the other box.
"""
import json

import pytest
from pydantic import ValidationError

from finance import manual_entry


def _entry(**overrides):
    fields = dict(
        image_path='/staged/scan_freezer.jpg',
        merchant_name='Kroger',
        transaction_date='2026-08-15',
        total_amount=12.34,
        category_id=None,
        org_id=1,
    )
    fields.update(overrides)
    return manual_entry.ManualReceiptEntry(**fields)


def test_rejects_empty_merchant_name():
    with pytest.raises(ValidationError):
        _entry(merchant_name='   ')


def test_rejects_non_iso_date():
    with pytest.raises(ValidationError):
        _entry(transaction_date='08/15/2026')


@pytest.mark.parametrize('bad_amount', [0, -5.0])
def test_rejects_non_positive_amount(bad_amount):
    with pytest.raises(ValidationError):
        _entry(total_amount=bad_amount)


def test_rejects_empty_image_path():
    with pytest.raises(ValidationError):
        _entry(image_path='  ')


def test_merchant_name_whitespace_is_collapsed():
    entry = _entry(merchant_name='  Kroger   Freezer  ')
    assert entry.merchant_name == 'Kroger Freezer'


def test_build_save_command_uses_local_engine_and_overrides():
    """--engine local is load-bearing: the only value that spends zero
    tokens (see parse_and_categorize.py's _parse_receipt tier selection)."""
    cmd = manual_entry.build_save_command(_entry())
    assert '--engine' in cmd
    assert cmd[cmd.index('--engine') + 1] == 'local'
    assert '--no-pick' in cmd
    assert '--save' in cmd
    # The two free-text values use the `--opt=value` form (see
    # build_save_command): argparse rejects a separate value starting with a
    # dash, which a merchant name can legitimately do.
    assert '--file=/staged/scan_freezer.jpg' in cmd
    assert '--merchant-name-override=Kroger' in cmd
    assert cmd[cmd.index('--transaction-date-override') + 1] == '2026-08-15'
    assert cmd[cmd.index('--total-amount-override') + 1] == '12.34'
    assert cmd[cmd.index('--org-id') + 1] == '1'
    assert '--category-id' not in cmd


def test_build_save_command_includes_category_id_when_given():
    cmd = manual_entry.build_save_command(_entry(category_id=42))
    assert cmd[cmd.index('--category-id') + 1] == '42'


def test_submit_manual_receipt_entry_success(monkeypatch):
    calls = []

    def fake_runner(command):
        calls.append(command)
        return {
            'returncode': 0,
            'stdout': '{"success": true, "expense_id": 9001, "duplicate": false}',
            'stderr': '',
            'report': {'success': True, 'expense_id': 9001, 'duplicate': False},
        }

    ok, payload = manual_entry.submit_manual_receipt_entry(_entry(), runner=fake_runner)
    assert ok is True
    assert payload['report']['expense_id'] == 9001
    assert len(calls) == 1


def test_submit_manual_receipt_entry_merchant_required_failure():
    def fake_runner(command):
        return {
            'returncode': 1,
            'stdout': '{"success": false, "error": "A verified merchant/counterparty is required before saving", "merchant_required": true}',
            'stderr': '',
            'report': {'success': False,
                       'error': 'A verified merchant/counterparty is required before saving',
                       'merchant_required': True},
        }

    ok, payload = manual_entry.submit_manual_receipt_entry(_entry(), runner=fake_runner)
    assert ok is False
    assert 'merchant' in payload['error'].lower()


def test_submit_manual_receipt_entry_transport_failure_never_raises():
    def boom_runner(command):
        return {'returncode': 1, 'stderr': 'OSError: no such file', 'stdout': '', 'report': {}}

    ok, payload = manual_entry.submit_manual_receipt_entry(_entry(), runner=boom_runner)
    assert ok is False
    assert 'OSError' in payload['error']


def test_build_preview_command_uses_local_engine_and_json_no_save():
    cmd = manual_entry.build_preview_command('/staged/scan_freezer.jpg')
    assert cmd[cmd.index('--engine') + 1] == 'local'
    assert '--json' in cmd
    assert '--save' not in cmd
    assert cmd[cmd.index('--file') + 1] == '/staged/scan_freezer.jpg'


def test_build_preview_command_accepts_gemini_only_engine():
    cmd = manual_entry.build_preview_command('/staged/scan.jpg', engine='gemini-only')
    assert cmd[cmd.index('--engine') + 1] == 'gemini-only'


def test_build_preview_command_accepts_haiku_only_engine():
    cmd = manual_entry.build_preview_command('/staged/scan.jpg', engine='haiku-only')
    assert cmd[cmd.index('--engine') + 1] == 'haiku-only'


def test_build_preview_command_rejects_any_other_engine():
    # PREVIEW_ENGINES is a hard allow-list -- 'gemini'/'chatgpt-oauth'/'openai'
    # must never reach a preview request, since 'gemini' is parse_and_categorize.py's
    # full-auto-chain alias (can fall through to paid tiers on Gemini failure)
    # and the other two are paid tiers outright.
    for engine in ('gemini', 'chatgpt-oauth', 'openai', 'auto', 'bogus'):
        with pytest.raises(ValueError):
            manual_entry.build_preview_command('/staged/scan.jpg', engine=engine)


class _NoMatch:
    vendor_key = None
    category_name = None


class _NoVendorLookup:
    """Stand-in for VendorCategoryLookup that never matches anything --
    tests inject this via preview_receipt_parse's vendor_lookup_fn= so they
    don't depend on the real vendor_category.yaml (mirrors the file's
    runner= injection style)."""

    def find_vendor_match(self, merchant_name, document_text=''):
        return _NoMatch()


def _no_vendor_match():
    return _NoVendorLookup()


def test_preview_receipt_parse_extracts_prefill_fields():
    def fake_runner(command):
        return {
            'returncode': 0,
            'stdout': '', 'stderr': '',
            'report': {
                'party': {'merchant_name': 'Kroger'},
                'transaction_date': '2026-08-15',
                'totals': {'total_amount': 12.34},
            },
        }

    ok, prefill = manual_entry.preview_receipt_parse(
        '/staged/scan.jpg', runner=fake_runner, vendor_lookup_fn=_no_vendor_match)
    assert ok is True
    assert prefill == {
        'merchant_name': 'Kroger',
        'transaction_date': '2026-08-15',
        'total_amount': 12.34,
        'vendor_key': None,
        'category_name': None,
        'vendor_ambiguous': False,
        'vendor_candidates': [],
        'possible_statement': False,
    }


def test_preview_receipt_parse_flags_a_statement_shaped_document():
    """Prefill from OCR runs for free before the operator touches anything --
    if the raw text it already read looks like a multi-transaction statement
    table, the form should know that without a second call."""
    def fake_runner(command):
        return {
            'returncode': 0, 'stdout': '', 'stderr': '',
            'report': {
                'party': {'merchant_name': None},
                'transaction_date': None,
                'totals': {'total_amount': None},
                'meta': {'raw_text': (
                    '05/22 QUALITY INNS JASPER TN $93.99\n'
                    '05/23 ECONO LODGE VALDOSTA GA $87.80\n'
                )},
            },
        }

    ok, prefill = manual_entry.preview_receipt_parse(
        '/staged/scan.jpg', runner=fake_runner)
    assert ok is False  # no receipt-shaped field was readable
    assert prefill['possible_statement'] is True


def test_preview_receipt_parse_does_not_flag_an_ordinary_receipt():
    def fake_runner(command):
        return {
            'returncode': 0, 'stdout': '', 'stderr': '',
            'report': {
                'party': {'merchant_name': 'Kroger'},
                'transaction_date': '2026-08-15',
                'totals': {'total_amount': 12.34},
                'meta': {'raw_text': 'KROGER\n06/15/2025\nMILK $3.49\nBREAD $2.99\n'},
            },
        }

    ok, prefill = manual_entry.preview_receipt_parse(
        '/staged/scan.jpg', runner=fake_runner, vendor_lookup_fn=_no_vendor_match)
    assert ok is True
    assert prefill['possible_statement'] is False


def test_preview_receipt_parse_partial_fields_still_prefill_what_was_found():
    """OCR partially failing (e.g. handwriting) must still let the form
    prefill whatever it did find -- never block the form on an incomplete
    read. Missing fields come back None; the human types those in."""
    def fake_runner(command):
        return {
            'returncode': 0, 'stdout': '', 'stderr': '',
            'report': {'party': {'merchant_name': 'Kroger'}},
        }

    ok, prefill = manual_entry.preview_receipt_parse(
        '/staged/scan.jpg', runner=fake_runner, vendor_lookup_fn=_no_vendor_match)
    assert ok is True
    assert prefill['merchant_name'] == 'Kroger'
    assert prefill['transaction_date'] is None
    assert prefill['total_amount'] is None
    assert prefill['vendor_key'] is None
    assert prefill['category_name'] is None


def test_preview_receipt_parse_surfaces_a_matched_vendor_key_and_category():
    class _Match:
        vendor_key = 'consumers_energy'
        category_name = 'Utilities'

    class _MatchingLookup:
        def find_vendor_match(self, merchant_name, document_text=''):
            assert merchant_name == 'Consumers Energy'
            return _Match()

    def fake_runner(command):
        return {
            'returncode': 0, 'stdout': '', 'stderr': '',
            'report': {'party': {'merchant_name': 'Consumers Energy'}},
        }

    ok, prefill = manual_entry.preview_receipt_parse(
        '/staged/scan.jpg', runner=fake_runner, vendor_lookup_fn=_MatchingLookup)
    assert ok is True
    assert prefill['vendor_key'] == 'consumers_energy'
    assert prefill['category_name'] == 'Utilities'


def test_preview_receipt_parse_vendor_lookup_failure_never_breaks_prefill():
    """A lookup error (e.g. a malformed vendor_category.yaml) must not turn
    a successful OCR read into a failed preview -- same fail-soft posture
    as OCR itself."""
    class _BoomLookup:
        def find_vendor_match(self, merchant_name, document_text=''):
            raise RuntimeError('yaml parse error')

    def fake_runner(command):
        return {
            'returncode': 0, 'stdout': '', 'stderr': '',
            'report': {'party': {'merchant_name': 'Kroger'}},
        }

    ok, prefill = manual_entry.preview_receipt_parse(
        '/staged/scan.jpg', runner=fake_runner, vendor_lookup_fn=_BoomLookup)
    assert ok is True
    assert prefill['merchant_name'] == 'Kroger'
    assert prefill['vendor_key'] is None
    assert prefill['category_name'] is None


def test_preview_receipt_parse_rejects_bad_engine_without_raising():
    def fail_runner(command):
        raise AssertionError('should never run a subprocess for a rejected engine')

    ok, payload = manual_entry.preview_receipt_parse(
        '/staged/scan.jpg', engine='gemini', runner=fail_runner)
    assert ok is False
    assert 'error' in payload


def test_preview_receipt_parse_empty_report_is_a_failure():
    """A completely empty report means the subprocess produced no decodable
    JSON at all -- a transport/format failure, not "nothing found"."""
    def fake_runner(command):
        return {'returncode': 0, 'stdout': '', 'stderr': '', 'report': {}}

    ok, prefill = manual_entry.preview_receipt_parse('/staged/scan.jpg', runner=fake_runner)
    assert ok is False
    assert 'error' in prefill


def test_preview_receipt_parse_ocr_process_failure_is_reported_not_raised():
    def boom_runner(command):
        return {'returncode': 1, 'stderr': 'tesseract not found', 'stdout': '', 'report': {}}

    ok, payload = manual_entry.preview_receipt_parse('/staged/scan.jpg', runner=boom_runner)
    assert ok is False
    assert 'tesseract' in payload['error']


def test_preview_receipt_parse_gemini_only_surfaces_an_auth_failure_not_a_generic_blank():
    """A bad/expired GEMINI_API_KEY makes _try_gemini_parse fail and fall back
    to the zero-token local parser, which (for a receipt local OCR truly
    can't read) returns an empty report -- same shape as a plain unreadable
    scan. Without pulling parse_and_categorize.py's own stderr line into the
    error, an operator can't tell "rotate the key" from "rescan the receipt"."""
    def fake_runner(command):
        return {
            'returncode': 0,
            'stdout': '{"transaction_date": null, "party": {}, "totals": {}, "meta": {}}',
            'stderr': (
                "Gemini parsing failed: 401 Request had invalid authentication "
                "credentials.\nFalling back to local parser after AI engine failure."
            ),
            'report': {'transaction_date': None, 'party': {}, 'totals': {}, 'meta': {}},
        }

    ok, payload = manual_entry.preview_receipt_parse(
        '/staged/scan.jpg', engine='gemini-only', runner=fake_runner)
    assert ok is False
    assert 'Gemini parsing failed: 401' in payload['error']


def test_preview_receipt_parse_haiku_only_surfaces_a_logged_out_failure_not_a_generic_blank():
    """A logged-out ~/.claude/.credentials.json makes _try_haiku_parse fail and
    fall back to the zero-token local parser, same "auth failure looks like a
    blank scan" gap gemini-only's test above covers."""
    def fake_runner(command):
        return {
            'returncode': 0,
            'stdout': '{"transaction_date": null, "party": {}, "totals": {}, "meta": {}}',
            'stderr': (
                "Claude parsing failed: logged out (no OAuth token on this host)\n"
                "Falling back to local parser after AI engine failure."
            ),
            'report': {'transaction_date': None, 'party': {}, 'totals': {}, 'meta': {}},
        }

    ok, payload = manual_entry.preview_receipt_parse(
        '/staged/scan.jpg', engine='haiku-only', runner=fake_runner)
    assert ok is False
    assert 'Claude parsing failed: logged out' in payload['error']


def test_preview_receipt_parse_local_engine_never_reports_ai_stderr_noise():
    """engine='local' never runs an AI tier, so even if its stderr happened to
    contain an unrelated "parsing failed" line, it must not be attributed to
    an engine that was never asked to run."""
    def fake_runner(command):
        return {
            'returncode': 0,
            'stdout': '{"transaction_date": null, "party": {}, "totals": {}, "meta": {}}',
            'stderr': 'some unrelated parsing failed message',
            'report': {'transaction_date': None, 'party': {}, 'totals': {}, 'meta': {}},
        }

    ok, payload = manual_entry.preview_receipt_parse('/staged/scan.jpg', runner=fake_runner)
    assert ok is False
    assert payload['error'] == 'OCR could not read any fields from this document'


# ── _extract_json_result: regression coverage for the 2026-08-16 bug ────────
# A real save succeeded (the receipt file was moved into archive storage) but
# was reported as a failure, because an earlier, incidental JSON-shaped dict
# on stdout (a receipt-metadata debug print, unrelated to the save result)
# was mistaken for the actual result. Root cause: the extraction scanned for
# the FIRST decodable JSON object in stdout, not the last, and didn't check
# that it was actually the save result (it never carried a 'success' key).

def test_extract_json_result_skips_an_earlier_unrelated_json_object():
    stdout = (
        'Falling back to local parser after AI engine failure.\n'
        '{"merchant_name": "Kroger", "merchant_phone": null}\n'
        '{"success": true, "expense_id": 9001, "duplicate": false}\n'
    )
    result = manual_entry._extract_json_result(stdout, required_key='success')
    assert result == {'success': True, 'expense_id': 9001, 'duplicate': False}


def test_extract_json_result_returns_last_match_when_no_key_required():
    stdout = '{"a": 1}\n{"b": 2}\n'
    assert manual_entry._extract_json_result(stdout) == {'b': 2}


def test_extract_json_result_handles_indented_multiline_json():
    stdout = 'warning noise\n' + json.dumps({'ok': True, 'party': {'merchant_name': 'Kroger'}}, indent=2)
    assert manual_entry._extract_json_result(stdout) == {
        'ok': True, 'party': {'merchant_name': 'Kroger'}}


def test_extract_json_result_no_decodable_json_returns_empty_dict():
    assert manual_entry._extract_json_result('no json here at all') == {}


def test_submit_manual_receipt_entry_uses_default_runner_with_required_key(monkeypatch):
    """End-to-end (subprocess mocked, not the runner) reproduction of the
    actual bug: a successful save whose stdout has an incidental JSON object
    ahead of the real result must still be read as success."""
    class FakeCompleted:
        returncode = 0
        stdout = (
            'pytesseract import failed: No module named \'pytesseract\'\n'
            '{"merchant_name": "Kroger", "merchant_phone": null}\n'
            '{"success": true, "expense_id": 42, "duplicate": false}\n'
        )
        stderr = ''

    monkeypatch.setattr(manual_entry.subprocess, 'run', lambda *a, **k: FakeCompleted())
    ok, payload = manual_entry.submit_manual_receipt_entry(_entry())
    assert ok is True
    assert payload['report']['expense_id'] == 42


# ---------------------------------------------------------------------------
# Ambiguous vendor prefill (DTE repro, 2026-08-17)
# ---------------------------------------------------------------------------

class _FakeMatch:
    def __init__(self, vendor_key=None, category_name=None,
                 ambiguous=False, candidates=()):
        self.vendor_key = vendor_key
        self.category_name = category_name
        self.ambiguous = ambiguous
        self.candidates = list(candidates)


class _FakeCandidate:
    def __init__(self, vendor_key, category_name):
        self.vendor_key = vendor_key
        self.category_name = category_name


class _FakeLookup:
    """Records what find_vendor_match was called with, so the tests can assert
    the document text actually reaches the disambiguator."""

    def __init__(self, match):
        self.match = match
        self.calls = []

    def find_vendor_match(self, merchant_name, document_text=''):
        self.calls.append((merchant_name, document_text))
        return self.match


DTE_CANDIDATES = (
    _FakeCandidate('dte_energy_0544', 'Housing Gas Bill'),
    _FakeCandidate('dte_energy_0020', 'Church Electric Bill'),
)


def test_ambiguous_vendor_prefills_nothing_but_reports_candidates():
    lookup = _FakeLookup(_FakeMatch(ambiguous=True, candidates=DTE_CANDIDATES))
    out = manual_entry.resolve_vendor_match('DTE Energy', lambda: lookup)
    assert out['vendor_key'] is None
    assert out['category_name'] is None
    assert out['vendor_ambiguous'] is True
    assert [c['vendor_key'] for c in out['vendor_candidates']] == [
        'dte_energy_0544', 'dte_energy_0020']


def test_unambiguous_vendor_reports_no_candidates():
    lookup = _FakeLookup(_FakeMatch(vendor_key='kroger', category_name='Food'))
    out = manual_entry.resolve_vendor_match('Kroger', lambda: lookup)
    assert out['vendor_key'] == 'kroger'
    assert out['vendor_ambiguous'] is False
    assert out['vendor_candidates'] == []


def test_document_text_is_passed_through_to_the_vendor_lookup():
    lookup = _FakeLookup(_FakeMatch(vendor_key='dte_energy_0544'))
    manual_entry.resolve_vendor_match(
        'DTE Energy', lambda: lookup, document_text='Account Number 0544')
    assert lookup.calls == [('DTE Energy', 'Account Number 0544')]


def test_vendor_lookup_failure_still_fails_soft():
    class _Boom:
        def find_vendor_match(self, *a, **kw):
            raise RuntimeError('yaml unreadable')

    out = manual_entry.resolve_vendor_match('DTE Energy', lambda: _Boom())
    assert out == {'vendor_key': None, 'category_name': None,
                   'vendor_ambiguous': False, 'vendor_candidates': []}


def test_document_text_is_read_from_the_parse_payloads_meta():
    assert manual_entry._document_text(
        {'meta': {'raw_text': 'Account Number 9100 210 8054 4'}}
    ) == 'Account Number 9100 210 8054 4'


@pytest.mark.parametrize('payload', [
    {}, {'meta': None}, {'meta': 'not a dict'}, {'meta': {}},
    {'meta': {'raw_text': None}}, {'meta': {'raw_text': 123}},
])
def test_missing_or_malformed_raw_text_is_an_empty_string_not_a_crash(payload):
    assert manual_entry._document_text(payload) == ''


def test_preview_forwards_the_documents_raw_text_to_the_vendor_lookup():
    lookup = _FakeLookup(_FakeMatch(vendor_key='dte_energy_0544',
                                    category_name='Housing Gas Bill'))
    report = {
        'party': {'merchant_name': 'DTE Energy'},
        'transaction_date': '2025-05-12',
        'totals': {'total_amount': 90.34},
        'meta': {'raw_text': 'Account Number 9100 210 8054 4'},
    }
    ok, payload = manual_entry.preview_receipt_parse(
        '/staged/dte.jpg',
        runner=lambda cmd: {'returncode': 0, 'report': report},
        vendor_lookup_fn=lambda: lookup)
    assert ok is True
    assert lookup.calls == [('DTE Energy', 'Account Number 9100 210 8054 4')]
    assert payload['vendor_key'] == 'dte_energy_0544'


# ---------------------------------------------------------------------------
# Category label vocabulary (found 2026-08-17)
# ---------------------------------------------------------------------------
#
# VendorCategoryLookup answers in categories_tree.txt's LEAF names ("Housing
# Gas Bill"); the form's dropdown is built from the taxonomy's REPORTING BUCKET
# labels ("Housing Payment & Upkeep"). Handing the form a leaf name silently
# did nothing -- a <select> ignores a value matching no <option> -- so a
# correctly-resolved vendor still left Category blank with no error anywhere.
# Mazda's own pipeline was unaffected: it writes a raw category_id straight to
# the DB and never needs a label.

class _FakeNamer:
    BUCKETS = {311: 'Housing Payment & Upkeep', 123: 'Church Utilities'}

    def name_for(self, category_id):
        return self.BUCKETS.get(category_id, '')

    def id_for(self, category_name):
        raise NotImplementedError


class _LeafMatch:
    """What VendorCategoryLookup really returns: a leaf name plus its id."""

    def __init__(self, vendor_key=None, category_id=None, category_name=None,
                 ambiguous=False, candidates=()):
        self.vendor_key = vendor_key
        self.category_id = category_id
        self.category_name = category_name
        self.ambiguous = ambiguous
        self.candidates = list(candidates)


def test_vendor_category_is_translated_to_a_selectable_bucket_label():
    lookup = _FakeLookup(_LeafMatch(
        vendor_key='dte_energy_0544', category_id=311,
        category_name='Housing Gas Bill'))
    out = manual_entry.resolve_vendor_match(
        'DTE Energy', lambda: lookup, category_namer=_FakeNamer())
    assert out['vendor_key'] == 'dte_energy_0544'
    assert out['category_name'] == 'Housing Payment & Upkeep', (
        "the form's dropdown holds reporting buckets, not tree leaf names")


def test_ambiguous_candidates_also_get_selectable_bucket_labels():
    lookup = _FakeLookup(_LeafMatch(ambiguous=True, candidates=(
        _LeafMatch(vendor_key='dte_energy_0544', category_id=311,
                   category_name='Housing Gas Bill'),
        _LeafMatch(vendor_key='dte_energy_0020', category_id=123,
                   category_name='Church Electric Bill'),
    )))
    out = manual_entry.resolve_vendor_match(
        'DTE Energy', lambda: lookup, category_namer=_FakeNamer())
    assert [c['category_name'] for c in out['vendor_candidates']] == [
        'Housing Payment & Upkeep', 'Church Utilities']


def test_without_a_namer_the_leaf_name_is_left_alone():
    # Offline tests and any caller that hasn't wired the taxonomy keep the old
    # behaviour rather than losing the name entirely.
    lookup = _FakeLookup(_LeafMatch(
        vendor_key='dte_energy_0544', category_id=311,
        category_name='Housing Gas Bill'))
    out = manual_entry.resolve_vendor_match('DTE Energy', lambda: lookup)
    assert out['category_name'] == 'Housing Gas Bill'


def test_a_taxonomy_failure_leaves_the_dropdown_alone_instead_of_breaking():
    class _BoomNamer:
        def name_for(self, category_id):
            raise RuntimeError('taxonomy unreachable')

        def id_for(self, category_name):
            raise NotImplementedError

    lookup = _FakeLookup(_LeafMatch(
        vendor_key='dte_energy_0544', category_id=311,
        category_name='Housing Gas Bill'))
    out = manual_entry.resolve_vendor_match(
        'DTE Energy', lambda: lookup, category_namer=_BoomNamer())
    assert out['vendor_key'] == 'dte_energy_0544'
    assert out['category_name'] is None


def test_a_vendor_with_no_category_stays_uncategorized():
    lookup = _FakeLookup(_LeafMatch(vendor_key='kroger', category_id=None))
    out = manual_entry.resolve_vendor_match(
        'Kroger', lambda: lookup, category_namer=_FakeNamer())
    assert out['category_name'] is None


def test_an_unmapped_category_id_yields_no_label_rather_than_a_bad_one():
    lookup = _FakeLookup(_LeafMatch(
        vendor_key='x', category_id=9999, category_name='Some Leaf'))
    out = manual_entry.resolve_vendor_match(
        'X', lambda: lookup, category_namer=_FakeNamer())
    assert out['category_name'] is None


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_a_candidate_with_no_category_id_keeps_its_own_name_as_a_label():
    # The label is display-only on the pick-list button, so falling back to
    # whatever name the candidate carried beats showing the operator nothing.
    # _chooseVendorCandidate still only sets the dropdown for a selectable one.
    lookup = _FakeLookup(_FakeMatch(ambiguous=True, candidates=DTE_CANDIDATES))
    out = manual_entry.resolve_vendor_match(
        'DTE Energy', lambda: lookup, category_namer=_FakeNamer())
    assert [c['category_name'] for c in out['vendor_candidates']] == [
        'Housing Gas Bill', 'Church Electric Bill']
    assert [c['vendor_key'] for c in out['vendor_candidates']] == [
        'dte_energy_0544', 'dte_energy_0020']


class _OldMatch:
    """A VendorMatch from before ambiguous/candidates existed."""
    vendor_key = 'kroger'
    category_id = None
    category_name = 'Food'


def test_a_match_object_without_the_new_attributes_still_works():
    # getattr defaults keep the boundary tolerant of a stale library rather
    # than raising AttributeError in the middle of a prefill.
    lookup = _FakeLookup(_OldMatch())
    out = manual_entry.resolve_vendor_match('Kroger', lambda: lookup)
    assert out['vendor_ambiguous'] is False
    assert out['vendor_candidates'] == []
    assert out['vendor_key'] == 'kroger'


@pytest.mark.parametrize('name', ['', '   ', None])
def test_a_blank_merchant_name_skips_the_lookup_entirely(name):
    lookup = _FakeLookup(_FakeMatch(vendor_key='should_not_be_used'))
    out = manual_entry.resolve_vendor_match(name, lambda: lookup)
    assert out['vendor_key'] is None
    assert lookup.calls == []


def test_document_text_defaults_to_empty_when_the_payload_has_no_meta():
    lookup = _FakeLookup(_FakeMatch(vendor_key='kroger'))
    manual_entry.preview_receipt_parse(
        '/x.jpg',
        runner=lambda c: {'returncode': 0, 'report': {
            'party': {'merchant_name': 'Kroger'}}},
        vendor_lookup_fn=lambda: lookup)
    assert lookup.calls == [('Kroger', '')]


def test_a_very_large_raw_text_is_passed_through_unchanged():
    big = 'Account Number 0544 ' + ('x' * 50_000)
    assert manual_entry._document_text({'meta': {'raw_text': big}}) == big


def test_an_empty_raw_text_string_is_returned_as_empty():
    assert manual_entry._document_text({'meta': {'raw_text': ''}}) == ''


# ---------------------------------------------------------------------------
# argv safety: values that look like options
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('merchant', ['-Kroger', '-5Below', '--save', '-'])
def test_a_merchant_name_that_looks_like_a_flag_stays_one_argv_token(merchant):
    # `--opt value` with a dash-leading value is read by argparse as an unknown
    # option and the save fails; `--opt=value` is always taken as the value.
    cmd = manual_entry.build_save_command(_entry(merchant_name=merchant))
    assert f'--merchant-name-override={merchant}' in cmd
    # The bare option name never appears, so there is no separate value for
    # argparse to mistake for an option in the first place.
    assert '--merchant-name-override' not in cmd


def test_a_dash_leading_image_path_is_also_pinned_to_its_option():
    cmd = manual_entry.build_save_command(_entry(image_path='-weird.jpg'))
    assert '--file=-weird.jpg' in cmd


def test_a_merchant_name_with_spaces_and_quotes_stays_a_single_token():
    # The command is a list, never a shell string, so nothing needs quoting --
    # but it must still arrive as exactly one element.
    name = 'Bob\'s "Big" Boy & Co'
    cmd = manual_entry.build_save_command(_entry(merchant_name=name))
    assert cmd.count(f'--merchant-name-override={name}') == 1


# ---------------------------------------------------------------------------
# _extract_json_result: the store subprocess's real result
# ---------------------------------------------------------------------------
#
# Load-bearing and previously the site of a real defect (a first-match scan
# grabbed an unrelated debug dict and reported a successful save as a failure).

def test_a_brace_inside_a_string_value_does_not_fool_the_scanner():
    out = '{"note": "a { brace", "success": true, "expense_id": 7}'
    assert manual_entry._extract_json_result(out, 'success')['expense_id'] == 7


def test_a_debug_dict_printed_before_the_result_is_skipped():
    out = '{"debug": 1}\n{"success": true, "expense_id": 9}'
    assert manual_entry._extract_json_result(out, 'success')['expense_id'] == 9


def test_trailing_noise_after_the_result_does_not_lose_it():
    out = '{"success": true, "expense_id": 3}\nWarning: deprecated'
    assert manual_entry._extract_json_result(out, 'success')['expense_id'] == 3


def test_the_last_result_wins_when_several_carry_the_key():
    out = '{"success": false}\n{"success": true, "expense_id": 5}'
    assert manual_entry._extract_json_result(out, 'success')['expense_id'] == 5


def test_a_nested_object_is_not_rescanned_as_its_own_candidate():
    out = '{"success": true, "party": {"merchant_name": "Kroger"}}'
    result = manual_entry._extract_json_result(out, 'success')
    assert result['party'] == {'merchant_name': 'Kroger'}


@pytest.mark.parametrize('out', [
    '{"success": true, ',       # truncated
    'Traceback: boom',          # no JSON at all
    '',                         # nothing
    None,                       # not even a string
    '[1, 2, 3]',                # JSON, but not an object
    '{"other": 1}',             # an object, but without the required key
])
def test_output_with_no_usable_result_is_an_empty_dict_not_a_crash(out):
    assert manual_entry._extract_json_result(out, 'success') == {}


def test_without_a_required_key_the_last_object_of_any_shape_wins():
    out = '{"a": 1}\n{"b": 2}'
    assert manual_entry._extract_json_result(out) == {'b': 2}
