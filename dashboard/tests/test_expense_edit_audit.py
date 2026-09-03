"""Persistent audit evidence for individual Edit Expense requests."""

import json

import server
from finance.expense_edit_audit import (
    IExpenseEditAuditLog,
    JsonlExpenseEditAuditLog,
)


class _RecordingAuditLog(IExpenseEditAuditLog):
    def __init__(self):
        self.calls = []

    def record(self, request, response):
        self.calls.append((request, response))


class _Namer:
    def id_for(self, category_name):
        return 140


def test_edit_expense_records_rejected_request_and_exact_error():
    audit = _RecordingAuditLog()

    result = server.edit_stored_expense(
        {
            'expense_id': 2546,
            'merchant_name': 'The Service Professor',
            'transaction_date': '08/01/2025',
            'total_amount': 14.99,
            'category_name': 'Office & Administration',
        },
        namer=_Namer(),
        audit_log=audit,
    )

    assert result['ok'] is False
    assert audit.calls == [(
        {
            'expense_id': 2546,
            'merchant_name': 'The Service Professor',
            'transaction_date': '08/01/2025',
            'total_amount': 14.99,
            'category_name': 'Office & Administration',
        },
        result,
    )]


def test_jsonl_audit_log_preserves_request_result_and_time(tmp_path):
    path = tmp_path / 'expense-edit.jsonl'
    audit = JsonlExpenseEditAuditLog(
        str(path),
        clock=lambda: '2026-08-30T16:23:37+00:00',
        id_factory=lambda: 'edit-123',
    )

    audit.record(
        {
            'expense_id': 2546,
            'merchant_name': 'The Service Professor',
            'transaction_date': '2025-08-01',
            'total_amount': 14.99,
            'category_name': 'Office & Administration',
            'ignored_secret': 'do not persist',
        },
        {
            'ok': False,
            'error': 'receipt file could not be renamed',
            'warnings': ['old receipt was left in place'],
        },
    )

    event = json.loads(path.read_text())
    assert event == {
        'action_id': 'edit-123',
        'timestamp': '2026-08-30T16:23:37+00:00',
        'status': 'failed',
        'request': {
            'expense_id': 2546,
            'merchant_name': 'The Service Professor',
            'transaction_date': '2025-08-01',
            'total_amount': 14.99,
            'category_name': 'Office & Administration',
        },
        'request_keys': [
            'category_name',
            'expense_id',
            'ignored_secret',
            'merchant_name',
            'total_amount',
            'transaction_date',
        ],
        'response': {
            'ok': False,
            'error': 'receipt file could not be renamed',
            'warnings': ['old receipt was left in place'],
        },
    }


def test_jsonl_audit_log_marks_success_and_keeps_changed_fields(tmp_path):
    path = tmp_path / 'expense-edit.jsonl'
    audit = JsonlExpenseEditAuditLog(str(path))

    audit.record(
        {'expense_id': 2546, 'transaction_date': '2025-08-01'},
        {
            'ok': True,
            'changed_fields': ['expense_date'],
            'warnings': [],
            'record': {
                'id': 2546,
                'transaction_date': '2025-08-01',
                'total_amount': 14.99,
            },
        },
    )

    event = json.loads(path.read_text())
    assert event['status'] == 'succeeded'
    assert event['response']['changed_fields'] == ['expense_date']
    assert event['response']['record']['transaction_date'] == '2025-08-01'


def test_audit_failure_never_changes_edit_response(capsys):
    class _BrokenAuditLog(IExpenseEditAuditLog):
        def record(self, request, response):
            raise OSError('disk full')

    result = server.edit_stored_expense(
        {'expense_id': 'not-a-number'}, audit_log=_BrokenAuditLog())

    assert result['ok'] is False
    assert 'expense_id' in result['error']
    assert 'expense-edit-audit' in capsys.readouterr().out
