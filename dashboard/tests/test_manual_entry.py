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
    assert cmd[cmd.index('--file') + 1] == '/staged/scan_freezer.jpg'
    assert cmd[cmd.index('--merchant-name-override') + 1] == 'Kroger'
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

    ok, prefill = manual_entry.preview_receipt_parse('/staged/scan.jpg', runner=fake_runner)
    assert ok is True
    assert prefill == {
        'merchant_name': 'Kroger',
        'transaction_date': '2026-08-15',
        'total_amount': 12.34,
    }


def test_preview_receipt_parse_partial_fields_still_prefill_what_was_found():
    """OCR partially failing (e.g. handwriting) must still let the form
    prefill whatever it did find -- never block the form on an incomplete
    read. Missing fields come back None; the human types those in."""
    def fake_runner(command):
        return {
            'returncode': 0, 'stdout': '', 'stderr': '',
            'report': {'party': {'merchant_name': 'Kroger'}},
        }

    ok, prefill = manual_entry.preview_receipt_parse('/staged/scan.jpg', runner=fake_runner)
    assert ok is True
    assert prefill['merchant_name'] == 'Kroger'
    assert prefill['transaction_date'] is None
    assert prefill['total_amount'] is None


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
