"""Real producer contract, isolated durable envelopes, and malformed boundaries."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from monitoring import adw_supervisor as sup
from monitoring.supervisor_sources import FileLedgerReader, PostOfficeLedgerReader
from monitoring.task_timing import duration_seconds, epoch


@pytest.mark.parametrize('value', [True, -1, float('nan'), float('inf'), 'junk'])
def test_invalid_duration_does_not_claim_a_healthy_age(value):
    assert duration_seconds(value) is None


def test_naive_timestamps_are_unknown_and_real_display_durations_are_supported():
    assert epoch('2026-11-06T13:00:00') is None
    assert duration_seconds('2h 01m') == 7260
    assert duration_seconds('3m 04s') == 184


def test_file_source_rejects_bad_rows_and_duplicate_task_ids(tmp_path):
    path = tmp_path / 'ledger.json'
    for rows in ([{'id': 'x', 'status': 'queued', 'attempts': 'a'}],
                 [{'id': 'x', 'status': 'queued'}, {'id': 'x', 'status': 'running'}]):
        path.write_text(json.dumps(rows))
        result = FileLedgerReader(path).read(path.stat().st_mtime)
        assert result.tasks is None and result.error


def test_direct_post_office_reader_keeps_work_visible_without_a_worker(tmp_path, monkeypatch):
    package = Path.home() / 'agent_blocks' / 'lancedb_memory'
    if not package.is_dir():
        pytest.skip('real producer is outside the read-only workspace jail; run this integration check on the host')
    monkeypatch.syspath_prepend(str(package))
    from agent_bridge_worker import activity_snapshot as producer
    from agent_comms.models import Envelope, MessageKind, TaskStatus
    mailbox = tmp_path / 'mailboxes'
    folder = mailbox / 'claude-sonnet' / 'inbox' / 'new'
    folder.mkdir(parents=True)
    made = datetime(2026, 11, 6, 13, tzinfo=timezone.utc)
    request = Envelope(id='local-1', kind=MessageKind.REQUEST, sender='chatgpt-bridge',
                       recipient='claude-sonnet', task_type='inspect', text='PRIVATE PROMPT',
                       correlation_id='local-1', status=TaskStatus.QUEUED,
                       context={'bridge_task_id': 't_direct', 'workdir': '/w'},
                       created_at=made, enqueued_at=made)
    envelope = folder / 'local-1.json'
    envelope.write_text(request.model_dump_json())
    workspace = tmp_path / 'workspaces.json'
    workspace.write_text('{"workspaces":{}}')
    monkeypatch.setattr(producer, 'MAILBOX_ROOT', mailbox)
    monkeypatch.setattr(producer, 'WORKSPACES_FILE', workspace)
    monkeypatch.setattr(producer, 'NOTES_LOG', tmp_path / 'absent-notes.jsonl')
    monkeypatch.setattr(sup, '_worker_diagnostic', lambda tasks, now: {'status': 'offline'})
    monkeypatch.setattr(sup.model_registry, 'registry', lambda: [])
    before = envelope.read_bytes()
    result = sup.run_cycle(ledger_path=tmp_path / 'missing-worker-snapshot.json',
                           state_path=tmp_path / 'state.json', thresholds=sup.Thresholds(),
                           now=made.timestamp() + 601, reader=PostOfficeLedgerReader(package))
    assert result['tasks']['t_direct']['tier'] == 'diagnose'
    assert result['source'] == 'local-post-office'
    assert result['coverage_complete'] is False
    assert result['worker_diagnostic']['status'] == 'offline'
    assert 'PRIVATE PROMPT' not in json.dumps(result)
    assert envelope.read_bytes() == before


def test_unreadable_cycle_preserves_last_escalation_without_advancing_it(tmp_path, monkeypatch):
    monkeypatch.setattr(sup, '_worker_diagnostic', lambda tasks, now: None)
    monkeypatch.setattr(sup.model_registry, 'registry', lambda: [])
    path, state = tmp_path / 'ledger.json', tmp_path / 'state.json'
    path.write_text('[{"id":"x","status":"queued","queue_age":601}]')
    os.utime(path, (1000, 1000))
    before = sup.run_cycle(ledger_path=path, state_path=state, thresholds=sup.Thresholds(), now=1000)
    after = sup.run_cycle(ledger_path=path, state_path=state, thresholds=sup.Thresholds(), now=1061)
    assert after['ok'] is False and after['ledger_stale'] is True
    assert after['tasks'] == before['tasks']


def test_state_may_not_overwrite_the_source_ledger(tmp_path):
    path = tmp_path / 'ledger.json'
    path.write_text('[]')
    with pytest.raises(ValueError, match='state path must differ'):
        sup.run_cycle(ledger_path=path, state_path=path, thresholds=sup.Thresholds(), now=0)
    assert path.read_text() == '[]'


def test_skipping_directly_to_incident_retains_second_opinion_candidates():
    state = sup.evaluate_task({'id':'x', 'status':'queued', 'queue_age':1801},
                              sup.TaskEscalationState(), sup.Thresholds(), now=2000,
                              candidates=('reviewer',))
    assert state.events[0]['second_opinion_models'] == ['reviewer']


def test_no_progress_event_is_bounded_and_replaying_a_cycle_is_idempotent():
    task = {'id':'x', 'status':'queued', 'queue_age':150}
    state = sup.TaskEscalationState()
    for now in range(50):
        state = sup.evaluate_task(task, state, sup.Thresholds(), now=now)
    assert state.no_progress_cycles == 2
    assert len(state.events) == 2
    assert sup.evaluate_task(task, state, sup.Thresholds(), now=49) == state


@pytest.mark.parametrize('values', [(0, 1, 2, 3), (1, 1, 2, 3), (1, 2, 3, float('nan'))])
def test_invalid_thresholds_are_rejected(values):
    with pytest.raises(ValueError):
        sup.Thresholds(*values)


def test_gateway_head_is_added_and_ages_while_unclaimed():
    from monitoring.supervisor_contracts import LedgerObservation
    from monitoring.supervisor_sources import GatewayAwareLedgerReader

    class Local:
        def read(self, now):
            return LedgerObservation(tasks=[], source="local-post-office", updated_at=now)

    head = ["t_" + "a" * 24]
    reader = GatewayAwareLedgerReader(Local(), lambda: head[0])
    first = reader.read(1000.0)
    assert [t.id for t in first.tasks] == head and first.coverage_complete
    later = reader.read(1700.0)
    assert later.tasks[0].queued_at == 1000.0   # age keeps growing, first-seen is kept
    head[0] = None
    assert reader.read(1800.0).tasks == [] and reader._first_seen == {}


def test_unreachable_gateway_is_reported_not_an_empty_queue():
    from monitoring.supervisor_contracts import LedgerObservation
    from monitoring.supervisor_sources import GatewayAwareLedgerReader

    class Local:
        def read(self, now):
            return LedgerObservation(tasks=[], source="local-post-office", updated_at=now)

    def down():
        raise OSError("no route")

    seen = GatewayAwareLedgerReader(Local(), down).read(1.0)
    assert not seen.coverage_complete and "could not be checked" in seen.coverage_reason
