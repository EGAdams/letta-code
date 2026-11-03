"""The Poll Settings tab's payload: green only when the worker really polls, never a call to HostGator."""
import json
import subprocess

from monitoring import agent_bridge_poll as abp

SHOW_RUNNING = ('ActiveState=active\nSubState=running\nUnitFileState=enabled\n'
                'MainPID=4242\nActiveEnterTimestamp=@1793503924\n')
WAITING = {'phase': 'waiting', 'outcome': 'idle', 'delay_seconds': 30.0,
           'next_check_at': '2026-10-31T23:32:34-04:00', 'checks': 3, 'pid': 4242}


def test_parse_show_reads_systemd_fields():
    service = abp.parse_show(SHOW_RUNNING)
    assert (service.active, service.enabled, service.pid) == ('active', 'enabled', 4242)
    assert service.started_at == 1793503924.0


def test_parse_show_tolerates_never_started():
    service = abp.parse_show('ActiveState=inactive\nUnitFileState=disabled\nMainPID=0\nActiveEnterTimestamp=\n')
    assert service.active == 'inactive' and service.started_at is None


def test_running_and_waiting_is_active():
    assert abp.classify(abp.parse_show(SHOW_RUNNING), WAITING)[0] == 'active'


def test_stopped_service_is_disabled():
    polling, why = abp.classify(abp.parse_show('ActiveState=inactive\nUnitFileState=disabled\n'), WAITING)
    assert polling == 'disabled' and 'inactive' in why and 'disabled' in why


def test_state_from_an_older_process_does_not_count():
    assert abp.classify(abp.parse_show(SHOW_RUNNING), {**WAITING, 'pid': 1})[0] == 'disabled'


def test_loop_that_said_stopped_is_disabled():
    assert abp.classify(abp.parse_show(SHOW_RUNNING), {**WAITING, 'phase': 'stopped'})[0] == 'disabled'


def test_outside_active_hours_is_paused():
    raw = {'active_hours': {'start_hour': 7, 'end_hour': 24}}
    assert abp.classify(abp.parse_show(SHOW_RUNNING), WAITING, raw, hour=3)[0] == 'paused'
    assert abp.classify(abp.parse_show(SHOW_RUNNING), WAITING, raw, hour=9)[0] == 'active'
    assert abp.classify(abp.parse_show(SHOW_RUNNING), WAITING, {'active_hours': None}, hour=3)[0] == 'active'


def test_overnight_hours_wrap_past_midnight():
    raw = {'active_hours': {'start_hour': 22, 'end_hour': 6}}
    assert [h for h in range(24) if not abp.outside_hours(raw, h)] == [0, 1, 2, 3, 4, 5, 22, 23]


def test_every_setting_gets_a_row_even_when_missing():
    rows = abp.setting_rows({'idle_seconds': 30})
    assert [r.key for r in rows] == [key for key, *_ in abp.SETTING_ROWS]
    idle = rows[0]
    assert idle.value == 30 and idle.in_file
    assert not rows[1].in_file and rows[1].value is None


def test_payload_from_files(tmp_path, monkeypatch):
    settings = tmp_path / 'poll_settings.json'
    state = tmp_path / 'poll_state.json'
    settings.write_text(json.dumps({'idle_seconds': 30, 'active_hours': None}))
    state.write_text(json.dumps(WAITING))
    monkeypatch.setattr(abp, 'SETTINGS_PATH', settings)
    monkeypatch.setattr(abp, 'STATE_PATH', state)
    monkeypatch.setattr(abp.subprocess, 'run',
                        lambda *a, **k: subprocess.CompletedProcess(a[0], 0, SHOW_RUNNING, ''))
    payload = abp.agent_bridge_poll_payload()
    assert payload['polling'] == 'active'
    assert payload['state']['checks'] == 3
    assert payload['settings'][0]['value'] == 30
    assert payload['settings_path'] == str(settings)
    assert 'restart' in payload['restart_command']


def test_missing_files_and_no_systemctl_still_answer(tmp_path, monkeypatch):
    monkeypatch.setattr(abp, 'SETTINGS_PATH', tmp_path / 'nope.json')
    monkeypatch.setattr(abp, 'STATE_PATH', tmp_path / 'nope_state.json')

    def boom(*a, **k):
        raise FileNotFoundError('systemctl')
    monkeypatch.setattr(abp.subprocess, 'run', boom)
    payload = abp.agent_bridge_poll_payload()
    assert payload['polling'] == 'disabled'
    assert 'not found' in payload['settings_error']
