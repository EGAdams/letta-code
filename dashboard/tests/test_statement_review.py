"""Tests for the Scanner screen's statement-review queue.

The store subprocess is injected (`runner=`) so these run offline — the real
finance DB and venv live on the other box.
"""
import json
import os
import types

import pytest

import statement_review


def _packet(**overrides):
    packet = {
        'source_file': '/scans/scan.jpg',
        'quarantined_at': '20260722-180000',
        'reason': 'statement requires every transaction row complete',
        'bank_name': 'Chase',
        'account_last4': '5783',
        'statement_total': 17.00,
        'missing_fields': ['transactions', 'amount'],
        'needs_workbook_entry': False,
        'workbook_ambiguous_last4': [],
        'transactions': [
            {'date': '2025-01-04', 'description': 'STORE A', 'amount': -5.0},
            {'date': '2025-01-05', 'description': 'STORE B', 'amount': -3.0},
            {'date': '2025-01-06', 'description': 'STORE C', 'amount': -4.5},
            {'date': '2025-01-07', 'description': 'SMUDGED', 'amount': None,
             'unreadable': True},
        ],
        'row_errors': [{
            'index': 3, 'missing': ['amount'],
            'date': '2025-01-07', 'description': 'SMUDGED',
            'suggested_amount': 4.5,
        }],
        'archive_root': '/archive',
        'env_path': '/env/.env',
    }
    packet.update(overrides)
    return packet


def _write(tmp_path, packet, name='20260722-180000_scan.jpg.json'):
    review = tmp_path / statement_review.NEEDS_REVIEW_DIRNAME
    review.mkdir(parents=True, exist_ok=True)
    (review / name).write_text(json.dumps(packet))
    (review / name[: -len('.json')]).write_bytes(b'scan bytes')
    return name


def test_amount_message_uses_egs_phrasing_and_offers_the_guess():
    message = statement_review.review_message(_packet())
    assert "I can't read the expense for SMUDGED on 2025-01-07." in message
    assert 'My guess is $4.50.' in message
    assert 'enter a different number' in message


def test_amount_message_asks_plainly_when_no_guess_is_possible():
    packet = _packet(statement_total=None)
    packet['row_errors'][0]['suggested_amount'] = None
    message = statement_review.review_message(packet)
    assert 'Please enter the expense amount.' in message
    assert 'guess' not in message


def test_date_message_asks_for_the_date_not_an_expense_number():
    packet = _packet(statement_total=None)
    packet['row_errors'][0] = {
        'index': 3,
        'missing': ['date'],
        'date': None,
        'description': 'MICROSOFT 365',
    }
    message = statement_review.review_message(packet)
    assert 'date is unreadable' in message
    assert 'enter the transaction date' in message
    assert 'expense number' not in message


def test_workbook_message_asks_for_a_row_then_ok():
    message = statement_review.review_message(
        _packet(needs_workbook_entry=True, bank_name='Bank Of Nowhere'))
    assert 'Bank Of Nowhere' in message
    assert 'add a row' in message
    assert 'press OK' in message


def test_workbook_message_names_the_candidates_when_ambiguous():
    message = statement_review.review_message(_packet(
        needs_workbook_entry=True, bank_name='American Express',
        workbook_ambiguous_last4=['1006', '5004']))
    assert '1006, 5004' in message
    assert "can't tell which one" in message


def test_list_reviews_reads_sidecars(tmp_path):
    _write(tmp_path, _packet())
    reviews = statement_review.list_reviews(archive_root=str(tmp_path))

    assert len(reviews) == 1
    item = reviews[0]
    assert item['kind'] == 'amounts'
    assert item['rows'][0]['suggested_amount'] == 4.5
    assert item['rows'][0]['description'] == 'SMUDGED'
    assert item['document_path'].endswith('20260722-180000_scan.jpg')
    assert item['document_url'].startswith('/api/statement-review-document?id=')
    assert item['document_context']['transactions'][3]['description'] == 'SMUDGED'


def test_list_reviews_empty_when_no_directory(tmp_path):
    assert statement_review.list_reviews(archive_root=str(tmp_path)) == []


def test_review_document_path_serves_only_the_queued_sibling(tmp_path):
    name = _write(tmp_path, _packet())
    expected = (
        tmp_path / statement_review.NEEDS_REVIEW_DIRNAME
        / name[:-len('.json')]
    )

    assert statement_review.review_document_path(
        name, archive_root=str(tmp_path)) == str(expected)
    assert statement_review.review_document_path(
        '../../etc/passwd.json', archive_root=str(tmp_path)) == ''
    assert statement_review.review_document_path(
        'missing.jpg.json', archive_root=str(tmp_path)) == ''


def test_apply_amounts_fills_the_row_and_keeps_the_charge_sign():
    transactions = statement_review.apply_amounts(_packet(), {'3': '4.50'})
    assert transactions[3]['amount'] == -4.5
    assert 'unreadable' not in transactions[3]
    # untouched rows are unchanged
    assert transactions[0]['amount'] == -5.0


def test_apply_corrections_fills_a_missing_date():
    packet = _packet()
    packet['transactions'][3].update(date=None, amount=-106.99)
    packet['row_errors'][0] = {
        'index': 3, 'missing': ['date'], 'date': None,
        'description': 'MICROSOFT 365',
    }

    transactions = statement_review.apply_corrections(
        packet, {'3': {'date': '2025-09-15'}})

    assert transactions[3]['date'] == '2025-09-15'
    assert transactions[3]['amount'] == -106.99
    assert 'unreadable' not in transactions[3]


def test_apply_corrections_rejects_an_invalid_date():
    with pytest.raises(ValueError, match='invalid date'):
        statement_review.apply_corrections(
            _packet(), {'3': {'date': '09/15'}})


def test_apply_amounts_rejects_a_bad_index_or_value():
    with pytest.raises(ValueError):
        statement_review.apply_amounts(_packet(), {'99': '4.50'})
    with pytest.raises(ValueError):
        statement_review.apply_amounts(_packet(), {'3': 'not a number'})


def test_resolve_success_runs_store_and_clears_the_queue(tmp_path):
    name = _write(tmp_path, _packet())
    seen = {}

    def runner(command):
        seen['command'] = command
        payload = json.load(open(command[command.index('-f') + 1]))
        seen['transactions'] = payload['transactions']
        return {'returncode': 0, 'stderr': '', 'report': {'ok': True, 'stored': 4}}

    ok, payload = statement_review.resolve_review(
        name, amounts={'3': 4.5}, archive_root=str(tmp_path), runner=runner)

    assert ok is True
    assert payload['report']['stored'] == 4
    # the human's amount reached the store script
    assert seen['transactions'][3]['amount'] == -4.5
    # queue cleared: both sidecar and parked image are gone
    review = tmp_path / statement_review.NEEDS_REVIEW_DIRNAME
    assert not (review / name).exists()
    assert not (review / name[: -len('.json')]).exists()
    assert statement_review.list_reviews(archive_root=str(tmp_path)) == []


def test_resolve_success_clears_retry_packets_for_the_same_source(tmp_path):
    first = _write(tmp_path, _packet(), name='20260722-180000_scan.jpg.json')
    second = _write(tmp_path, _packet(), name='20260722-181000_scan.jpg.json')

    ok, _payload = statement_review.resolve_review(
        second,
        amounts={'3': 4.5},
        archive_root=str(tmp_path),
        runner=lambda _command: {
            'returncode': 0, 'stderr': '',
            'report': {'ok': True, 'stored': 4},
        },
    )

    assert ok is True
    review = tmp_path / statement_review.NEEDS_REVIEW_DIRNAME
    assert not (review / first).exists()
    assert not (review / second).exists()
    assert statement_review.list_reviews(archive_root=str(tmp_path)) == []


def test_resolve_accepts_field_corrections(tmp_path):
    packet = _packet()
    packet['transactions'][3].update(date=None, amount=-106.99)
    packet['row_errors'][0] = {
        'index': 3, 'missing': ['date'], 'date': None,
        'description': 'MICROSOFT 365',
    }
    name = _write(tmp_path, packet)
    seen = {}

    def runner(command):
        parsed = json.load(open(command[command.index('-f') + 1]))
        seen['row'] = parsed['transactions'][3]
        return {'returncode': 0, 'stderr': '', 'report': {'ok': True, 'stored': 4}}

    ok, _payload = statement_review.resolve_review(
        name,
        corrections={'3': {'date': '2025-09-15'}},
        archive_root=str(tmp_path),
        runner=runner,
    )

    assert ok is True
    assert seen['row']['date'] == '2025-09-15'


def test_resolve_applies_handwritten_categories_before_clearing(tmp_path):
    name = _write(tmp_path, _packet())
    seen = {}

    def annotations(command):
        seen['command'] = command
        return {
            'returncode': 0, 'stderr': '',
            'report': {'ok': True, 'applied': [{'expense_id': 1541}]},
        }

    ok, payload = statement_review.resolve_review(
        name,
        amounts={'3': 4.5},
        archive_root=str(tmp_path),
        runner=lambda _command: {
            'returncode': 0, 'stderr': '',
            'report': {
                'ok': True,
                'stored': 1,
                'expense_ids': [1541],
                'duplicate_expense_ids': [],
            },
        },
        annotation_runner=annotations,
    )

    assert ok is True
    assert '--expense-ids' in seen['command']
    assert '1541' in seen['command']
    assert payload['report']['annotations']['applied'][0]['expense_id'] == 1541


def test_resolve_keeps_review_when_annotation_step_fails(tmp_path):
    name = _write(tmp_path, _packet())

    ok, payload = statement_review.resolve_review(
        name,
        amounts={'3': 4.5},
        archive_root=str(tmp_path),
        runner=lambda _command: {
            'returncode': 0, 'stderr': '',
            'report': {'ok': True, 'stored': 1, 'expense_ids': [1541]},
        },
        annotation_runner=lambda _command: {
            'returncode': 1, 'stderr': '',
            'report': {'ok': False, 'problems': ['vision unavailable']},
        },
    )

    assert ok is False
    assert 'vision unavailable' in payload['error']
    assert len(statement_review.list_reviews(archive_root=str(tmp_path))) == 1


def test_resolve_failure_keeps_the_item_queued_so_the_dialog_returns(tmp_path):
    """EG: 'If Mazda does not find it, the OK Dialog should pop up again.'"""
    name = _write(tmp_path, _packet(needs_workbook_entry=True))

    def runner(_command):
        return {'returncode': 2, 'stderr': '',
                'report': {'ok': False, 'error': 'still no workbook row'}}

    ok, payload = statement_review.resolve_review(
        name, archive_root=str(tmp_path), runner=runner)

    assert ok is False
    assert 'still no workbook row' in payload['error']
    assert payload['item']['kind'] == 'workbook'
    # still queued
    assert len(statement_review.list_reviews(archive_root=str(tmp_path))) == 1


def test_resolve_rejects_a_path_traversal_id(tmp_path):
    ok, payload = statement_review.resolve_review(
        '../../etc/passwd', archive_root=str(tmp_path))
    assert ok is False
    assert 'no pending review' in payload['error']


def test_run_store_extracts_json_after_dependency_diagnostic(monkeypatch):
    completed = types.SimpleNamespace(
        returncode=0,
        stdout=(
            'No vendor_key found for: MICROSOFT in '
            'VendorCategoryStore.resolve_vendor_key().\n'
            '{"ok": true, "stored": 1, "expense_ids": [1541]}\n'
        ),
        stderr='',
    )
    monkeypatch.setattr(statement_review.subprocess, 'run', lambda *a, **k: completed)

    result = statement_review._run_store(['python', 'store.py'])

    assert result['returncode'] == 0
    assert result['report']['ok'] is True
    assert result['report']['expense_ids'] == [1541]
