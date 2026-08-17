"""Tests for the Edit Expense search/correct boundary.

The database is injected (a fake connection/cursor), so these run offline --
the real finance DB lives on the other box, same posture as
test_manual_entry.py's injected subprocess runner.
"""
import pytest
from pydantic import ValidationError

from finance.expense_edit_model import (
    MAX_SEARCH_RESULTS,
    ExpenseEdit,
    ExpenseNotFound,
    ExpenseRecord,
    ExpenseSearchCriteria,
    describe_changes,
    linkage_warnings,
)
from finance.expense_edit_repository import (
    ICategoryNamer,
    MySqlExpenseRecordRepository,
    _where_clauses,
    records_as_json,
    search_criteria_from_request,
)
from finance.expense_schema import ExpenseSchema, IExpenseSchemaProbe


# --------------------------------------------------------------------------
# Test doubles
# --------------------------------------------------------------------------

class _FakeNamer(ICategoryNamer):
    NAMES = {140: 'Office', 243: 'Rosemary'}

    def name_for(self, category_id):
        return self.NAMES.get(category_id, '')

    def id_for(self, category_name):
        name = (category_name or '').strip()
        if not name:
            return None
        for cid, label in self.NAMES.items():
            if label == name:
                return cid
        raise ValueError(f'Unknown category: {name!r}')


class _FakeProbe(IExpenseSchemaProbe):
    def __init__(self, available=('id_light',)):
        self._available = frozenset(available)

    def read(self, cur, candidates):
        return ExpenseSchema(available=self._available)


class _FakeCursor:
    def __init__(self, rows):
        self._rows = list(rows)
        self.executed = []
        self._result = []

    def execute(self, sql, params=()):
        self.executed.append((' '.join(sql.split()), tuple(params)))
        if sql.lstrip().upper().startswith('UPDATE'):
            self._result = []
            return
        self._result = list(self._rows)

    def fetchall(self):
        return list(self._result)

    def fetchone(self):
        return self._result[0] if self._result else None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeConnection:
    def __init__(self, rows):
        self.cur = _FakeCursor(rows)
        self.commits = 0

    def cursor(self):
        return self.cur

    def commit(self):
        self.commits += 1

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _row(**overrides):
    row = {
        'id': 501,
        'expense_date': '2026-08-15',
        'amount': 12.34,
        'description': 'Kroger',
        'category_id': 140,
        'id_light': 'kroger_08_15_26_12_34',
    }
    row.update(overrides)
    return row


def _repo(rows, probe=None):
    connection = _FakeConnection(rows)
    repo = MySqlExpenseRecordRepository(
        lambda: connection, _FakeNamer(), schema_probe=probe or _FakeProbe())
    return repo, connection


# --------------------------------------------------------------------------
# ExpenseSearchCriteria
# --------------------------------------------------------------------------

def test_empty_search_is_rejected_rather_than_returning_everything():
    with pytest.raises(ValidationError):
        ExpenseSearchCriteria()


def test_reversed_date_range_is_rejected():
    with pytest.raises(ValidationError):
        ExpenseSearchCriteria(date_from='2026-08-20', date_to='2026-08-01')


def test_non_iso_date_is_rejected():
    with pytest.raises(ValidationError):
        ExpenseSearchCriteria(date_from='08/20/2026')


def test_limit_is_clamped_to_the_maximum():
    criteria = ExpenseSearchCriteria(merchant='Kroger', limit=10_000)
    assert criteria.limit == MAX_SEARCH_RESULTS


def test_limit_of_zero_falls_back_to_one_not_unlimited():
    assert ExpenseSearchCriteria(merchant='Kroger', limit=0).limit == 1


def test_merchant_whitespace_is_collapsed():
    assert ExpenseSearchCriteria(merchant='  Kum   Go ').merchant == 'Kum Go'


def test_non_positive_search_amount_is_rejected():
    with pytest.raises(ValidationError):
        ExpenseSearchCriteria(amount=0.0)


# --------------------------------------------------------------------------
# search_criteria_from_request: the untrusted-HTTP-shape boundary
# --------------------------------------------------------------------------

def test_request_coerces_a_string_amount_before_strict_pydantic():
    criteria = search_criteria_from_request({'amount': '12.34'})
    assert criteria.amount == pytest.approx(12.34)


def test_request_rejects_a_non_numeric_amount():
    with pytest.raises(ValueError):
        search_criteria_from_request({'amount': 'twelve'})


def test_request_treats_blank_dates_as_absent():
    criteria = search_criteria_from_request(
        {'merchant': 'Kroger', 'date_from': '  ', 'date_to': ''})
    assert criteria.date_from is None and criteria.date_to is None


# --------------------------------------------------------------------------
# _where_clauses: the SQL the search builds
# --------------------------------------------------------------------------

def test_merchant_search_covers_vendor_key_when_the_column_exists():
    clauses, params = _where_clauses(
        ExpenseSearchCriteria(merchant='Kroger'), has_vendor_key=True)
    assert clauses == ['(description LIKE %s OR id_light LIKE %s)']
    assert params == ['%Kroger%', '%Kroger%']


def test_merchant_search_drops_vendor_key_on_a_narrower_schema():
    clauses, params = _where_clauses(
        ExpenseSearchCriteria(merchant='Kroger'), has_vendor_key=False)
    assert clauses == ['description LIKE %s']
    assert params == ['%Kroger%']


def test_every_criterion_is_parameterized_never_interpolated():
    criteria = ExpenseSearchCriteria(
        merchant="O'Brien", date_from='2026-08-01',
        date_to='2026-08-31', amount=12.34)
    clauses, params = _where_clauses(criteria, has_vendor_key=True)
    assert len(clauses) == 4
    assert all('%s' in clause for clause in clauses)
    assert "O'Brien" not in ' '.join(clauses)
    assert "%O'Brien%" in params


# --------------------------------------------------------------------------
# MySqlExpenseRecordRepository.search
# --------------------------------------------------------------------------

def test_search_returns_records_with_resolved_category_names():
    repo, _ = _repo([_row()])
    records = repo.search(ExpenseSearchCriteria(merchant='Kroger'))
    assert [r.id for r in records] == [501]
    assert records[0].category_name == 'Office'
    assert records[0].vendor_key == 'kroger_08_15_26_12_34'


def test_search_reports_a_negative_stored_amount_as_positive():
    repo, _ = _repo([_row(amount=-12.34)])
    records = repo.search(ExpenseSearchCriteria(merchant='Kroger'))
    assert records[0].total_amount == pytest.approx(12.34)


def test_search_passes_the_limit_as_the_last_bind_param():
    repo, connection = _repo([_row()])
    repo.search(ExpenseSearchCriteria(merchant='Kroger', limit=7))
    sql, params = connection.cur.executed[-1]
    assert 'LIMIT %s' in sql
    assert params[-1] == 7


# --------------------------------------------------------------------------
# MySqlExpenseRecordRepository.apply_edit
# --------------------------------------------------------------------------

def _edit(**overrides):
    fields = dict(
        expense_id=501,
        merchant_name='Kroger Fuel',
        transaction_date='2026-08-15',
        total_amount=12.34,
        category_id=140,
    )
    fields.update(overrides)
    return ExpenseEdit(**fields)


def test_edit_reports_only_the_fields_that_actually_changed():
    repo, connection = _repo([_row()])
    result = repo.apply_edit(_edit())
    assert result.changed_fields == ('description',)
    assert connection.commits == 1


def test_edit_that_changes_nothing_writes_nothing():
    repo, connection = _repo([_row()])
    result = repo.apply_edit(_edit(merchant_name='Kroger'))
    assert result.changed_fields == ()
    assert connection.commits == 0
    assert not any(sql.startswith('UPDATE')
                   for sql, _ in connection.cur.executed)


def test_edit_keeps_a_negative_rows_sign():
    repo, connection = _repo([_row(amount=-12.34)])
    repo.apply_edit(_edit(total_amount=20.00))
    update = [p for sql, p in connection.cur.executed if sql.startswith('UPDATE')]
    assert update and update[0][2] == pytest.approx(-20.00)


def test_edit_keeps_a_positive_rows_sign():
    repo, connection = _repo([_row(amount=12.34)])
    repo.apply_edit(_edit(total_amount=20.00))
    update = [p for sql, p in connection.cur.executed if sql.startswith('UPDATE')]
    assert update and update[0][2] == pytest.approx(20.00)


def test_edit_of_an_unknown_id_raises_rather_than_writing():
    repo, connection = _repo([])
    with pytest.raises(ExpenseNotFound):
        repo.apply_edit(_edit())
    assert connection.commits == 0


def test_edit_warns_that_a_moved_amount_desyncs_the_vendor_key():
    repo, _ = _repo([_row()])
    result = repo.apply_edit(_edit(total_amount=99.99))
    assert result.warnings
    assert 'kroger_08_15_26_12_34' in result.warnings[0]


def test_a_description_only_edit_raises_no_linkage_warning():
    repo, _ = _repo([_row()])
    assert repo.apply_edit(_edit()).warnings == ()


def test_edit_returns_the_corrected_record():
    repo, _ = _repo([_row()])
    record = repo.apply_edit(_edit(category_id=243)).record
    assert record.description == 'Kroger Fuel'
    assert record.category_name == 'Rosemary'


# --------------------------------------------------------------------------
# ExpenseEdit inherits the shared field rules
# --------------------------------------------------------------------------

@pytest.mark.parametrize('overrides', [
    {'merchant_name': '   '},
    {'transaction_date': '08/15/2026'},
    {'total_amount': 0.0},
    {'total_amount': -1.0},
    {'expense_id': 0},
])
def test_edit_refuses_what_a_fresh_manual_entry_would_refuse(overrides):
    with pytest.raises(ValidationError):
        _edit(**overrides)


# --------------------------------------------------------------------------
# Pure helpers
# --------------------------------------------------------------------------

def _record(**overrides):
    fields = dict(id=501, transaction_date='2026-08-15', total_amount=12.34,
                  description='Kroger', vendor_key='kroger_08_15_26_12_34',
                  category_id=140, category_name='Office')
    fields.update(overrides)
    return ExpenseRecord(**fields)


def test_sub_half_cent_amount_drift_is_not_a_change():
    assert describe_changes(_record(), _edit(total_amount=12.342)) == (
        'description',)


def test_linkage_warning_is_silent_for_a_row_with_no_vendor_key():
    assert linkage_warnings(_record(vendor_key=''), ('amount',)) == ()


def test_records_as_json_uses_the_snake_case_names_the_browser_reads():
    payload = records_as_json([_record()])
    assert payload == [{
        'id': 501,
        'transaction_date': '2026-08-15',
        'total_amount': 12.34,
        'description': 'Kroger',
        'vendor_key': 'kroger_08_15_26_12_34',
        'category_name': 'Office',
    }]


# --------------------------------------------------------------------------
# readable_validation_error
# --------------------------------------------------------------------------

def test_validation_errors_read_as_one_operator_sentence():
    from finance.expense_edit_repository import readable_validation_error
    with pytest.raises(ValidationError) as caught:
        ExpenseSearchCriteria()
    message = readable_validation_error(caught.value)
    assert message == 'enter a merchant, a date range, or an amount to search'
    assert 'pydantic.dev' not in message


def test_field_validation_errors_name_the_offending_field():
    from finance.expense_edit_repository import readable_validation_error
    with pytest.raises(ValidationError) as caught:
        ExpenseEdit(expense_id=1, merchant_name='  ',
                    transaction_date='2026-08-15', total_amount=1.0)
    assert readable_validation_error(caught.value) == (
        'merchant_name: merchant_name is required')


def test_a_plain_exception_falls_back_to_its_own_message():
    from finance.expense_edit_repository import readable_validation_error
    assert readable_validation_error(ValueError('amount must be a number')) == (
        'amount must be a number')
