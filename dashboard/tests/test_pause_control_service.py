"""PauseControlService: durable intent, fail-closed pausability, idempotency,
priority ordering, restart recovery and transition logging.

The control layer does not itself know whether a task_id is "queued" or
"running" in the StarTrekBridge ledger -- that ledger is outside this
workspace (docs/bridge-pause-resume.md). It treats every task_id the same
way, so the two task_ids below named queued-task-1 / running-task-1 are
only there to show both kinds of task are accepted identically; which one
is currently queued vs running is not something this service can see.
"""

from __future__ import annotations

import pytest

from pause_control.repository import ControlRequestNotFound, InvalidTransition
from pause_control.service import ControlRefused
from tests.pause_control_fakes import Rig


# -- pause / resume lifecycle ----------------------------------------------------
def test_pause_then_resume_then_pause_again_is_a_clean_cycle(tmp_path):
    rig = Rig(tmp_path, pausable=frozenset({'queued-task-1'}))
    paused, created = rig.service.request_pause('queued-task-1', 'eg')
    assert (paused.status, created) == ('pause_requested', True)

    resumed, created = rig.service.request_resume('queued-task-1', 'eg')
    assert (resumed.status, created) == ('resume_requested', True)

    # A second pause after the resume request is a fresh cycle, not a duplicate
    # of the first (which is still only "resume_requested", not yet resolved).
    again, created = rig.service.request_pause('queued-task-1', 'eg')
    assert (again.request_id != paused.request_id, created) == (True, True)


def test_running_task_can_be_pause_requested_the_same_way(tmp_path):
    rig = Rig(tmp_path, pausable=frozenset({'running-task-1'}))
    record, created = rig.service.request_pause('running-task-1', 'eg')
    assert (record.status, created) == ('pause_requested', True)


def test_resume_without_an_open_pause_is_refused(tmp_path):
    rig = Rig(tmp_path, pausable=frozenset({'queued-task-1'}))
    with pytest.raises(ControlRefused) as refused:
        rig.service.request_resume('queued-task-1', 'eg')
    assert (refused.value.code, refused.value.http) == ('no_pause_in_progress', 409)


def test_acknowledge_moves_pause_requested_to_paused_and_logs_it(tmp_path):
    rig = Rig(tmp_path, pausable=frozenset({'queued-task-1'}))
    record, _ = rig.service.request_pause('queued-task-1', 'eg')
    acked = rig.service.acknowledge(record.request_id, 'paused', 'agent-bridge-worker')
    assert acked.status == 'paused'
    events = [e for _, e, _ in rig.ledger.audit_rows(record.request_id)]
    assert events == ['pause_requested', 'paused']


def test_acknowledge_cannot_skip_straight_from_pause_requested_to_resumed(tmp_path):
    rig = Rig(tmp_path, pausable=frozenset({'queued-task-1'}))
    record, _ = rig.service.request_pause('queued-task-1', 'eg')
    with pytest.raises(InvalidTransition):
        rig.service.acknowledge(record.request_id, 'resumed', 'agent-bridge-worker')


def test_a_failed_acknowledgement_is_a_visible_terminal_state(tmp_path):
    rig = Rig(tmp_path, pausable=frozenset({'queued-task-1'}))
    record, _ = rig.service.request_pause('queued-task-1', 'eg')
    failed = rig.service.acknowledge(record.request_id, 'failed', 'agent-bridge-worker',
                                     error='worker crashed mid-checkpoint')
    assert (failed.status, failed.error, failed.open) == ('failed', 'worker crashed mid-checkpoint', False)


# -- jobs that cannot be safely paused / unsupported agents ----------------------
def test_an_explicitly_not_pausable_task_is_refused(tmp_path):
    rig = Rig(tmp_path, not_pausable=frozenset({'jailed-codex-task'}))
    with pytest.raises(ControlRefused) as refused:
        rig.service.request_pause('jailed-codex-task', 'eg')
    assert (refused.value.code, refused.value.http) == ('not_pausable', 409)


def test_an_unknown_task_is_refused_fail_closed(tmp_path):
    """Unsupported agents/tasks this workspace was never told about: refuse,
    never assume a cooperative checkpoint exists."""
    rig = Rig(tmp_path)
    with pytest.raises(ControlRefused) as refused:
        rig.service.request_pause('never-mentioned-task', 'eg')
    assert (refused.value.code, refused.value.http) == ('pausability_unknown', 409)


def test_resume_and_priority_do_not_consult_pausability(tmp_path):
    """Resume only needs an open pause (checked separately); priority never
    stops a task mid-flight, so neither needs the pausability gate."""
    rig = Rig(tmp_path)  # nothing allow-listed
    record, _ = rig.service.request_priority('anything', 'chatgpt')
    assert record.status == 'priority_requested'


# -- duplicate requests / idempotency ---------------------------------------------
def test_a_second_plain_pause_click_while_one_is_open_is_not_a_duplicate(tmp_path):
    rig = Rig(tmp_path, pausable=frozenset({'queued-task-1'}))
    first, created_first = rig.service.request_pause('queued-task-1', 'eg')
    second, created_second = rig.service.request_pause('queued-task-1', 'eg')
    assert (first.request_id, created_first) == (second.request_id, True)
    assert created_second is False


def test_an_idempotency_key_replay_returns_the_same_request_even_for_a_different_task_id(tmp_path):
    """Guards urgent/priority dispatch from spawning a duplicate task: the
    caller's idempotency_key, not the task_id, is the source of truth for
    "have I already asked for this.\""""
    rig = Rig(tmp_path)
    first, created_first = rig.service.request_priority('urgent-check-1', 'chatgpt', idempotency_key='chat-req-77')
    second, created_second = rig.service.request_priority('urgent-check-1-retry-copy', 'chatgpt',
                                                           idempotency_key='chat-req-77')
    assert (first.request_id, first.task_id) == (second.request_id, second.task_id)
    assert (created_first, created_second) == (True, False)


def test_bad_request_without_a_task_id(tmp_path):
    rig = Rig(tmp_path)
    with pytest.raises(ControlRefused) as refused:
        rig.service.request_priority('', 'chatgpt')
    assert refused.value.code == 'bad_request'


# -- priority ordering -------------------------------------------------------------
def test_priority_requests_sort_ahead_of_pause_and_resume(tmp_path):
    rig = Rig(tmp_path, pausable=frozenset({'queued-task-1'}))
    rig.service.request_pause('queued-task-1', 'eg')
    rig.clock.advance(1)
    rig.service.request_priority('urgent-check-1', 'chatgpt')
    ordered = rig.service.list_recent(order='priority')
    assert [r.action for r in ordered] == ['priority', 'pause']


# -- persistence / restart recovery ------------------------------------------------
def test_requests_survive_a_dashboard_restart(tmp_path):
    rig = Rig(tmp_path, pausable=frozenset({'queued-task-1'}))
    record, _ = rig.service.request_pause('queued-task-1', 'eg')
    rig.restart()
    reloaded = rig.service.get(record.request_id)
    assert reloaded is not None
    assert reloaded.model_dump() == record.model_dump()


def test_an_acknowledgement_also_survives_a_restart(tmp_path):
    rig = Rig(tmp_path, pausable=frozenset({'queued-task-1'}))
    record, _ = rig.service.request_pause('queued-task-1', 'eg')
    rig.service.acknowledge(record.request_id, 'paused', 'agent-bridge-worker')
    rig.restart()
    assert rig.service.get(record.request_id).status == 'paused'


def test_acknowledging_an_unknown_request_id_is_not_found(tmp_path):
    rig = Rig(tmp_path)
    with pytest.raises(ControlRequestNotFound):
        rig.service.acknowledge('pc_doesnotexist00000000000', 'paused', 'agent-bridge-worker')
