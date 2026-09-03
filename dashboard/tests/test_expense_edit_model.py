"""Expense edit model and browser-serialization contract tests."""
import pytest
from pydantic import ValidationError

from finance.expense_edit_model import (
    ExpenseSearchCriteria,
    describe_changes,
    linkage_warnings,
)
from finance.expense_record_serialization import records_as_json
from tests.expense_edit_test_fakes import edit, record


@pytest.mark.parametrize('overrides', [
    {'merchant_name': '   '},
    {'transaction_date': '08/15/2026'},
    {'total_amount': 0.0},
    {'total_amount': -1.0},
    {'expense_id': 0},
])
def test_edit_refuses_values_a_fresh_entry_would_refuse(overrides):
    with pytest.raises(ValidationError):
        edit(**overrides)


def test_sub_half_cent_amount_drift_is_not_a_change():
    assert describe_changes(record(), edit(total_amount=12.342)) == ('description',)


def test_linkage_warning_is_silent_without_a_filing_key():
    assert linkage_warnings(record(id_light=''), ('amount',)) == ()


def test_records_as_json_uses_browser_contract_without_vendor_alias():
    payload = records_as_json([record()])
    assert payload == [{
        'id': 501,
        'transaction_date': '2026-08-15',
        'total_amount': 12.34,
        'description': 'Kroger',
        'id_light': 'kroger_08_15_26_12_34',
        'category_name': 'Office',
    }]
    assert 'vendor_key' not in payload[0]


@pytest.mark.parametrize('delta,expected', [
    (0.0, ()), (0.004, ()), (0.005, ('amount',)), (0.01, ('amount',)),
])
def test_amount_change_detection_at_tolerance_boundary(delta, expected):
    assert describe_changes(record(), edit(
        merchant_name='Kroger', total_amount=12.34 + delta)) == expected


def test_same_magnitude_is_not_a_change():
    assert 'amount' not in describe_changes(
        record(total_amount=12.34),
        edit(merchant_name='Kroger', total_amount=12.34))


def test_unicode_and_whitespace_merchant_names_are_normalized_safely():
    assert edit(merchant_name='Café Münster — naïve').merchant_name == (
        'Café Münster — naïve')
    assert edit(merchant_name='  Kum \t\n  Go  ').merchant_name == 'Kum Go'
    assert edit(merchant_name='🛒').merchant_name == '🛒'


@pytest.mark.parametrize('bad_date', [
    '2026-02-30', '2026-13-01', '2026-1-5',
    '2026-08-15T00:00:00', '',
])
def test_impossible_and_malformed_dates_are_rejected(bad_date):
    with pytest.raises(ValidationError):
        edit(transaction_date=bad_date)


def test_dates_are_normalized_before_change_detection():
    assert edit(transaction_date='20260815').transaction_date == '2026-08-15'
    assert describe_changes(
        record(transaction_date='2026-08-15'),
        edit(merchant_name='Kroger', transaction_date='20260815')) == ()
    assert edit(transaction_date='2024-02-29').transaction_date == '2024-02-29'


def test_search_limit_boundaries_remain_clamped():
    for value, expected in ((1, 1), (100, 100), (101, 100), (-5, 1)):
        assert ExpenseSearchCriteria(merchant='x', limit=value).limit == expected
