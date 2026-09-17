"""MySQL expense repository edit/read/delete behavior with injected fakes."""
import pytest

from finance.expense_edit_model import ExpenseNotFound, ExpenseSearchCriteria
from tests.expense_edit_test_fakes import FakeProbe, edit, repository, row


def test_edit_reports_only_actual_changes_and_commits_once():
    repo, connection = repository([row()])
    result = repo.apply_edit(edit())
    assert result.changed_fields == ('description',)
    assert connection.commits == 1


def test_edit_that_changes_nothing_writes_nothing():
    repo, connection = repository([row()])
    result = repo.apply_edit(edit(merchant_name='Kroger'))
    assert result.changed_fields == ()
    assert connection.commits == 0
    assert not any(sql.startswith('UPDATE') for sql, _ in connection.cur.executed)


@pytest.mark.parametrize('stored,expected', [(-12.34, -20.0), (12.34, 20.0), (0.0, 20.0)])
def test_edit_preserves_the_stored_amount_sign(stored, expected):
    repo, connection = repository([row(amount=stored)])
    repo.apply_edit(edit(total_amount=20.0))
    update = [params for sql, params in connection.cur.executed
              if sql.startswith('UPDATE')][0]
    assert update[2] == pytest.approx(expected)


def test_unknown_expense_never_writes():
    repo, connection = repository([])
    with pytest.raises(ExpenseNotFound):
        repo.apply_edit(edit())
    assert connection.commits == 0


def test_edit_without_receipt_warns_about_filing_key_drift():
    repo, _ = repository([row()])
    result = repo.apply_edit(edit(total_amount=99.99))
    assert 'kroger_08_15_26_12_34' in result.warnings[0]
    assert repository([row()])[0].apply_edit(edit()).warnings == ()


def test_edit_returns_corrected_record():
    repo, _ = repository([row()])
    record = repo.apply_edit(edit(category_id=243)).record
    assert record.description == 'Kroger Fuel'
    assert record.category_name == 'Rosemary'


def test_search_and_read_carry_an_existing_note():
    probe = FakeProbe(available=('id_light', 'notes'))
    repo, _ = repository(
        [row(notes='Reimbursed by Sam')], probe=probe)
    assert repo.search(ExpenseSearchCriteria(merchant='Kroger'))[0].notes == (
        'Reimbursed by Sam')
    assert repo.read(501).notes == 'Reimbursed by Sam'


def test_a_deployment_without_the_notes_column_reads_a_blank_note():
    repo, _ = repository([row()])  # FakeProbe() only exposes id_light
    assert repo.read(501).notes == ''


def test_edit_preserves_the_existing_note_unchanged():
    probe = FakeProbe(available=('id_light', 'notes'))
    repo, _ = repository(
        [row(notes='Reimbursed by Sam')], probe=probe)
    record = repo.apply_edit(edit(category_id=243)).record
    assert record.notes == 'Reimbursed by Sam'


def test_read_and_delete_commands():
    repo, connection = repository([row(amount=-12.34)])
    assert repo.read(501).total_amount == 12.34
    deletion = repo.delete(501)
    assert deletion.record.description == 'Kroger'
    assert ('DELETE FROM expenses WHERE id = %s', (501,)) in connection.cur.executed
    assert connection.commits == 1


def test_delete_unknown_expense_never_commits():
    repo, connection = repository([])
    with pytest.raises(ExpenseNotFound):
        repo.delete(501)
    assert connection.commits == 0


def test_category_and_date_changes_are_reported_precisely():
    repo, connection = repository([row()])
    assert repo.apply_edit(edit(
        merchant_name='Kroger', category_id=None)).changed_fields == ('category_id',)
    assert connection.commits == 1

    repo, _ = repository([row()])
    result = repo.apply_edit(edit(
        merchant_name='Kroger', transaction_date='2026-09-01'))
    assert result.changed_fields == ('expense_date',)
    assert 'expense_date' in result.warnings[0]


def test_date_and_amount_warning_names_both_fields():
    repo, _ = repository([row()])
    result = repo.apply_edit(edit(
        merchant_name='Kroger', transaction_date='2026-09-01',
        total_amount=99.99))
    assert len(result.warnings) == 1
    assert 'expense_date and amount' in result.warnings[0]


def test_search_on_minimal_schema_still_works():
    repo, _ = repository([row(id_light=None)])
    records = repo.search(ExpenseSearchCriteria(merchant='Kroger'))
    assert records[0].id_light == ''
