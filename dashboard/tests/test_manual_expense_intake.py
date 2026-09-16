"""Tests for the Add Expense page's HTTP-shaped orchestration.

finance.manual_entry.submit_manual_expense_entry (the subprocess call) is
faked here too -- these tests are about the boundary work: coercion,
category resolution, and building the response `record` -- not about the
real rol_finances script, which finance/manual_entry.py already tests via
its own injected `runner`.
"""
from finance import manual_expense_intake


def _deps(resolve_reporting_category=None, get_expense_edit_repository=None):
    return manual_expense_intake.Collaborators(
        resolve_reporting_category=resolve_reporting_category or (lambda name: (None, None)),
        get_expense_edit_repository=get_expense_edit_repository or (lambda: None),
    )


def test_success_reads_back_the_stored_record(monkeypatch):
    monkeypatch.setattr(
        manual_expense_intake.manual_entry, 'submit_manual_expense_entry',
        lambda entry: (True, {'report': {'expense_id': 501, 'duplicate': False}}))

    class FakeRepo:
        def read(self, expense_id):
            assert expense_id == 501
            return {'id': 501, 'description': 'Cash Tip'}

    monkeypatch.setattr(
        manual_expense_intake, 'records_as_json',
        lambda rows: [{'id': 501, 'description': 'Cash Tip', 'category_name': 'Food'}])

    deps = _deps(
        resolve_reporting_category=lambda name: (7, 'cat-food'),
        get_expense_edit_repository=lambda: FakeRepo(),
    )
    result = manual_expense_intake.submit_manual_expense_entry(deps, {
        'merchant_name': 'Cash Tip',
        'transaction_date': '2026-02-03',
        'total_amount': '5.00',
        'category_name': 'Food',
    })
    assert result['ok'] is True
    assert result['expense_id'] == 501
    assert result['duplicate'] is False
    assert result['record'] == {'id': 501, 'description': 'Cash Tip', 'category_name': 'Food'}


def test_unknown_category_is_rejected_before_any_save(monkeypatch):
    called = []
    monkeypatch.setattr(
        manual_expense_intake.manual_entry, 'submit_manual_expense_entry',
        lambda entry: called.append(entry) or (True, {'report': {}}))

    deps = _deps(resolve_reporting_category=lambda name: (None, None))
    result = manual_expense_intake.submit_manual_expense_entry(deps, {
        'merchant_name': 'Cash Tip',
        'transaction_date': '2026-02-03',
        'total_amount': '5.00',
        'category_name': 'Not A Real Category',
    })
    assert result == {'ok': False, 'error': "Unknown category: 'Not A Real Category'"}
    assert called == []


def test_bad_amount_is_rejected_before_any_save(monkeypatch):
    called = []
    monkeypatch.setattr(
        manual_expense_intake.manual_entry, 'submit_manual_expense_entry',
        lambda entry: called.append(entry) or (True, {'report': {}}))

    deps = _deps()
    result = manual_expense_intake.submit_manual_expense_entry(deps, {
        'merchant_name': 'Cash Tip',
        'transaction_date': '2026-02-03',
        'total_amount': 'not-a-number',
    })
    assert result['ok'] is False
    assert called == []


def test_store_failure_is_surfaced_not_raised(monkeypatch):
    monkeypatch.setattr(
        manual_expense_intake.manual_entry, 'submit_manual_expense_entry',
        lambda entry: (False, {'error': 'Error saving expense: boom'}))

    deps = _deps()
    result = manual_expense_intake.submit_manual_expense_entry(deps, {
        'merchant_name': 'Cash Tip',
        'transaction_date': '2026-02-03',
        'total_amount': '5.00',
    })
    assert result == {'ok': False, 'error': 'Error saving expense: boom'}


def test_no_category_still_saves_with_null_category_id(monkeypatch):
    captured = {}

    def fake_submit(entry):
        captured['entry'] = entry
        return True, {'report': {'expense_id': 9, 'duplicate': False}}

    monkeypatch.setattr(manual_expense_intake.manual_entry, 'submit_manual_expense_entry', fake_submit)
    monkeypatch.setattr(manual_expense_intake, 'records_as_json', lambda rows: [{}])

    deps = _deps(get_expense_edit_repository=lambda: type('R', (), {'read': lambda self, i: {}})())
    result = manual_expense_intake.submit_manual_expense_entry(deps, {
        'merchant_name': 'Cash Tip',
        'transaction_date': '2026-02-03',
        'total_amount': '5.00',
    })
    assert result['ok'] is True
    assert captured['entry'].category_id is None
