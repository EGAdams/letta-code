"""Tests for the Scanner screen's statement-review queue.

The store subprocess is injected (`runner=`) so these run offline — the real
finance DB and venv live on the other box.
"""
import json
import os

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
    assert 'Please enter the expense number.' in message
    assert 'guess' not in message


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


def test_list_reviews_empty_when_no_directory(tmp_path):
    assert statement_review.list_reviews(archive_root=str(tmp_path)) == []


def test_apply_amounts_fills_the_row_and_keeps_the_charge_sign():
    transactions = statement_review.apply_amounts(_packet(), {'3': '4.50'})
    assert transactions[3]['amount'] == -4.5
    assert 'unreadable' not in transactions[3]
    # untouched rows are unchanged
    assert transactions[0]['amount'] == -5.0


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
