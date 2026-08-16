"""Tests for finance/receipt_filename.py -- pure receipt-filename parsing.

Companion to test_archive_path.py: archive_path builds this filename shape
from a date/amount, this module recovers the date/amount from an existing
filename. Same production example (kroger_08_15_26_12_34.jpg, expense id
2158) is used here so the two stay provably consistent with each other.
"""
from finance import receipt_filename


def test_parses_real_production_filename():
    result = receipt_filename.parse_receipt_filename('kroger_08_15_26_12_34.jpg')
    assert result is not None
    assert result.expense_date.isoformat() == '2026-08-15'
    assert result.amount == '12.34'
    assert result.index_key() == ('2026-08-15', '12.34')


def test_parses_regardless_of_vendor_prefix_shape():
    result = receipt_filename.parse_receipt_filename(
        'gardner_clinic_05_12_25_117_00.jpg')
    assert result.index_key() == ('2025-05-12', '117.00')


def test_multi_digit_dollar_amount():
    result = receipt_filename.parse_receipt_filename('acme_01_02_25_1234_56.png')
    assert result.index_key() == ('2025-01-02', '1234.56')


def test_returns_none_for_unrelated_filename():
    assert receipt_filename.parse_receipt_filename('receipt_url_list.txt') is None
    assert receipt_filename.parse_receipt_filename('IMG_20250815.jpg') is None
    assert receipt_filename.parse_receipt_filename('') is None


def test_returns_none_for_impossible_calendar_date():
    # Month 13, day 32 -- old regex-only code would have silently built a
    # bogus '2025-13-32' key; this must reject it instead.
    assert receipt_filename.parse_receipt_filename('vendor_13_32_25_10_00.jpg') is None


def test_returns_none_for_missing_extension():
    assert receipt_filename.parse_receipt_filename('kroger_08_15_26_12_34') is None
