"""Receipt-reference synchronization through the repository boundary."""
import json

import pytest

from finance.receipt_relocation import IReceiptFileRelocator, ReceiptRelocationResult
from tests.expense_edit_test_fakes import FakeProbe, edit, repository, row


class FakeRelocator(IReceiptFileRelocator):
    def __init__(self, result=None):
        self.result = result or ReceiptRelocationResult(
            relocated=True,
            new_receipt_url='kroger_08_20_26_99_99.jpg',
            new_path='/receipts/2026/august/august_20/kroger_08_20_26_99_99.jpg',
        )
        self.calls = []

    def relocate(self, *, receipt_url, old_id_light, new_id_light):
        self.calls.append((receipt_url, old_id_light, new_id_light))
        return self.result


RECEIPT_SCHEMA = ('id_light', 'receipt_url', 'document_url', 'source_file')


def test_amount_edit_relocates_receipt_and_updates_database_identity():
    relocator = FakeRelocator()
    repo, connection = repository(
        [row(receipt_url='kroger_08_15_26_12_34.jpg')],
        probe=FakeProbe(RECEIPT_SCHEMA), relocator=relocator)
    result = repo.apply_edit(edit(merchant_name='Kroger', total_amount=99.99))
    assert relocator.calls == [
        ('kroger_08_15_26_12_34.jpg', 'kroger_08_15_26_12_34',
         'kroger_08_15_26_99_99')]
    assert result.record.id_light == 'kroger_08_15_26_99_99'
    assert result.record.receipt_url == 'kroger_08_20_26_99_99.jpg'
    update = next(params for sql, params in connection.cur.executed
                  if sql.startswith('UPDATE'))
    assert 'kroger_08_15_26_99_99' in update


def test_date_edit_synchronizes_absolute_source_and_document_references():
    old_path = '/receipts/2026/august/august_15/kroger_08_15_26_12_34.jpg'
    new_path = '/receipts/2026/august/august_20/kroger_08_20_26_12_34.jpg'
    relocated = ReceiptRelocationResult(
        relocated=True,
        new_receipt_url='kroger_08_20_26_12_34.jpg',
        new_path=new_path,
    )
    repo, connection = repository(
        [row(receipt_url='kroger_08_15_26_12_34.jpg',
             document_url=old_path, source_file=old_path)],
        probe=FakeProbe(RECEIPT_SCHEMA), relocator=FakeRelocator(relocated))
    result = repo.apply_edit(edit(
        merchant_name='Kroger', transaction_date='2026-08-20'))
    assert result.record.receipt_url == 'kroger_08_20_26_12_34.jpg'
    assert result.record.document_url == new_path
    assert result.record.source_file == new_path
    update = next(params for sql, params in connection.cur.executed
                  if sql.startswith('UPDATE'))
    assert new_path in update


def test_failed_relocation_warns_without_rewriting_filing_key():
    relocator = FakeRelocator(ReceiptRelocationResult(
        warning='a naming collision at the new path'))
    repo, _ = repository(
        [row(receipt_url='kroger_08_15_26_12_34.jpg')],
        probe=FakeProbe(RECEIPT_SCHEMA), relocator=relocator)
    result = repo.apply_edit(edit(merchant_name='Kroger', total_amount=99.99))
    assert result.warnings == ('a naming collision at the new path',)
    assert result.record.id_light == 'kroger_08_15_26_12_34'


def test_date_amount_edit_synchronizes_owned_metadata_and_raw_response():
    old_id = 'kroger_08_15_26_12_34'
    metadata = {
        'id_light': old_id,
        'model_name': 'gemini',
        'unrelated': {'keep': True},
        'raw_response': json.dumps({
            'transaction_date': '2026-08-15',
            'totals': {'subtotal': 10.00, 'total_amount': 12.34},
            'merchant': {'name': 'Kroger'},
        }),
    }
    repo, connection = repository(
        [row(receipt_url=f'{old_id}.jpg', receipt_metadata=json.dumps(metadata))],
        probe=FakeProbe(RECEIPT_SCHEMA + ('receipt_metadata',)),
        relocator=FakeRelocator(ReceiptRelocationResult(
            relocated=True,
            new_receipt_url='kroger_08_20_26_99_99.jpg',
            new_path='/receipts/kroger_08_20_26_99_99.jpg')))

    repo.apply_edit(edit(transaction_date='2026-08-20', total_amount=99.99))

    sql, params = next((sql, params) for sql, params in connection.cur.executed
                       if sql.startswith('UPDATE'))
    metadata_value = params[sql.split('SET ', 1)[1].split(' WHERE')[0]
                            .split(', ').index('receipt_metadata = %s')]
    stored = json.loads(metadata_value)
    raw = json.loads(stored['raw_response'])
    assert stored['id_light'] == 'kroger_08_20_26_99_99'
    assert stored['model_name'] == 'gemini'
    assert stored['unrelated'] == {'keep': True}
    assert raw['transaction_date'] == '2026-08-20'
    assert raw['totals'] == {'subtotal': 10.0, 'total_amount': 99.99}
    assert raw['merchant'] == {'name': 'Kroger'}


def test_mismatched_metadata_identity_is_not_rewritten():
    import json

    metadata = {'id_light': 'someone_else', 'raw_response': json.dumps({
        'transaction_date': '2026-08-15', 'totals': {'total_amount': 12.34}})}
    repo, connection = repository(
        [row(receipt_url='kroger_08_15_26_12_34.jpg',
             receipt_metadata=json.dumps(metadata))],
        probe=FakeProbe(RECEIPT_SCHEMA + ('receipt_metadata',)),
        relocator=FakeRelocator())

    repo.apply_edit(edit(total_amount=99.99))

    sql, _params = next((sql, params) for sql, params in connection.cur.executed
                        if sql.startswith('UPDATE'))
    assert 'receipt_metadata = %s' not in sql


def test_category_only_edit_does_not_relocate():
    relocator = FakeRelocator()
    repo, _ = repository(
        [row(receipt_url='kroger_08_15_26_12_34.jpg')],
        probe=FakeProbe(RECEIPT_SCHEMA), relocator=relocator)
    repo.apply_edit(edit(merchant_name='Kroger', category_id=243))
    assert relocator.calls == []


def test_date_amount_edit_synchronizes_separate_metadata_table():
    old_id = 'kroger_08_15_26_12_34'
    metadata = {
        'id_light': old_id,
        'raw_response': json.dumps({
            'transaction_date': '2026-08-15',
            'totals': {'subtotal': 10.0, 'total_amount': 12.34},
            'party': {'merchant_name': 'Kroger'},
        }),
    }
    repo, connection = repository(
        [row(receipt_url=f'{old_id}.jpg')],
        probe=FakeProbe(RECEIPT_SCHEMA),
        relocator=FakeRelocator(ReceiptRelocationResult(
            relocated=True,
            new_receipt_url='kroger_08_20_26_99_99.jpg',
            new_path='/receipts/kroger_08_20_26_99_99.jpg')),
        receipt_metadata_rows=[metadata],
    )

    repo.apply_edit(edit(transaction_date='2026-08-20', total_amount=99.99))

    sql, params = next(
        (sql, params) for sql, params in connection.cur.executed
        if sql.startswith('UPDATE receipt_metadata'))
    assert sql.endswith('WHERE expense_id = %s AND id_light = %s')
    assert params[0] == 'kroger_08_20_26_99_99'
    raw = json.loads(params[1])
    assert raw['transaction_date'] == '2026-08-20'
    assert raw['totals'] == {'subtotal': 10.0, 'total_amount': 99.99}
    assert raw['party'] == {'merchant_name': 'Kroger'}
    assert params[-2:] == (501, old_id)
    assert connection.commits == 1


def test_separate_metadata_mismatch_is_not_rewritten():
    repo, connection = repository(
        [row(receipt_url='kroger_08_15_26_12_34.jpg')],
        probe=FakeProbe(RECEIPT_SCHEMA), relocator=FakeRelocator(),
        receipt_metadata_rows=[{
            'id_light': 'someone_else',
            'raw_response': json.dumps({'transaction_date': '2026-08-15'}),
        }],
    )

    repo.apply_edit(edit(total_amount=99.99))

    assert not any(sql.startswith('UPDATE receipt_metadata')
                   for sql, _ in connection.cur.executed)
    assert connection.commits == 1


def test_malformed_separate_metadata_preserves_payload_and_updates_identity():
    repo, connection = repository(
        [row(receipt_url='kroger_08_15_26_12_34.jpg')],
        probe=FakeProbe(RECEIPT_SCHEMA), relocator=FakeRelocator(),
        receipt_metadata_rows=[{
            'id_light': 'kroger_08_15_26_12_34',
            'raw_response': '["historical", "non-object"]',
        }],
    )

    repo.apply_edit(edit(total_amount=99.99))

    sql, params = next(
        (sql, params) for sql, params in connection.cur.executed
        if sql.startswith('UPDATE receipt_metadata'))
    assert 'raw_response = %s' not in sql
    assert params == ('kroger_08_15_26_99_99', 501,
                      'kroger_08_15_26_12_34')


def test_metadata_collision_rolls_back_expense_and_metadata_updates():
    collision = RuntimeError('duplicate receipt_metadata.id_light')
    repo, connection = repository(
        [row(receipt_url='kroger_08_15_26_12_34.jpg')],
        probe=FakeProbe(RECEIPT_SCHEMA), relocator=FakeRelocator(),
        receipt_metadata_rows=[{
            'id_light': 'kroger_08_15_26_12_34',
            'raw_response': json.dumps({'transaction_date': '2026-08-15'}),
        }],
        fail_on_metadata_update=collision,
    )

    with pytest.raises(RuntimeError, match='duplicate receipt_metadata'):
        repo.apply_edit(edit(total_amount=99.99))

    assert connection.commits == 0
    assert connection.rollbacks == 1
