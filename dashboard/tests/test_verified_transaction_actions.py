"""The fixed sales-tax rule and the two stored-row commands."""

from finance.expense_edit_model import ExpenseDeletion
from finance.expense_edit_repository import records_as_json
from finance.sales_tax import tax_on, with_sales_tax
import server


def _record(amount=12.34):
    from finance.expense_edit_model import ExpenseRecord
    return ExpenseRecord(
        id=501, transaction_date='2026-08-15', total_amount=amount,
        description='Kroger', id_light='kroger_08_15_26_12_34',
        category_id=140, category_name='Office')


class _Repo:
    def __init__(self, record=None):
        self.record = record or _record()
        self.deleted = []
        self.edits = []

    def read(self, expense_id):
        assert expense_id == self.record.id
        return self.record

    def delete(self, expense_id):
        self.deleted.append(expense_id)
        return ExpenseDeletion(record=self.record)

    def apply_edit(self, edit):
        from finance.expense_edit_model import ExpenseEditResult, ExpenseRecord
        self.edits.append(edit)
        changed = ExpenseRecord(
            id=self.record.id, transaction_date=edit.transaction_date,
            total_amount=edit.total_amount, description=edit.merchant_name,
            id_light=self.record.id_light, category_id=edit.category_id,
            category_name=self.record.category_name)
        return ExpenseEditResult(record=changed, changed_fields=('amount',))


def test_michigan_tax_rounds_the_tax_to_cents_before_adding():
    assert str(tax_on('28.73')) == '1.72'
    assert str(with_sales_tax('28.73')) == '30.45'


def test_delete_endpoint_returns_the_removed_row(monkeypatch):
    repo = _Repo()
    monkeypatch.setattr(server, '_invalidate_receipt_index', lambda: None)
    result = server.delete_stored_expense({'expense_id': '501'}, repository=repo)
    assert result == {
        'ok': True,
        'record': records_as_json([repo.record])[0],
        'line_item_ids': [],
    }
    assert repo.deleted == [501]


def test_add_tax_always_uses_six_percent_even_if_body_supplies_a_rate():
    repo = _Repo(_record(28.73))
    result = server.add_sales_tax_to_expense(
        {'expense_id': 501, 'rate': 0.50}, repository=repo)
    assert result['ok'] is True
    assert result['record']['total_amount'] == 30.45
    assert result['tax_added'] == 1.72
    assert result['rate'] == 0.06
    assert repo.edits[0].total_amount == 30.45


def test_row_commands_reject_non_positive_ids():
    assert server.delete_stored_expense({'expense_id': 0}, repository=_Repo()) == {
        'ok': False, 'error': 'expense_id must be a positive row id'}
    assert server.add_sales_tax_to_expense({'expense_id': -1}, repository=_Repo()) == {
        'ok': False, 'error': 'expense_id must be a positive row id'}
