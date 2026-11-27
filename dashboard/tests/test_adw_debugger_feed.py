"""The debugger feed against a real, temporary sssf.db -- no dashboard server."""
import json
import sqlite3

import pytest

from adw_debugger.feed import AdwDebuggerFeed
from adw_debugger.models import DebuggerSettings
from adw_debugger.sqlite_repository import SqliteAdwEventRepository

SCHEMA = """
CREATE TABLE sessions (adw_id TEXT PRIMARY KEY, adw_name TEXT, status TEXT, started_at TEXT, ended_at TEXT);
CREATE TABLE events (event_id TEXT PRIMARY KEY, adw_id TEXT, phase_id TEXT, parent_id TEXT, type TEXT,
                     name TEXT, payload_json TEXT, tokens INTEGER, started_at TEXT, ended_at TEXT);
CREATE TABLE processes (id INTEGER PRIMARY KEY AUTOINCREMENT, adw_id TEXT, kind TEXT, name TEXT, pid INTEGER,
                        command TEXT, started_at TEXT, ended_at TEXT);
"""


class Settings:
    def __init__(self, db_path, **extra):
        self.value = DebuggerSettings(db_path=db_path, **extra)

    def load(self):
        return self.value


class Processes:
    def __init__(self, living=()):
        self.living = set(living)

    def alive(self, pid, command):
        return pid in self.living


class Trace:
    def __init__(self, path):
        self.path = str(path)
        self.conn = sqlite3.connect(self.path, isolation_level=None)
        self.conn.executescript(SCHEMA)
        self.count = 0

    def run(self, run_id, adw='adw_debug_pilot', status='running', pid=None, started='2026-11-13T10:00:00+00:00'):
        self.conn.execute('INSERT INTO sessions VALUES (?,?,?,?,NULL)', (run_id, adw, status, started))
        if pid is not None:
            self.conn.execute("INSERT INTO processes (adw_id, kind, pid, command) VALUES (?,'adw',?,'adw_debug_pilot.py')",
                              (run_id, pid))

    def event(self, run_id, type_, payload, phase_id='', name=''):
        self.count += 1
        self.conn.execute('INSERT INTO events VALUES (?,?,?,?,?,?,?,NULL,?,NULL)',
                          (f'evt_{self.count}', run_id, phase_id, '', type_, name, json.dumps(payload),
                           '2026-11-13T10:00:01.000+00:00'))


@pytest.fixture
def trace(tmp_path):
    return Trace(tmp_path / 'sssf.db')


def feed(trace, living=(), **settings):
    return AdwDebuggerFeed(Settings(trace.path, **settings), SqliteAdwEventRepository, Processes(living), 'testbox')


def test_bootstrap_returns_the_run_and_every_one_of_its_events(trace):
    trace.run('r1', pid=7)
    trace.event('r1', 'log', {'adw_debug': {'kind': 'constructed', 'instance_id': 'r1:prepare',
                                            'phase_name': 'prepare', 'class_name': 'PrepareStep', 'attempt': 1}})
    trace.event('r1', 'phase_start', {'description': 'Choose items'}, 'r1_01_prepare', 'prepare')
    result = feed(trace, living=[7]).read(None)
    assert result.ok and result.bootstrap and result.machine == 'testbox'
    assert [run.status for run in result.runs] == ['running']
    assert [e.kind for e in result.events] == ['constructed', 'phase_start']
    assert result.events[0].instance_id == 'r1:prepare' and result.events[0].attempt == 1
    assert result.events[1].status == 'running' and result.events[1].instance_id == 'r1_01_prepare'
    assert result.cursor == 2 and result.stall_timeout_seconds == 120


def test_execution_host_is_producer_metadata_not_dashboard_hostname(trace):
    trace.run('dad')
    trace.event('dad', 'log', {'execution_host': 'DADSComputer'})
    result = feed(trace).read(None)
    assert result.runs[0].execution_host == 'DADSComputer'
    assert result.events[0].execution_host == 'DADSComputer'


def test_incremental_read_delivers_only_newer_monitored_events(trace):
    trace.run('r1')
    trace.run('other', adw='adw_bridge_worker')
    trace.event('r1', 'phase_start', {}, 'r1_01_a', 'a')
    named = dict(adw_names=['adw_debug_pilot'])
    first = feed(trace, **named).read(None)
    trace.event('other', 'log', {'message': 'not ours'})
    trace.event('r1', 'phase_end', {'status': 'fail'}, 'r1_01_a', 'a')
    second = feed(trace, **named).read(first.cursor)
    assert [(e.kind, e.status) for e in second.events] == [('phase_end', 'fail')]
    assert second.cursor == 3
    assert feed(trace, **named).read(second.cursor).events == []


def test_resending_a_cursor_redelivers_the_same_events_and_no_gap(trace):
    trace.run('r1')
    for _ in range(5):
        trace.event('r1', 'log', {'message': 'x'})
    paged = feed(trace, page_limit=2)
    first = paged.read(0)
    assert [e.cursor for e in first.events] == [1, 2] and first.cursor == 2
    assert [e.cursor for e in paged.read(0).events] == [1, 2]
    assert [e.cursor for e in paged.read(2).events] == [3, 4]
    assert [e.cursor for e in paged.read(4).events] == [5]


def test_a_running_run_whose_process_is_gone_is_interrupted_not_failed(trace):
    trace.run('r1', pid=99)
    run = feed(trace, living=[]).read(None).runs[0]
    assert run.status == 'interrupted' and run.process_alive is False


def test_text_is_delivered_whole(trace):
    text = 'line one; "q"\nend\n<script>x</script>' + ' long' * 500
    trace.run('r1')
    trace.event('r1', 'tool_result', {'adw_debug': {'kind': 'tool_result', 'instance_id': 'r1:lookup-1',
                                                    'tool': 'catalog.get', 'call_id': 'call_1', 'result': text}})
    event = feed(trace).read(None).events[0]
    assert event.message.endswith(text) and event.call_id == 'call_1' and event.tool == 'catalog.get'


def test_waiting_carries_its_deadline_and_messages_carry_both_ends(trace):
    trace.run('r1')
    trace.event('r1', 'log', {'adw_debug': {'kind': 'waiting', 'instance_id': 'r1:wait', 'text': 'gate',
                                            'deadline_seconds': 30}}, 'r1_04_wait')
    trace.event('r1', 'handoff', {'adw_debug': {'kind': 'message', 'instance_id': 'r1:prepare', 'text': 'hi',
                                                'source_instance': 'r1:prepare', 'target_instance': 'r1:report'}})
    waiting, message = feed(trace).read(None).events
    assert waiting.deadline_at == '2026-11-13T10:00:31.000+00:00'
    assert (message.source_instance, message.target_instance) == ('r1:prepare', 'r1:report')


def test_a_missing_database_is_reported_and_never_created(tmp_path):
    missing = tmp_path / 'nope.db'
    result = AdwDebuggerFeed(Settings(str(missing)), SqliteAdwEventRepository, Processes(), 'testbox').read(None)
    assert result.ok is False and 'OperationalError' in result.error
    assert not missing.exists()


def test_old_runs_beyond_the_bootstrap_window_are_left_out_unless_running(trace):
    trace.run('old-running', started='2026-11-01T00:00:00+00:00')
    for index in range(4):
        trace.run(f'done{index}', status='success', started=f'2026-11-1{index}T00:00:00+00:00')
    ids = [run.run_id for run in feed(trace, bootstrap_runs=2).read(None).runs]
    assert ids == ['old-running', 'done2', 'done3']


def test_every_adw_is_visible_by_default(trace):
    trace.run('scala', adw='adw_interface_scala_file_scan', status='success')
    trace.event('scala', 'log', {'adw_debug': {'kind': 'constructed',
                'instance_id': 'scala:read_text', 'phase_name': 'read_text', 'class_name': 'ReadTextPhase'}})
    trace.event('scala', 'phase_start', {}, 'scala_03_read_text', 'read_text')
    trace.event('scala', 'phase_end', {'status': 'success'}, 'scala_03_read_text', 'read_text')
    trace.run('pilot', status='success')
    trace.run('worker', adw='adw_bridge_worker')
    result = feed(trace).read(None)
    assert {run.adw_name for run in result.runs} == {
        'adw_debug_pilot', 'adw_interface_scala_file_scan', 'adw_bridge_worker'}
    assert [e.kind for e in result.events] == ['constructed', 'phase_start', 'phase_end']
    assert result.events[-1].status == 'pass'


def test_an_excluded_adw_is_left_out_of_runs_and_live_events(trace):
    trace.run('scala', adw='adw_interface_scala_file_scan')
    trace.run('worker', adw='adw_bridge_worker')
    quiet = dict(exclude_adws=['adw_bridge_worker'])
    first = feed(trace, **quiet).read(None)
    assert [run.run_id for run in first.runs] == ['scala']
    trace.event('worker', 'log', {'message': 'muted'})
    trace.event('scala', 'log', {'message': 'shown'})
    assert [e.run_id for e in feed(trace, **quiet).read(first.cursor).events] == ['scala']


def test_one_run_read_returns_only_that_run_and_all_its_events(trace):
    trace.run('r1')
    trace.run('r2', started='2026-11-13T11:00:00+00:00')
    trace.event('r1', 'phase_start', {}, 'r1_01_a', 'a')
    trace.event('r2', 'phase_start', {}, 'r2_01_a', 'a')
    trace.event('r1', 'phase_end', {'status': 'pass'}, 'r1_01_a', 'a')
    first = feed(trace).read_run('r1', None)
    assert first.ok and first.bootstrap and [run.run_id for run in first.runs] == ['r1']
    assert [e.cursor for e in first.events] == [1, 3] and first.cursor == 3
    trace.event('r1', 'log', {'message': 'later'})
    later = feed(trace).read_run('r1', first.cursor)
    assert [e.cursor for e in later.events] == [4] and not later.bootstrap


def test_one_run_read_of_an_unknown_run_fails_closed(trace):
    trace.run('r1')
    result = feed(trace).read_run('nope', None)
    assert result.ok is False and 'nope' in result.error and result.events == []
    assert feed(trace).read_run('', None).ok is False


def test_one_run_read_recovers_legacy_trace_with_its_own_cursor(trace, tmp_path):
    legacy = Trace(tmp_path / 'legacy.db')
    legacy.run('triage', adw='adw_failure_triage', status='success')
    legacy.event('triage', 'phase_start', {}, 'triage_01_collect', 'collect')
    legacy.event('triage', 'phase_end', {'status': 'pass'}, 'triage_01_collect', 'collect')
    trace.run('primary')
    trace.event('primary', 'phase_start', {}, 'primary_01_collect', 'collect')
    service = feed(trace, legacy_db_path=legacy.path)

    first = service.read_run('triage', None)
    assert first.ok and first.runs[0].status == 'success'
    assert [event.cursor for event in first.events] == [1, 2]
    assert first.cursor == 2
    assert service.read_run('triage', first.cursor).events == []
    assert service.read_run('primary', None).cursor == 1
    assert [run.run_id for run in service.read(None).runs] == ['primary']
