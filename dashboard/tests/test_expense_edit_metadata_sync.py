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

    # Should still update receipt_metadata with new id_light
    updates = [
        (sql, params) for sql, params in connection.cur.executed
        if sql.startswith('UPDATE expenses SET')
    ]
    assert len(updates) == 1
    sql, params = updates[0]

    assert 'receipt_metadata = %s' in sql
    metadata_param = params[-2]
    updated_metadata = json.loads(metadata_param)
    assert updated_metadata['id_light'] == 'kroger_08_20_26_22_50'


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


def test_malformed_receipt_metadata_is_replaced():
    """Malformed JSON in receipt_metadata should be replaced with valid JSON."""
    probe = FakeProbe(available=('id_light', 'receipt_metadata'))
    repo, connection = repository(
        [row(
            id_light='kroger_08_15_26_12_34',
            receipt_metadata='{invalid json}',
        )],
        probe=probe,
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

    updates = [
        (sql, params) for sql, params in connection.cur.executed
        if sql.startswith('UPDATE expenses SET')
    ]
    assert len(updates) == 1
    sql, params = updates[0]

    # Should have created valid metadata with new id_light
    metadata_param = params[-2]
    updated_metadata = json.loads(metadata_param)
    assert updated_metadata['id_light'] == 'kroger_08_20_26_22_50'


# ── Tests for separate receipt_metadata table synchronization ──


def test_separate_table_sync_updates_id_light_and_raw_response():
    """When id_light changes, separate receipt_metadata table is synchronized."""
    initial_raw_response = json.dumps({
        'transaction_date': '2026-08-15',
        'total': 12.34,
        'vendor': 'Kroger',
        'other_field': 'preserved',
    })
    probe = FakeProbe(available=('id_light', 'receipt_url'))
    repo, connection = repository(
        [row(
            id_light='kroger_08_15_26_12_34',
            receipt_url='kroger_08_15_26_12_34.jpg',
        )],
        probe=probe,
        relocator=FakeRelocator(),
    )

    # Set up separate table data
    connection.separate_receipt_metadata = {
        501: {
            'expense_id': 501,
            'id_light': 'kroger_08_15_26_12_34',
            'raw_response': initial_raw_response,
        }
    }

    edit_cmd = ExpenseEdit(
        expense_id=501,
        merchant_name='Kroger',
        transaction_date='2026-08-20',
        total_amount=22.50,
        category_id=140,
    )

    result = repo.apply_edit(edit_cmd)

    # Check that separate table was queried
    metadata_queries = [
        (sql, params) for sql, params in connection.cur.executed
        if 'SELECT id_light, raw_response FROM receipt_metadata' in sql
    ]
    assert len(metadata_queries) == 1

    # Check that separate table was updated
    metadata_updates = [
        (sql, params) for sql, params in connection.cur.executed
        if 'UPDATE receipt_metadata SET id_light' in sql
    ]
    assert len(metadata_updates) == 1
    sql, params = metadata_updates[0]

    # Verify new id_light and updated raw_response
    assert params[0] == 'kroger_08_20_26_22_50'  # new id_light
    updated_raw_response = json.loads(params[1])
    assert updated_raw_response['transaction_date'] == '2026-08-20'
    assert updated_raw_response['total'] == 22.50
    assert updated_raw_response['other_field'] == 'preserved'


def test_separate_table_sync_skips_when_no_row_exists():
    """When no separate metadata row exists, sync is skipped silently."""
    probe = FakeProbe(available=('id_light',))
    repo, connection = repository(
        [row(id_light='kroger_08_15_26_12_34')],
        probe=probe,
    )

    # No separate table data
    connection.separate_receipt_metadata = {}

    edit_cmd = ExpenseEdit(
        expense_id=501,
        merchant_name='Kroger',
        transaction_date='2026-08-20',
        total_amount=22.50,
        category_id=140,
    )

    # Should not crash
    result = repo.apply_edit(edit_cmd)
    assert result.record.id_light == 'kroger_08_20_26_22_50'


def test_separate_table_sync_skips_when_id_light_mismatch():
    """When old id_light doesn't match, ownership check prevents update."""
    probe = FakeProbe(available=('id_light',))
    repo, connection = repository(
        [row(id_light='kroger_08_15_26_12_34')],
        probe=probe,
    )

    # Separate table has different id_light (doesn't match expense)
    connection.separate_receipt_metadata = {
        501: {
            'expense_id': 501,
            'id_light': 'different_id_08_15_26_99_99',
            'raw_response': json.dumps({'total': 99.99}),
        }
    }

    edit_cmd = ExpenseEdit(
        expense_id=501,
        merchant_name='Kroger',
        transaction_date='2026-08-20',
        total_amount=22.50,
        category_id=140,
    )

    result = repo.apply_edit(edit_cmd)

    # Should not have updated separate table (ownership mismatch)
    metadata_updates = [
        (sql, params) for sql, params in connection.cur.executed
        if 'UPDATE receipt_metadata SET id_light' in sql
    ]
    assert len(metadata_updates) == 0


def test_separate_table_sync_handles_malformed_raw_response():
    """Malformed raw_response JSON allows id_light update while preserving broken JSON."""
    probe = FakeProbe(available=('id_light',))
    repo, connection = repository(
        [row(id_light='kroger_08_15_26_12_34')],
        probe=probe,
    )

    # Malformed raw_response
    connection.separate_receipt_metadata = {
        501: {
            'expense_id': 501,
            'id_light': 'kroger_08_15_26_12_34',
            'raw_response': '{invalid json}',
        }
    }

    edit_cmd = ExpenseEdit(
        expense_id=501,
        merchant_name='Kroger',
        transaction_date='2026-08-20',
        total_amount=22.50,
        category_id=140,
    )

    # Should not crash
    result = repo.apply_edit(edit_cmd)

    # Should have updated only id_light (not raw_response)
    metadata_updates = [
        (sql, params) for sql, params in connection.cur.executed
        if 'UPDATE receipt_metadata SET id_light' in sql and 'raw_response' not in sql
    ]
    # With malformed JSON, it updates only id_light
    assert len(metadata_updates) == 1
    sql, params = metadata_updates[0]
    assert params[0] == 'kroger_08_20_26_22_50'


def test_separate_table_sync_rollback_on_collision():
    """When separate table update fails (e.g., unique constraint), transaction rolls back."""
    probe = FakeProbe(available=('id_light',))
    repo, connection = repository(
        [row(id_light='kroger_08_15_26_12_34')],
        probe=probe,
    )

    # Set up to trigger unique constraint violation
    connection.separate_receipt_metadata = {
        501: {
            'expense_id': 501,
            'id_light': 'kroger_08_15_26_12_34',
            'raw_response': json.dumps({'total': 12.34}),
        }
    }
    connection.fail_on_metadata_update = True  # Trigger SQL error

    edit_cmd = ExpenseEdit(
        expense_id=501,
        merchant_name='Kroger',
        transaction_date='2026-08-20',
        total_amount=22.50,
        category_id=140,
    )

    # Should raise exception
    with pytest.raises(Exception):
        repo.apply_edit(edit_cmd)

    # Verify rollback was called
    assert connection.rolled_back


def test_category_only_edit_does_not_trigger_separate_table_sync():
    """Category-only edits don't change id_light, so no separate table sync."""
    probe = FakeProbe(available=('id_light',))
    repo, connection = repository(
        [row(id_light='kroger_08_15_26_12_34')],
        probe=probe,
    )

    connection.separate_receipt_metadata = {
        501: {
            'expense_id': 501,
            'id_light': 'kroger_08_15_26_12_34',
            'raw_response': json.dumps({'total': 12.34}),
        }
    }

    # Edit only category, not date/amount
    edit_cmd = ExpenseEdit(
        expense_id=501,
        merchant_name='Kroger',
        transaction_date='2026-08-15',
        total_amount=12.34,
        category_id=999,  # Different category
    )

    result = repo.apply_edit(edit_cmd)

    # Should not have queried or updated separate table
    metadata_queries = [
        (sql, params) for sql, params in connection.cur.executed
        if 'receipt_metadata' in sql.lower()
    ]
    assert len(metadata_queries) == 0
