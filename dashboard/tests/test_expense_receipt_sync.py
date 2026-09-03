"""Receipt-reference synchronization through the repository boundary."""
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


def test_category_only_edit_does_not_relocate():
    relocator = FakeRelocator()
    repo, _ = repository(
        [row(receipt_url='kroger_08_15_26_12_34.jpg')],
        probe=FakeProbe(RECEIPT_SCHEMA), relocator=relocator)
    repo.apply_edit(edit(merchant_name='Kroger', category_id=243))
    assert relocator.calls == []
