"""Expense search model, SQL strategy, and HTTP-boundary tests."""
import pytest
from pydantic import ValidationError

from finance.expense_edit_model import MAX_SEARCH_RESULTS, ExpenseEdit, ExpenseSearchCriteria
from finance.expense_search import (
    escape_like,
    readable_validation_error,
    search_criteria_from_request,
    where_clauses,
)
from tests.expense_edit_test_fakes import FakeProbe, repository, row


def test_empty_search_is_rejected_rather_than_returning_everything():
    with pytest.raises(ValidationError):
        ExpenseSearchCriteria()


def test_reversed_or_non_iso_date_range_is_rejected():
    with pytest.raises(ValidationError):
        ExpenseSearchCriteria(date_from='2026-08-20', date_to='2026-08-01')
    with pytest.raises(ValidationError):
        ExpenseSearchCriteria(date_from='08/20/2026')


def test_limit_is_clamped_to_supported_range():
    assert ExpenseSearchCriteria(merchant='Kroger', limit=10_000).limit == MAX_SEARCH_RESULTS
    assert ExpenseSearchCriteria(merchant='Kroger', limit=0).limit == 1


def test_search_merchant_and_amount_validation():
    assert ExpenseSearchCriteria(merchant='  Kum   Go ').merchant == 'Kum Go'
    with pytest.raises(ValidationError):
        ExpenseSearchCriteria(amount=0.0)


def test_request_boundary_coerces_amount_and_blank_dates():
    criteria = search_criteria_from_request(
        {'amount': '12.34', 'date_from': '  ', 'date_to': ''})
    assert criteria.amount == pytest.approx(12.34)
    assert criteria.date_from is None and criteria.date_to is None
    with pytest.raises(ValueError):
        search_criteria_from_request({'amount': 'twelve'})


def test_merchant_search_uses_filing_key_only_when_available():
    criteria = ExpenseSearchCriteria(merchant='Kroger')
    clauses, params = where_clauses(criteria, has_vendor_key=True)
    assert clauses == ["(description LIKE %s ESCAPE '!' OR id_light LIKE %s ESCAPE '!')"]
    assert params == ['%Kroger%', '%Kroger%']
    clauses, params = where_clauses(criteria, has_vendor_key=False)
    assert clauses == ["description LIKE %s ESCAPE '!'"]
    assert params == ['%Kroger%']


def test_every_criterion_is_parameterized_never_interpolated():
    criteria = ExpenseSearchCriteria(
        merchant="O'Brien", date_from='2026-08-01',
        date_to='2026-08-31', amount=12.34)
    clauses, params = where_clauses(criteria, has_vendor_key=True)
    assert len(clauses) == 4
    assert all('%s' in clause for clause in clauses)
    assert "O'Brien" not in ' '.join(clauses)
    assert "%O'Brien%" in params


def test_search_repository_maps_rows_and_limit():
    repo, connection = repository([row()])
    records = repo.search(ExpenseSearchCriteria(merchant='Kroger', limit=7))
    assert records[0].category_name == 'Office'
    assert records[0].id_light == 'kroger_08_15_26_12_34'
    assert connection.cur.executed[-1][1][-1] == 7


def test_search_reports_negative_amount_as_positive():
    repo, _ = repository([row(amount=-12.34)])
    assert repo.search(ExpenseSearchCriteria(merchant='Kroger'))[0].total_amount == 12.34


def test_validation_errors_are_one_operator_sentence():
    with pytest.raises(ValidationError) as caught:
        ExpenseSearchCriteria()
    assert readable_validation_error(caught.value) == (
        'enter a merchant, a date range, or an amount to search')
    with pytest.raises(ValidationError) as caught:
        ExpenseEdit(expense_id=1, merchant_name='  ',
                    transaction_date='2026-08-15', total_amount=1.0)
    assert readable_validation_error(caught.value) == (
        'merchant_name: merchant_name is required')
    assert readable_validation_error(ValueError('bad amount')) == 'bad amount'


def test_like_metacharacters_are_matched_literally():
    clauses, params = where_clauses(
        ExpenseSearchCriteria(merchant='50%'), has_vendor_key=False)
    assert params == ['%50!%%']
    assert "ESCAPE '!'" in clauses[0]
    assert escape_like('a_b') == 'a!_b'
    assert escape_like('Wow!') == 'Wow!!'
    assert escape_like('!%') == '!!!%'
    assert escape_like('Kroger') == 'Kroger'


def test_both_search_columns_get_their_own_escape_clause():
    clauses, params = where_clauses(
        ExpenseSearchCriteria(merchant='50%'), has_vendor_key=True)
    assert clauses[0].count("ESCAPE '!'") == 2
    assert params == ['%50!%%', '%50!%%']


def test_search_criteria_boundaries():
    one_day = ExpenseSearchCriteria(date_from='2026-08-15', date_to='2026-08-15')
    assert one_day.date_from == one_day.date_to
    assert ExpenseSearchCriteria(amount=0.01).amount == 0.01
    with pytest.raises(ValidationError):
        ExpenseSearchCriteria(merchant='   \t  ')
    with pytest.raises(ValidationError):
        ExpenseSearchCriteria(amount='12.34')
    with pytest.raises(ValidationError):
        ExpenseSearchCriteria(merchant='x', typo_field='oops')


def test_narrow_schema_and_null_values_still_map():
    repo, _ = repository(
        [row(description=None, id_light=None, category_id=None)],
        probe=FakeProbe(available=()))
    record = repo.search(ExpenseSearchCriteria(merchant='x'))[0]
    assert record.description == ''
    assert record.id_light == ''
    assert record.category_name == ''


@pytest.mark.parametrize('criteria', [
    ExpenseSearchCriteria(merchant='Kroger'),
    ExpenseSearchCriteria(amount=12.34),
    ExpenseSearchCriteria(date_from='2026-08-01'),
    ExpenseSearchCriteria(date_from='2026-08-01', date_to='2026-08-31'),
    ExpenseSearchCriteria(merchant='K', date_from='2026-08-01',
                          date_to='2026-08-31', amount=12.34),
])
@pytest.mark.parametrize('has_vendor_key', [True, False])
def test_placeholder_count_matches_bound_values(criteria, has_vendor_key):
    clauses, params = where_clauses(criteria, has_vendor_key)
    assert ' '.join(clauses).count('%s') == len(params)


def test_amount_tolerance_is_bound_not_inlined():
    _clauses, params = where_clauses(
        ExpenseSearchCriteria(amount=12.34), has_vendor_key=False)
    assert params == [12.34, 0.005]
