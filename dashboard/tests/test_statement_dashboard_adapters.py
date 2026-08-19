"""Tests for the two dashboard-side adapters the composition root injects."""
from finance.statement_dashboard_adapters import (
    CallableStatementPreflight,
    CallbackStatementIntakeRecorder,
)
from finance.statement_models import StatementRow, StatementStoreRequest, StatementStoreResponse


def _request(**overrides):
    fields = dict(
        image_path='/staged/window_scan.jpg',
        bank_name='Choice Privileges Mastercard',
        account_last4='5596',
        conversation_id='conv-9',
        transactions=[StatementRow(transaction_date='2025-05-23',
                                   description='QUALITY INNS JASPER TN',
                                   amount=-93.99)],
    )
    fields.update(overrides)
    return StatementStoreRequest(**fields)


def test_preflight_uses_the_human_override_facade_not_a_paid_classify():
    """The operator has already looked at the page via Show Image.

    Re-deriving "is this a statement" with a vision call would spend exactly the
    token MAZDA_DECISION_MODE=human_only exists to avoid.
    """
    seen = {}

    def run_preflight(image_path, facade, metadata=None, engine='auto'):
        seen.update(image_path=image_path, facade=facade, metadata=metadata,
                    engine=engine)
        return {'ok': True}

    gateway = CallableStatementPreflight(
        run_preflight, lambda path, pre: {}, lambda kind: {'doc_kind': kind})
    gateway.run('/staged/window_scan.jpg', {'bank_name': 'Wells Fargo'}, 'haiku-only')
    assert seen['image_path'] == '/staged/window_scan.jpg'
    assert seen['facade'] == {'doc_kind': 'statement'}
    assert seen['metadata'] == {'bank_name': 'Wells Fargo'}
    assert seen['engine'] == 'haiku-only'


def test_rows_come_from_the_payload_builder_not_the_complete_row_summary():
    """The preflight's top-level `transactions` drops rows it could not fully
    read -- which are exactly the rows the operator is here to repair."""
    preflight = {
        'transactions': [{'date': '2025-05-23', 'description': 'COMPLETE',
                          'amount': -1.0}],
        'statements': [{'transactions': [
            {'date': '2025-05-23', 'description': 'COMPLETE', 'amount': -1.0},
            {'date': '2025-05-24', 'description': '', 'amount': None,
             'unreadable': True},
        ]}],
    }

    def build_payload(image_path, result):
        return {'statements': [{'transactions':
                                result['statements'][0]['transactions']}]}

    gateway = CallableStatementPreflight(
        lambda *a, **k: preflight, build_payload, lambda kind: {})
    rows = gateway.rows('/staged/window_scan.jpg', preflight)
    assert len(rows) == 2


def test_recorder_emits_a_step8_shaped_event():
    events = []
    invalidated = []
    recorder = CallbackStatementIntakeRecorder(
        events.append, lambda: invalidated.append(True))
    recorder.record(_request(), StatementStoreResponse(
        ok=True, transactions_parsed=5, stored=2, duplicates=2,
        skipped_credits=1, expense_ids=[1601, 1602],
        duplicate_expense_ids=[1499]))
    assert invalidated == [True], 'stale receipt index would hide the evidence'
    assert len(events) == 1
    event = events[0]
    assert event['doc_kind'] == 'statement'
    assert event['status'] == 'complete'
    assert event['conversation_id'] == 'conv-9'
    assert event['expense_ids'] == [1601, 1602]
    assert event['duplicate_expense_ids'] == [1499]
    assert event['parsed'] == 5
    assert event['stored'] == 2
    assert '1 credit/payment skipped' in event['status_detail']


def test_recorder_works_without_a_receipt_index_to_invalidate():
    events = []
    CallbackStatementIntakeRecorder(events.append).record(
        _request(), StatementStoreResponse(ok=True, stored=1))
    assert len(events) == 1


def test_parsed_falls_back_to_the_row_count_the_operator_submitted():
    """A store that reported no count must not make the intake say "0 read"."""
    events = []
    CallbackStatementIntakeRecorder(events.append).record(
        _request(), StatementStoreResponse(ok=True, stored=1))
    assert events[0]['parsed'] == 1
