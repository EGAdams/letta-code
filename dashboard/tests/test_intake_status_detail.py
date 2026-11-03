"""The Trainer's status detail survives the recent-report store and the scan
bridge's verdict normalization (scan_01M6D5T6XEKGP8V3WTSYY2QPB7 regression:
the detail arrived empty). Temp files only; no production pointer file."""

import json
import threading

from intake import recent_report_store as store
from scan_jobs.mazda_verdicts import DETAIL_LIMIT, IntakeMazdaVerdicts

CONV = 'conv-test-1'
AT = 1762000000.25
GATE_DETAIL = ('Dashboard red-box gate FAIL: No expense IDs were found for this intake run. | '
               'Escalation: Callback reported no parsed or persisted records.')


def _deps(tmp_path, intake):
    pointer = tmp_path / 'recent_report.json'
    pointer.write_text(json.dumps({'intake': intake}), encoding='utf-8')
    noop = lambda *a, **k: None  # noqa: E731
    return pointer, store.Collaborators(
        pointer_file=str(pointer), lock=threading.Lock(), report_file_for_url=noop,
        rol_finance_recent_reports=noop, current_execution_mode=noop,
        fold_event_into_intake=noop, recent_intake_event_router=None,
        merge_recent_intake_event=noop)


def _merge(tmp_path, intake, update):
    pointer, deps = _deps(tmp_path, intake)
    assert store.merge_recent_intake_status(deps, update) is True
    return json.loads(pointer.read_text(encoding='utf-8'))['intake']


def _intake(**overrides):
    intake = {'kind': 'scan', 'image_path': '/scans/window_scan.jpg', 'conversation_id': CONV,
              'dispatched_at': AT, 'doc_kind': 'receipt', 'status': 'dispatched'}
    intake.update(overrides)
    return intake


def _update(**overrides):
    update = {'status': 'fail', 'detail': GATE_DETAIL, 'conversation_id': CONV,
              'dispatched_at': AT, 'document_path': '/scans/window_scan.jpg',
              'report_path': '/reports/r.md'}
    update.update(overrides)
    return update


def test_gate_and_escalation_detail_survives_store_and_bridge(tmp_path):
    merged = _merge(tmp_path, _intake(), _update())
    assert merged['status_detail'] == GATE_DETAIL
    summary = IntakeMazdaVerdicts(lambda _s: merged)._from_intake(merged)
    assert summary.status == 'failed'
    assert summary.detail == GATE_DETAIL[:DETAIL_LIMIT]


def test_honest_missing_diagnostic_message_survives(tmp_path):
    honest = 'Trainer reported fail but no upstream diagnostic was recorded; see report r.md.'
    merged = _merge(tmp_path, _intake(), _update(detail=honest))
    summary = IntakeMazdaVerdicts(lambda _s: merged)._from_intake(merged)
    assert summary.detail == honest


def test_not_applicable_pass_keeps_its_reason(tmp_path):
    reason = ("Expense audit not applicable: Mazda's final classification for this intake "
              'is tax_document, it was archived, and no expenses were expected.')
    merged = _merge(tmp_path, _intake(doc_kind='tax_document'), _update(status='pass', detail=reason))
    assert merged['status'] == 'pass'
    summary = IntakeMazdaVerdicts(lambda _s: merged)._from_intake(merged)
    assert summary.status == 'completed'
    assert summary.detail == reason


def test_another_intakes_status_is_never_attached(tmp_path):
    pointer, deps = _deps(tmp_path, _intake(conversation_id='conv-other', image_path='/scans/other.jpg'))
    assert store.merge_recent_intake_status(deps, _update()) is False
    assert json.loads(pointer.read_text(encoding='utf-8'))['intake']['status'] == 'dispatched'
