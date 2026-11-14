"""Regression tests for receipt_metadata.id_light synchronization on expense edits."""
import json
import pytest

from finance.expense_edit_model import ExpenseEdit
from finance.receipt_relocation import IReceiptFileRelocator, ReceiptRelocationResult
from tests.expense_edit_test_fakes import repository, row, FakeProbe


class FakeRelocator(IReceiptFileRelocator):
    """Relocator that successfully relocates files with the new id_light."""
    def __init__(self, result=None):
        self.result = result
        self.calls = []

    def relocate(self, *, receipt_url, old_id_light, new_id_light):
        self.calls.append((receipt_url, old_id_light, new_id_light))
        # If no specific result provided, build success result from the new_id_light
        if self.result is None:
            return ReceiptRelocationResult(
                relocated=True,
                new_receipt_url=f'{new_id_light}.jpg',
                new_path=f'/receipts/path/to/{new_id_light}.jpg',
            )
        return self.result


def test_edit_synchronizes_receipt_metadata_id_light_with_expense_id_light():
    """When id_light changes, receipt_metadata.id_light must change too."""
    initial_metadata = json.dumps({
        'id_light': 'kroger_08_15_26_12_34',
        'other_field': 'preserved_value',
    })
    # Schema probe that includes receipt_metadata
    probe = FakeProbe(available=('id_light', 'receipt_url', 'source_file', 'receipt_metadata'))
    repo, connection = repository(
        [row(
            id_light='kroger_08_15_26_12_34',
            receipt_url='kroger_08_15_26_12_34.jpg',
            source_file='/path/to/kroger_08_15_26_12_34.jpg',
            receipt_metadata=initial_metadata,
        )],
        probe=probe,
        relocator=FakeRelocator(),
    )

    # Edit that changes date and amount (triggers id_light recalculation)
    edit_cmd = ExpenseEdit(
        expense_id=501,
        merchant_name='Kroger',
        transaction_date='2026-08-20',
        total_amount=22.50,
        category_id=140,
    )

    result = repo.apply_edit(edit_cmd)

    # Check the new id_light was calculated
    assert result.record.id_light == 'kroger_08_20_26_22_50'

    # Find the UPDATE statement
    updates = [
        (sql, params) for sql, params in connection.cur.executed
        if sql.startswith('UPDATE expenses SET')
    ]
    assert len(updates) == 1
    sql, params = updates[0]

    # Verify receipt_metadata was included in the UPDATE
    assert 'receipt_metadata = %s' in sql

    # Find the metadata parameter
    # Parameters order: description, expense_date, amount, category_id, id_light, receipt_url, document_url, source_file, receipt_metadata, expense_id
    # receipt_metadata should be second-to-last (before expense_id)
    metadata_param = params[-2]
    updated_metadata = json.loads(metadata_param)

    # Verify the metadata.id_light was synchronized
    assert updated_metadata['id_light'] == 'kroger_08_20_26_22_50'
    # Verify other fields were preserved
    assert updated_metadata['other_field'] == 'preserved_value'


def test_edit_with_no_receipt_metadata_still_works():
    """Edits should not crash when receipt_metadata is NULL."""
    probe = FakeProbe(available=('id_light', 'receipt_url', 'source_file', 'receipt_metadata'))
    repo, connection = repository(
        [row(
            id_light='kroger_08_15_26_12_34',
            receipt_url='kroger_08_15_26_12_34.jpg',
            receipt_metadata=None,
        )],
        probe=probe,
        relocator=FakeRelocator(),
    )

    edit_cmd = ExpenseEdit(
        expense_id=501,
        merchant_name='Kroger',
        transaction_date='2026-08-20',
        total_amount=22.50,
        category_id=140,
    )

    # Should not crash
    result = repo.apply_edit(edit_cmd)

    # The row's own id_light still follows the relocated receipt...
    assert result.record.id_light == 'kroger_08_20_26_22_50'
    updates = [
        (sql, params) for sql, params in connection.cur.executed
        if sql.startswith('UPDATE expenses SET')
    ]
    assert len(updates) == 1
    sql, params = updates[0]

    # ...but metadata is only rewritten when it carries the pre-edit
    # id_light; an empty column proves no ownership and stays empty.
    assert 'receipt_metadata = %s' not in sql


def test_edit_without_id_light_change_does_not_update_metadata():
    """When id_light doesn't change, receipt_metadata is not updated."""
    initial_metadata = json.dumps({
        'id_light': 'kroger_08_15_26_12_34',
        'other_field': 'preserved',
    })
    probe = FakeProbe(available=('id_light', 'receipt_metadata'))
    repo, connection = repository(
        [row(
            id_light='kroger_08_15_26_12_34',
            receipt_metadata=initial_metadata,
        )],
        probe=probe,
    )

    # Edit that only changes description (no date/amount change)
    edit_cmd = ExpenseEdit(
        expense_id=501,
        merchant_name='Kroger Fuel',
        transaction_date='2026-08-15',
        total_amount=12.34,
        category_id=140,
    )

    result = repo.apply_edit(edit_cmd)

    updates = [
        (sql, params) for sql, params in connection.cur.executed
        if sql.startswith('UPDATE expenses SET')
    ]
    assert len(updates) == 1
    sql, params = updates[0]

    # receipt_metadata should not be in the UPDATE since id_light didn't change
    assert 'receipt_metadata' not in sql


def test_edit_on_schema_without_receipt_metadata_still_works():
    """Deployments without receipt_metadata column should not fail."""
    probe = FakeProbe(available=('id_light', 'receipt_url'))
    repo, connection = repository(
        [row(
            id_light='kroger_08_15_26_12_34',
            receipt_url='kroger_08_15_26_12_34.jpg',
        )],
        probe=probe,
        relocator=FakeRelocator(),
    )

    edit_cmd = ExpenseEdit(
        expense_id=501,
        merchant_name='Kroger',
        transaction_date='2026-08-20',
        total_amount=22.50,
        category_id=140,
    )

    # Should not crash
    result = repo.apply_edit(edit_cmd)

    # Should still update id_light
    assert result.record.id_light == 'kroger_08_20_26_22_50'

    updates = [
        (sql, params) for sql, params in connection.cur.executed
        if sql.startswith('UPDATE expenses SET')
    ]
    assert len(updates) == 1
    sql, params = updates[0]

    # receipt_metadata should not appear (column doesn't exist)
    assert 'receipt_metadata' not in sql


def test_malformed_receipt_metadata_is_left_untouched():
    """Malformed inline JSON cannot prove ownership, so it is preserved as is."""
    probe = FakeProbe(available=('id_light', 'receipt_url', 'receipt_metadata'))
    repo, connection = repository(
        [row(
            id_light=OLD_ID,
            receipt_url=f'{OLD_ID}.jpg',
            receipt_metadata='{invalid json}',
        )],
        probe=probe,
        relocator=FakeRelocator(),
    )

    # Should not crash
    result = repo.apply_edit(DATE_AMOUNT_EDIT)

    assert result.record.id_light == NEW_ID
    updates = [
        (sql, params) for sql, params in connection.cur.executed
        if sql.startswith('UPDATE expenses SET')
    ]
    assert len(updates) == 1
    sql, params = updates[0]
    assert 'receipt_metadata = %s' not in sql
    assert '{invalid json}' not in params


# ── Tests for separate receipt_metadata table synchronization ──
#
# The table's rows are handed to the shared fakes as ``receipt_metadata_rows``.
# id_light only changes when a filed receipt is actually relocated, so every
# case that expects a sync gives the row a receipt and a relocator.

OLD_ID = 'kroger_08_15_26_12_34'
NEW_ID = 'kroger_08_20_26_22_50'
DATE_AMOUNT_EDIT = ExpenseEdit(
    expense_id=501,
    merchant_name='Kroger',
    transaction_date='2026-08-20',
    total_amount=22.50,
    category_id=140,
)
RECEIPT_PROBE = FakeProbe(available=('id_light', 'receipt_url'))


def _receipt_repository(metadata_rows, **kwargs):
    return repository(
        [row(id_light=OLD_ID, receipt_url=f'{OLD_ID}.jpg')],
        probe=RECEIPT_PROBE,
        relocator=FakeRelocator(),
        receipt_metadata_rows=metadata_rows,
        **kwargs,
    )


def _metadata_statements(connection, prefix):
    return [
        (sql, params) for sql, params in connection.cur.executed
        if sql.startswith(prefix)
    ]


def test_separate_table_sync_updates_id_light_and_raw_response():
    """When id_light changes, separate receipt_metadata table is synchronized."""
    repo, connection = _receipt_repository([{
        'id_light': OLD_ID,
        'raw_response': json.dumps({
            'transaction_date': '2026-08-15',
            'total_amount': 12.34,
            'vendor': 'Kroger',
            'other_field': 'preserved',
        }),
    }])

    repo.apply_edit(DATE_AMOUNT_EDIT)

    assert len(_metadata_statements(
        connection, 'SELECT id_light, raw_response FROM receipt_metadata')) == 1
    metadata_updates = _metadata_statements(
        connection, 'UPDATE receipt_metadata SET id_light')
    assert len(metadata_updates) == 1
    sql, params = metadata_updates[0]

    assert params[0] == NEW_ID
    updated_raw_response = json.loads(params[1])
    assert updated_raw_response['transaction_date'] == '2026-08-20'
    assert updated_raw_response['total_amount'] == 22.50
    assert updated_raw_response['other_field'] == 'preserved'


def test_separate_table_sync_skips_when_no_row_exists():
    """When no separate metadata row exists, sync is skipped silently."""
    repo, connection = _receipt_repository([])

    # Should not crash
    result = repo.apply_edit(DATE_AMOUNT_EDIT)

    assert result.record.id_light == NEW_ID
    assert not _metadata_statements(connection, 'UPDATE receipt_metadata')
    assert connection.commits == 1


def test_separate_table_sync_skips_when_id_light_mismatch():
    """When old id_light doesn't match, ownership check prevents update."""
    repo, connection = _receipt_repository([{
        'id_light': 'different_id_08_15_26_99_99',
        'raw_response': json.dumps({'total_amount': 99.99}),
    }])

    repo.apply_edit(DATE_AMOUNT_EDIT)

    assert not _metadata_statements(connection, 'UPDATE receipt_metadata')


def test_separate_table_sync_handles_malformed_raw_response():
    """Malformed raw_response JSON allows id_light update while preserving broken JSON."""
    repo, connection = _receipt_repository([{
        'id_light': OLD_ID,
        'raw_response': '{invalid json}',
    }])

    # Should not crash
    repo.apply_edit(DATE_AMOUNT_EDIT)

    metadata_updates = _metadata_statements(connection, 'UPDATE receipt_metadata')
    assert len(metadata_updates) == 1
    sql, params = metadata_updates[0]
    assert 'raw_response' not in sql
    assert params[0] == NEW_ID


def test_separate_table_sync_rollback_on_collision():
    """When separate table update fails (e.g., unique constraint), transaction rolls back."""
    repo, connection = _receipt_repository(
        [{
            'id_light': OLD_ID,
            'raw_response': json.dumps({'total_amount': 12.34}),
        }],
        fail_on_metadata_update=RuntimeError('duplicate receipt_metadata.id_light'),
    )

    with pytest.raises(RuntimeError, match='duplicate receipt_metadata'):
        repo.apply_edit(DATE_AMOUNT_EDIT)

    assert connection.rollbacks == 1
    assert connection.commits == 0


def test_category_only_edit_does_not_trigger_separate_table_sync():
    """Category-only edits don't change id_light, so no separate table sync."""
    repo, connection = _receipt_repository([{
        'id_light': OLD_ID,
        'raw_response': json.dumps({'total_amount': 12.34}),
    }])

    # Edit only category, not date/amount
    edit_cmd = ExpenseEdit(
        expense_id=501,
        merchant_name='Kroger',
        transaction_date='2026-08-15',
        total_amount=12.34,
        category_id=999,  # Different category
    )

    repo.apply_edit(edit_cmd)

    # The table itself is neither read nor written (the expenses SELECT may
    # still name the inline receipt_metadata column).
    touched = [
        sql for sql, _ in connection.cur.executed
        if 'FROM receipt_metadata' in sql or sql.startswith('UPDATE receipt_metadata')
    ]
    assert touched == []
