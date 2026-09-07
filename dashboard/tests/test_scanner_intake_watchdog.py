"""scanner_intake_watchdog_health: catches a Trainer run that went dark.

See health/scanner_intake_watchdog.py's module docstring for the incident
this was built from — a Window Scanner intake stayed 'processing' with a
Trainer summoned and no report, no callback, and no live process, invisible
until a manual scan timed out with nothing to show for it.
"""
from __future__ import annotations

import json
import time

from health import scanner_intake_watchdog as watchdog


def _write_pointer(path, scanner_intakes):
    path.write_text(json.dumps({'scanner_intakes': scanner_intakes}))


def _intake(**overrides):
    base = {
        'status': 'processing',
        'trainer_dispatched': True,
        'dispatched_at': time.time() - watchdog.STUCK_AFTER_SECONDS - 60,
        'conversation_id': 'conv-abc123',
        'status_detail': 'Trainer summoned: callback reported no parsed or persisted records',
    }
    base.update(overrides)
    return base


def _patch_paths(monkeypatch, tmp_path):
    pointer_path = tmp_path / 'recent_report.json'
    reports_dir = tmp_path / 'reports'
    reports_dir.mkdir()
    monkeypatch.setattr(watchdog, 'RECENT_REPORT_PATH', str(pointer_path))
    monkeypatch.setattr(watchdog, 'TRAINER_REPORTS_DIR', str(reports_dir))
    return pointer_path, reports_dir


def test_no_pointer_file_is_healthy(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    result = watchdog.scanner_intake_watchdog_health()
    assert result == {'ok': True, 'text': 'no scanner intakes recorded yet'}


def test_a_fresh_processing_intake_is_not_stuck_yet(monkeypatch, tmp_path):
    pointer_path, _ = _patch_paths(monkeypatch, tmp_path)
    _write_pointer(pointer_path, {
        'Window Scanner': _intake(dispatched_at=time.time() - 60),
    })
    result = watchdog.scanner_intake_watchdog_health()
    assert result == {'ok': True, 'text': 'no stuck scanner intakes'}


def test_a_completed_intake_is_ignored_regardless_of_age(monkeypatch, tmp_path):
    pointer_path, _ = _patch_paths(monkeypatch, tmp_path)
    _write_pointer(pointer_path, {
        'Window Scanner': _intake(status='complete'),
    })
    result = watchdog.scanner_intake_watchdog_health()
    assert result['ok'] is True


def test_a_stuck_intake_with_no_report_goes_red(monkeypatch, tmp_path):
    pointer_path, _ = _patch_paths(monkeypatch, tmp_path)
    _write_pointer(pointer_path, {'Window Scanner': _intake()})
    result = watchdog.scanner_intake_watchdog_health()
    assert result['ok'] is False
    assert result['hard'] is True
    assert 'Window Scanner' in result['text']
    assert 'conv-abc123' in result['text']


def test_a_stuck_intake_with_a_matching_report_is_not_flagged(monkeypatch, tmp_path):
    pointer_path, reports_dir = _patch_paths(monkeypatch, tmp_path)
    dispatched_at = time.time() - watchdog.STUCK_AFTER_SECONDS - 60
    _write_pointer(pointer_path, {
        'Window Scanner': _intake(dispatched_at=dispatched_at),
    })
    dispatch_second = int(dispatched_at)
    (reports_dir / f'20260907-000000_Window_Scanner_d{dispatch_second}.md').write_text(
        '# Mazda Trainer Report\n')
    result = watchdog.scanner_intake_watchdog_health()
    assert result == {'ok': True, 'text': 'no stuck scanner intakes'}


def test_a_stuck_intake_matched_only_by_conversation_id_is_not_flagged(monkeypatch, tmp_path):
    pointer_path, reports_dir = _patch_paths(monkeypatch, tmp_path)
    _write_pointer(pointer_path, {'Window Scanner': _intake()})
    (reports_dir / 'some_other_name.md').write_text(
        'Conversation: `conv-abc123`\nVerdict: FAIL\n')
    result = watchdog.scanner_intake_watchdog_health()
    assert result['ok'] is True


def test_an_intake_never_dispatched_to_trainer_is_ignored(monkeypatch, tmp_path):
    pointer_path, _ = _patch_paths(monkeypatch, tmp_path)
    _write_pointer(pointer_path, {
        'Window Scanner': _intake(trainer_dispatched=False),
    })
    result = watchdog.scanner_intake_watchdog_health()
    assert result['ok'] is True


def test_a_corrupt_pointer_file_is_reported_not_raised(monkeypatch, tmp_path):
    pointer_path, _ = _patch_paths(monkeypatch, tmp_path)
    pointer_path.write_text('{not json')
    result = watchdog.scanner_intake_watchdog_health()
    assert result['ok'] is False
    assert 'cannot read' in result['text']
