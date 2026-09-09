"""Composition-root wiring for stored-expense report synchronization."""
import server
from finance.expense_edit_model import ExpenseEditResult, ExpenseRecord


def _record(**overrides):
    values = dict(
        id=2547,
        transaction_date='2025-08-19',
        total_amount=80.24,
        description='AT&T',
        id_light='at_t_08_19_25_80_24',
        category_id=140,
        category_name='Office & Administration',
    )
    values.update(overrides)
    return ExpenseRecord(**values)


class _Repository:
    def read(self, _expense_id):
        return _record()

    def apply_edit(self, _edit):
        return ExpenseEditResult(
            record=_record(
                transaction_date='2025-08-25',
                id_light='at_t_08_25_25_80_24'),
            changed_fields=('expense_date',),
        )


class _Namer:
    def id_for(self, _name):
        return 140


def test_default_report_sync_scans_the_real_bank_statement_root(monkeypatch):
    roots = []
    image_calls = []

    class _Synchronizer:
        def __init__(self, root):
            roots.append(root)

        def synchronize(self, _before, _after):
            return 0

    monkeypatch.setattr(server, 'StaticExpenseReportSynchronizer', _Synchronizer)
    monkeypatch.setattr(server, '_invalidate_receipt_index', lambda: None)
    monkeypatch.setattr(
        server, '_synchronize_recent_report_image',
        lambda *args, **kwargs: image_calls.append((args, kwargs)) or {})

    result = server._edit_stored_expense({
        'expense_id': 2547,
        'merchant_name': 'AT&T',
        'transaction_date': '2025-08-25',
        'total_amount': 80.24,
        'category_name': 'Office & Administration',
    }, repository=_Repository(), namer=_Namer())

    assert result['ok'] is True
    assert roots == [server.ROL_FINANCES_REPORTS_PARENT]
    assert result['warnings'] == []
    assert image_calls[0][1]['replace_identity'] is True


def test_amount_only_edit_preserves_recent_report_vendor_and_date(monkeypatch):
    image_calls = []

    class AmountRepository(_Repository):
        def read(self, _expense_id):
            return _record()

        def apply_edit(self, _edit):
            return ExpenseEditResult(
                record=_record(total_amount=99.99,
                               id_light='at_t_08_19_25_99_99'),
                changed_fields=('amount',),
            )

    monkeypatch.setattr(server, '_invalidate_receipt_index', lambda: None)
    monkeypatch.setattr(
        server, '_synchronize_recent_report_image',
        lambda *args, **kwargs: image_calls.append((args, kwargs)) or {})

    result = server._edit_stored_expense({
        'expense_id': 2547,
        'merchant_name': 'AT&T',
        'transaction_date': '2025-08-19',
        'total_amount': 99.99,
        'category_name': 'Office & Administration',
    }, repository=AmountRepository(), namer=_Namer(),
       report_sync=type('Sync', (), {'synchronize': lambda *_args: 0})())

    assert result['ok'] is True
    assert image_calls[0][1]['replace_identity'] is False
