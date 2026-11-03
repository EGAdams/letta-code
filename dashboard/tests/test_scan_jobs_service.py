"""ScanJobService: durable ids, immutable artifacts, and the bridge's refusals."""

import hashlib

import pytest

from scan_jobs.models import BridgeSettings, ScanRecord, rfc3339
from scan_jobs.repository import SqliteScanJobRepository
from scan_jobs.service import StartRefused
from tests.scan_jobs_fakes import Rig, jpeg


def _bridge_scan(rig, scanner='window', key=None, data=None):
    if data is not None:
        rig.scanner.next_bytes[scanner] = data
    record, created = rig.service.start(scanner, 'agent-bridge-worker', key)
    rig.clock.advance(61)                                 # clear the per-scanner interval
    return rig.service.get(record.scan_id), created


def test_an_overwritten_output_file_never_changes_an_earlier_scan(tmp_path):
    """The regression the whole package exists for: window_scan.jpg is
    overwritten by every scan, so a scan must never be read back through it."""
    rig = Rig(tmp_path)
    first, second = jpeg((200, 0, 0)), jpeg((0, 0, 200))
    a, _ = _bridge_scan(rig, data=first)
    b, _ = _bridge_scan(rig, data=second)
    assert a.scan_id != b.scan_id
    assert a.artifact.sha256 == hashlib.sha256(first).hexdigest()
    assert b.artifact.sha256 == hashlib.sha256(second).hexdigest()
    assert rig.service.original(a.scan_id)[1] == first
    assert rig.service.original(b.scan_id)[1] == second


def test_window_and_freezer_jobs_stay_separate(tmp_path):
    rig = Rig(tmp_path)
    w, _ = _bridge_scan(rig, 'window', data=jpeg((1, 2, 3)))
    f, _ = _bridge_scan(rig, 'freezer', data=jpeg((240, 240, 240)))
    w2, _ = _bridge_scan(rig, 'window', data=jpeg((90, 90, 9)))
    assert [w.scanner, f.scanner, w2.scanner] == ['window', 'freezer', 'window']
    assert rig.service.original(f.scan_id)[1] == jpeg((240, 240, 240))
    assert rig.service.original(w.scan_id)[1] == jpeg((1, 2, 3))
    assert f.scanner_name == 'Freezer Scanner'


def test_bridge_scans_are_off_unless_switched_on(tmp_path):
    rig = Rig(tmp_path, enabled=False)
    with pytest.raises(StartRefused) as refused:
        rig.service.start('window', 'agent-bridge-worker', None)
    assert (refused.value.code, refused.value.http) == ('bridge_scans_disabled', 403)
    assert rig.scanner.calls == []


def test_only_the_two_scanner_keys_are_accepted(tmp_path):
    rig = Rig(tmp_path)
    for bad in ('', 'Window', '../window', 'window;ls', 'printer'):
        with pytest.raises(StartRefused) as refused:
            rig.service.start(bad, 'agent-bridge-worker', None)
        assert refused.value.code == 'invalid_scanner'
    assert rig.scanner.calls == []


def test_a_retried_start_returns_the_same_scan_and_scans_once(tmp_path):
    rig = Rig(tmp_path)
    one, created_one = rig.service.start('window', 'agent-bridge-worker', 'chatgpt-req-0001')
    two, created_two = rig.service.start('window', 'agent-bridge-worker', 'chatgpt-req-0001')
    assert one.scan_id == two.scan_id
    assert (created_one, created_two) == (True, False)
    assert rig.scanner.calls == ['window']


def test_a_second_start_while_one_is_in_flight_is_refused(tmp_path):
    held = []
    rig = Rig(tmp_path, spawn=held.append)                # accepted, never run
    first, _ = rig.service.start('window', 'agent-bridge-worker', None)
    rig.settings = BridgeSettings(bridge_start_enabled=True, min_seconds_between_bridge_scans=5)
    rig.clock.advance(10)
    with pytest.raises(StartRefused) as refused:
        rig.service.start('window', 'agent-bridge-worker', None)
    assert (refused.value.code, refused.value.http, refused.value.scan_id) == ('scanner_busy', 409, first.scan_id)
    other, _ = rig.service.start('freezer', 'agent-bridge-worker', None)   # the other scanner is free
    assert other.scanner == 'freezer'
    assert rig.scanner.calls == []


def test_bridge_starts_are_rate_limited(tmp_path):
    rig = Rig(tmp_path)
    rig.service.start('window', 'agent-bridge-worker', None)
    rig.clock.advance(10)
    with pytest.raises(StartRefused) as refused:
        rig.service.start('window', 'agent-bridge-worker', None)
    assert (refused.value.code, refused.value.http) == ('rate_limited', 429)
    assert 1 <= refused.value.retry_after <= 50
    rig.clock.advance(51)
    rig.service.start('window', 'agent-bridge-worker', None)
    assert rig.scanner.calls == ['window', 'window']


def test_the_hourly_limit_counts_both_scanners(tmp_path):
    rig = Rig(tmp_path)
    rig.settings = BridgeSettings(bridge_start_enabled=True, max_bridge_scans_per_hour=2)
    _bridge_scan(rig, 'window')
    _bridge_scan(rig, 'freezer')
    with pytest.raises(StartRefused) as refused:
        rig.service.start('window', 'agent-bridge-worker', None)
    assert refused.value.code == 'rate_limited'


@pytest.mark.parametrize('result, status, code', [
    ({'status': 'offline', 'error': 'Scanner not found'}, 'failed', 'device_offline'),
    ({'status': 'busy', 'error': 'in use'}, 'failed', 'device_busy'),
    ({'status': 'error', 'error': 'Scan timed out after 120s (scanner not responding).'}, 'timed_out', 'timeout'),
    ({'status': 'error', 'error': 'no output', 'empty_output': True}, 'failed', 'empty_output'),
    ({'ok': False, 'status': 'intake_busy', 'error': 'still filing'}, 'failed', 'intake_busy'),
    ({'status': 'error', 'error': 'boom'}, 'failed', 'scanner_error'),
])
def test_hardware_failures_map_to_a_terminal_status(tmp_path, result, status, code):
    rig = Rig(tmp_path)
    rig.scanner.next_result['window'] = result
    record, _ = _bridge_scan(rig)
    assert (record.status, record.error_code, record.artifact) == (status, code, None)
    assert record.mazda.status == 'not_requested'


def test_a_stale_output_file_is_never_taken_as_the_new_scan(tmp_path):
    rig = Rig(tmp_path)
    _bridge_scan(rig, data=jpeg((5, 5, 5)))
    rig.scanner.touch = False                            # "ready", but the file is the old one
    record, _ = _bridge_scan(rig)
    assert (record.status, record.error_code) == ('failed', 'stale_output')


def test_the_dashboard_button_keeps_its_legacy_result_and_gains_a_scan_id(tmp_path):
    rig = Rig(tmp_path, enabled=False)                    # the flag only governs the bridge
    result = rig.service.run_recorded('window')
    assert result['status'] == 'ready' and result['ok'] is True and result['image_url'] == '/scan/window'
    record = rig.service.get(result['scan_id'])
    assert (record.source, record.status) == ('dashboard', 'captured')


def test_the_dashboard_button_passes_unknown_keys_and_odd_results_straight_through(tmp_path):
    rig = Rig(tmp_path)
    rig.scanner.next_result['printer'] = {'status': 'not_configured'}
    assert rig.service.run_recorded('printer') == {'status': 'not_configured'}
    rig.scanner.next_result['window'] = 'not a dict'
    assert rig.service.run_recorded('window') == 'not a dict'


def test_reading_status_never_scans(tmp_path):
    rig = Rig(tmp_path)
    record, _ = _bridge_scan(rig)
    calls = list(rig.scanner.calls)
    for _ in range(5):
        rig.service.get(record.scan_id)
        rig.service.list_recent(10, None)
        rig.service.mazda(record.scan_id)
    assert rig.scanner.calls == calls


def test_a_restart_marks_unfinished_jobs_interrupted(tmp_path):
    rig = Rig(tmp_path, spawn=lambda fn: None)            # the process "dies" before the scan runs
    record, _ = rig.service.start('window', 'agent-bridge-worker', None)
    reopened = SqliteScanJobRepository(tmp_path / 'jobs' / 'scan_jobs.sqlite3', clock_ns=rig.clock)
    assert reopened.interrupt_active() == 1
    after = reopened.get(record.scan_id)
    assert (after.status, after.error_code) == ('interrupted', 'interrupted')
    assert reopened.interrupt_active() == 0


def test_list_recent_pages_newest_first(tmp_path):
    rig = Rig(tmp_path)
    ids = [_bridge_scan(rig, k)[0].scan_id for k in ('window', 'freezer', 'window')]
    page, cursor = rig.service.list_recent(2, None)
    rest, end = rig.service.list_recent(2, cursor)
    assert [r.scan_id for r in page + rest] == ids[::-1] and end is None


def test_the_audit_trail_names_the_requester_and_never_the_content(tmp_path):
    rig = Rig(tmp_path)
    record, _ = _bridge_scan(rig, data=jpeg((7, 7, 7)))
    rows = rig.repo.audit_rows(record.scan_id)
    assert ('agent-bridge-worker', 'start_accepted', 'window') in rows
    assert all(len(detail) < 60 for _, _, detail in rows)


def test_public_view_hides_mazda_detail_without_the_verdict_scope():
    now = rfc3339(0)
    record = ScanRecord.model_validate_json(
        '{"scan_id": "scan_01ARZ3NDEKTSV4RRFFQ69G5FAV", "scanner": "window", "scanner_name": "W", '
        '"source": "bridge", "requester": "x", "status": "captured", "created_at": "%s", "updated_at": "%s", '
        '"mazda": {"status": "completed", "vendor": "Consumers Energy"}}' % (now, now))
    assert record.public()['mazda'] == {'status': 'completed'}
    assert record.public(include_mazda_detail=True)['mazda']['vendor'] == 'Consumers Energy'
