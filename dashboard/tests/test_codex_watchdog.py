"""Policy and orchestration tests for the Codex CLI quota watchdog.

`evaluate()` is pure, so the 2026-09-07 incident (three concurrent autonomous
sessions, one at 97% quota, one stopped in place) is expressed directly as a
table of process groups and expected decisions -- no real processes, no real
clock.
"""

from __future__ import annotations

from health.codex_watchdog import CodexWatchdog, evaluate
from health.codex_watchdog_contracts import (
    AUTONOMOUS_FLAG,
    CodexProcessGroup,
    CodexUsageSample,
    WatchdogAction,
)
from health.codex_watchdog_store import InMemoryWatchdogActionStore

WATCHED_CMD = 'node bin/codex'  # no AUTONOMOUS_FLAG: a person is watching it
AUTO_CMD = f'node bin/codex {AUTONOMOUS_FLAG}'


def _group(pgid, cmd=AUTO_CMD, state='Sl+', elapsed=60.0, session_path=None):
    return CodexProcessGroup(
        pgid=pgid, pids=[pgid], cmd=cmd, cwd='/home/adamsl/letta-code',
        state=state, elapsed_seconds=elapsed, session_path=session_path,
    )


def _usage(session_path, percent):
    return CodexUsageSample(session_path=session_path, observed_at=0.0,
                             primary_used_percent=percent)


def test_watched_session_is_never_touched_regardless_of_quota():
    group = _group(1, cmd=WATCHED_CMD, session_path='/s/a.jsonl')
    usage = {'/s/a.jsonl': _usage('/s/a.jsonl', 99.0)}
    decisions, _ = evaluate([group], usage, {}, now=1000.0)
    assert decisions == []


def test_kills_the_group_at_the_incident_quota_level():
    group = _group(1, session_path='/s/a.jsonl')
    usage = {'/s/a.jsonl': _usage('/s/a.jsonl', 97.0)}
    decisions, _ = evaluate([group], usage, {}, now=1000.0)
    assert len(decisions) == 1
    assert decisions[0].action == 'terminate_quota'
    assert decisions[0].group.pgid == 1
    assert decisions[0].used_percent == 97.0


def test_warns_but_does_not_kill_below_kill_threshold():
    group = _group(1, session_path='/s/a.jsonl')
    usage = {'/s/a.jsonl': _usage('/s/a.jsonl', 75.0)}
    decisions, _ = evaluate([group], usage, {}, now=1000.0)
    assert len(decisions) == 1
    assert decisions[0].action == 'warn_quota'


def test_healthy_quota_takes_no_action():
    group = _group(1, session_path='/s/a.jsonl')
    usage = {'/s/a.jsonl': _usage('/s/a.jsonl', 10.0)}
    decisions, _ = evaluate([group], usage, {}, now=1000.0)
    assert decisions == []


def test_missing_usage_sample_takes_no_quota_action():
    group = _group(1, session_path=None)
    decisions, _ = evaluate([group], {}, {}, now=1000.0)
    assert decisions == []


def test_stopped_session_is_reaped_after_the_grace_window():
    group = _group(1, state='Tl', session_path='/s/a.jsonl')
    stopped_since = {1: 100.0}
    decisions, next_state = evaluate(
        [group], {}, stopped_since, now=800.0, stopped_reap_seconds=600.0)
    assert len(decisions) == 1
    assert decisions[0].action == 'terminate_stopped'
    # The kill itself hasn't happened yet (evaluate() only decides); the
    # group is still "live" as far as this poll can see, so its clock stays
    # until a later poll observes it actually gone.
    assert next_state == {1: 100.0}


def test_stopped_session_is_left_alone_before_the_grace_window():
    group = _group(1, state='Tl', session_path='/s/a.jsonl')
    decisions, next_state = evaluate(
        [group], {}, {}, now=100.0, stopped_reap_seconds=600.0)
    assert decisions == []
    assert next_state == {1: 100.0}


def test_resuming_a_stopped_session_clears_its_stopped_clock():
    group = _group(1, state='Sl+', session_path='/s/a.jsonl')
    decisions, next_state = evaluate(
        [group], {}, {1: 100.0}, now=105.0)
    assert decisions == []
    assert next_state == {}


def test_exited_group_is_forgotten_instead_of_leaking_stopped_state():
    decisions, next_state = evaluate([], {}, {1: 100.0}, now=105.0)
    assert decisions == []
    assert next_state == {}


def test_concurrency_limit_kills_only_the_newer_sessions():
    old = _group(1, elapsed=3600.0, session_path='/s/old.jsonl')
    newer = _group(2, elapsed=100.0, session_path='/s/new.jsonl')
    decisions, _ = evaluate(
        [old, newer], {}, {}, now=1000.0, max_concurrent=1)
    assert len(decisions) == 1
    assert decisions[0].action == 'terminate_concurrency'
    assert decisions[0].group.pgid == 2


def test_incident_shape_kills_stopped_and_quota_sessions_leaving_one_survivor():
    """Three autonomous sessions like 2026-09-07: one stopped past the grace
    window, one over quota, one healthy. Killing the first two leaves just
    the healthy one -- within max_concurrent=1, so it is left running."""
    stopped = _group(1, state='Tl', elapsed=4896.0, session_path=None)
    over_quota = _group(2, elapsed=4878.0, session_path='/s/burning.jsonl')
    healthy = _group(3, elapsed=3544.0, session_path='/s/quiet.jsonl')
    usage = {
        '/s/burning.jsonl': _usage('/s/burning.jsonl', 97.0),
        '/s/quiet.jsonl': _usage('/s/quiet.jsonl', 5.0),
    }
    decisions, _ = evaluate(
        [stopped, over_quota, healthy], usage, {1: 0.0}, now=700.0,
        max_concurrent=1)
    actions_by_pgid = {d.group.pgid: d.action for d in decisions}
    assert actions_by_pgid == {1: 'terminate_stopped', 2: 'terminate_quota'}


def test_incident_shape_with_two_healthy_survivors_still_caps_concurrency():
    """Same as above but a second healthy session was also running --
    after the stopped/quota kills, two survivors still exceed
    max_concurrent=1, so the newer of the two is also terminated."""
    stopped = _group(1, state='Tl', elapsed=4896.0, session_path=None)
    over_quota = _group(2, elapsed=4878.0, session_path='/s/burning.jsonl')
    older_healthy = _group(3, elapsed=3544.0, session_path='/s/quiet.jsonl')
    newer_healthy = _group(4, elapsed=100.0, session_path='/s/quiet2.jsonl')
    usage = {
        '/s/burning.jsonl': _usage('/s/burning.jsonl', 97.0),
        '/s/quiet.jsonl': _usage('/s/quiet.jsonl', 5.0),
        '/s/quiet2.jsonl': _usage('/s/quiet2.jsonl', 5.0),
    }
    decisions, _ = evaluate(
        [stopped, over_quota, older_healthy, newer_healthy], usage,
        {1: 0.0}, now=700.0, max_concurrent=1)
    actions_by_pgid = {d.group.pgid: d.action for d in decisions}
    assert actions_by_pgid == {
        1: 'terminate_stopped',
        2: 'terminate_quota',
        4: 'terminate_concurrency',
    }


class _FakeInspector:
    def __init__(self, groups):
        self._groups = groups

    def running_groups(self):
        return self._groups


class _FakeReader:
    def __init__(self, usage_by_path):
        self._usage_by_path = usage_by_path

    def usage_for(self, session_path):
        return self._usage_by_path.get(session_path)


class _FakeController:
    def __init__(self):
        self.terminated = []
        self.killed = []

    def terminate(self, pgid):
        self.terminated.append(pgid)

    def force_kill(self, pgid):
        self.killed.append(pgid)


def test_watchdog_applies_quota_kill_and_records_it():
    group = _group(1, session_path='/s/a.jsonl')
    controller = _FakeController()
    store = InMemoryWatchdogActionStore()
    watchdog = CodexWatchdog(
        inspector=_FakeInspector([group]),
        reader=_FakeReader({'/s/a.jsonl': _usage('/s/a.jsonl', 97.0)}),
        controller=controller,
        store=store,
        clock=lambda: 42.0,
        sleeper=lambda _seconds: None,
    )

    decisions = watchdog.poll_once()

    assert len(decisions) == 1
    assert controller.terminated == [1]
    assert controller.killed == [1]
    recorded = store.recent()
    assert len(recorded) == 1
    assert isinstance(recorded[0], WatchdogAction)
    assert recorded[0].action == 'terminate_quota'
    assert recorded[0].timestamp == 42.0


def test_watchdog_warn_does_not_touch_the_process_and_only_warns_once():
    group = _group(1, session_path='/s/a.jsonl')
    controller = _FakeController()
    store = InMemoryWatchdogActionStore()
    logged = []
    watchdog = CodexWatchdog(
        inspector=_FakeInspector([group]),
        reader=_FakeReader({'/s/a.jsonl': _usage('/s/a.jsonl', 75.0)}),
        controller=controller,
        store=store,
        clock=lambda: 1.0,
        sleeper=lambda _seconds: None,
        log=logged.append,
    )

    watchdog.poll_once()
    watchdog.poll_once()

    assert controller.terminated == []
    assert controller.killed == []
    assert len(store.recent()) == 1  # only warned once, not every poll
    assert sum(1 for line in logged if line.startswith('WARN')) == 1
