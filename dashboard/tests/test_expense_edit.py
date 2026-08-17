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
    assert clauses == ["(description LIKE %s ESCAPE '!' "
                       "OR id_light LIKE %s ESCAPE '!')"]
    assert params == ['%Kroger%', '%Kroger%']


def test_merchant_search_drops_vendor_key_on_a_narrower_schema():
    clauses, params = _where_clauses(
        ExpenseSearchCriteria(merchant='Kroger'), has_vendor_key=False)
    assert clauses == ["description LIKE %s ESCAPE '!'"]
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


# ==========================================================================
# Edge cases
# ==========================================================================

# --- LIKE metacharacters ---------------------------------------------------
#
# `%` and `_` are LIKE pattern syntax, not text. Binding the value stops
# injection but not this: an unescaped search for "50%" became `%50%%`, which
# matches anything merely starting with 50, and "a_b" matched "axb".

def test_percent_in_a_merchant_search_is_matched_literally():
    from finance.expense_edit_repository import escape_like
    clauses, params = _where_clauses(
        ExpenseSearchCriteria(merchant='50%'), has_vendor_key=False)
    assert params == ['%50!%%']
    assert "ESCAPE '!'" in clauses[0]
    assert escape_like('50%') == '50!%'


def test_underscore_in_a_merchant_search_is_matched_literally():
    clauses, params = _where_clauses(
        ExpenseSearchCriteria(merchant='a_b'), has_vendor_key=False)
    assert params == ['%a!_b%']


def test_the_escape_character_itself_is_escaped_first():
    from finance.expense_edit_repository import escape_like
    # Otherwise escaping would corrupt a merchant name containing '!'.
    assert escape_like('Wow!') == 'Wow!!'
    assert escape_like('!%') == '!!!%'


def test_both_columns_get_their_own_escape_clause():
    clauses, params = _where_clauses(
        ExpenseSearchCriteria(merchant='50%'), has_vendor_key=True)
    assert clauses[0].count("ESCAPE '!'") == 2
    assert params == ['%50!%%', '%50!%%']


def test_an_ordinary_merchant_is_unchanged_by_escaping():
    from finance.expense_edit_repository import escape_like
    assert escape_like('Kroger') == 'Kroger'


# --- Amount tolerance boundaries -------------------------------------------

@pytest.mark.parametrize('delta,expected', [
    (0.0,    ()),            # identical
    (0.004,  ()),            # inside the half-cent tolerance
    (0.005,  ('amount',)),   # exactly at it -- counts as a change
    (0.01,   ('amount',)),   # a whole cent
])
def test_amount_change_detection_at_the_tolerance_boundary(delta, expected):
    assert describe_changes(_record(), _edit(
        merchant_name='Kroger', total_amount=12.34 + delta)) == expected


def test_a_sign_flip_of_the_same_magnitude_is_not_an_amount_change():
    # ExpenseRecord always carries the absolute value, so an edit resubmitting
    # the same magnitude must not read as a change just because the row is
    # stored negative.
    assert 'amount' not in describe_changes(
        _record(total_amount=12.34), _edit(merchant_name='Kroger',
                                           total_amount=12.34))


# --- Unicode / odd text ----------------------------------------------------

def test_a_unicode_merchant_name_survives_the_round_trip():
    edit = _edit(merchant_name='Café Münster — naïve')
    assert edit.merchant_name == 'Café Münster — naïve'


def test_merchant_whitespace_is_collapsed_not_just_trimmed():
    assert _edit(merchant_name='  Kum \t\n  Go  ').merchant_name == 'Kum Go'


def test_an_emoji_only_merchant_name_is_kept_not_treated_as_empty():
    assert _edit(merchant_name='🛒').merchant_name == '🛒'


# --- Date validity ---------------------------------------------------------

@pytest.mark.parametrize('bad_date', [
    '2026-02-30',   # well-formed but not a real day
    '2026-13-01',   # month 13
    '2026-1-5',     # not zero-padded
    '2026-08-15T00:00:00',
    '',
])
def test_impossible_and_malformed_dates_are_rejected(bad_date):
    with pytest.raises(ValidationError):
        _edit(transaction_date=bad_date)


def test_iso_basic_format_is_normalised_to_the_canonical_spelling():
    # date.fromisoformat accepts "20260815"; storing it verbatim meant two
    # spellings of one day compared unequal, so describe_changes reported a
    # date edit that changed nothing.
    assert _edit(transaction_date='20260815').transaction_date == '2026-08-15'


def test_a_normalised_date_is_not_reported_as_a_change():
    assert describe_changes(
        _record(transaction_date='2026-08-15'),
        _edit(merchant_name='Kroger', transaction_date='20260815')) == ()


def test_a_real_leap_day_is_accepted():
    assert _edit(transaction_date='2024-02-29').transaction_date == '2024-02-29'


# --- Search criteria boundaries --------------------------------------------

def test_a_single_day_range_is_valid():
    c = ExpenseSearchCriteria(date_from='2026-08-15', date_to='2026-08-15')
    assert c.date_from == c.date_to


@pytest.mark.parametrize('limit,expected', [
    (1, 1), (100, 100), (101, 100), (-5, 1),
])
def test_limit_clamping_at_the_boundaries(limit, expected):
    assert ExpenseSearchCriteria(merchant='x', limit=limit).limit == expected


def test_a_merchant_of_only_whitespace_is_not_a_criterion():
    # It collapses to empty, so on its own it must fail the "at least one
    # criterion" rule rather than searching the whole table for ''.
    with pytest.raises(ValidationError):
        ExpenseSearchCriteria(merchant='   \t  ')


def test_a_very_small_positive_amount_is_allowed():
    assert ExpenseSearchCriteria(amount=0.01).amount == pytest.approx(0.01)


def test_strict_mode_rejects_an_amount_that_arrives_as_a_string():
    # The HTTP boundary coerces; the model itself must not.
    with pytest.raises(ValidationError):
        ExpenseSearchCriteria(amount='12.34')


def test_unknown_fields_are_rejected_rather_than_silently_ignored():
    with pytest.raises(ValidationError):
        ExpenseSearchCriteria(merchant='x', typo_field='oops')


# --- Repository edge cases -------------------------------------------------

def test_a_row_whose_description_is_null_reads_as_empty_not_none():
    repo, _ = _repo([_row(description=None, id_light=None)])
    record = repo.search(ExpenseSearchCriteria(merchant='x'))[0]
    assert record.description == ''
    assert record.vendor_key == ''


def test_a_row_with_no_category_gets_an_empty_category_name():
    repo, _ = _repo([_row(category_id=None)])
    record = repo.search(ExpenseSearchCriteria(merchant='x'))[0]
    assert record.category_id is None
    assert record.category_name == ''


def test_search_on_a_table_with_no_id_light_column_still_works():
    repo, _ = _repo([_row(id_light=None)], probe=_FakeProbe(available=()))
    records = repo.search(ExpenseSearchCriteria(merchant='Kroger'))
    assert records[0].vendor_key == ''


def test_clearing_a_category_is_a_real_change():
    repo, connection = _repo([_row()])
    result = repo.apply_edit(_edit(merchant_name='Kroger', category_id=None))
    assert result.changed_fields == ('category_id',)
    assert connection.commits == 1


def test_an_edit_moving_only_the_date_warns_about_the_vendor_key():
    repo, _ = _repo([_row()])
    result = repo.apply_edit(
        _edit(merchant_name='Kroger', transaction_date='2026-09-01'))
    assert result.changed_fields == ('expense_date',)
    assert result.warnings and 'expense_date' in result.warnings[0]


def test_moving_both_date_and_amount_names_both_in_one_warning():
    repo, _ = _repo([_row()])
    result = repo.apply_edit(_edit(
        merchant_name='Kroger', transaction_date='2026-09-01',
        total_amount=99.99))
    assert len(result.warnings) == 1
    assert 'expense_date and amount' in result.warnings[0]


def test_an_edit_of_a_zero_amount_row_still_keeps_a_positive_sign():
    # 0.0 is falsy; the sign check must not treat it as "negative".
    repo, connection = _repo([_row(amount=0.0)])
    repo.apply_edit(_edit(merchant_name='Kroger', total_amount=5.0))
    update = [p for sql, p in connection.cur.executed if sql.startswith('UPDATE')]
    assert update[0][2] == pytest.approx(5.0)
