"""The scanner LEDs: the probes, and the rules that colour them.

`tests/test_server.py` already asserts a dozen whole-snapshot outcomes, and
those passing unchanged is most of the evidence the move was faithful. Two
things they never reached:

* the probe helpers. `_airscan_ready` and `_run_scanner_diag_ps` were private
  to a 10,000-line module and could only be exercised by monkeypatching
  `subprocess`; both are the layer that decides whether Windows gets consulted
  at all, and both are written to answer "couldn't ask" rather than "broken".
* the colour precedence. An LED that should be grey (unknown) but comes out
  red tells an operator to power-cycle healthy hardware -- the exact failure
  the AirScan path was added to stop -- and no assertion covered the ladder
  itself, only a handful of points on it.
"""
import json
import os

import pytest

import server
from hardware import scanner_diagnostics as diag


WINDOW = {'namelike': 'Window', 'driver_match': 'HP OfficeJet',
          'airscan_device': 'airscan:e0:Window Scanner'}


def led(result, check_id):
    return next((c for c in result['checks'] if c['id'] == check_id), None)


def states(result):
    return {c['id']: c['state'] for c in result['checks']}


def healthy_ps(**overrides):
    ps = {'stisvc': 'Running', 'driver_status': 'ok', 'wia': 'present',
          'wia_connect': 'ready', 'stale_scans': 0}
    ps.update(overrides)
    return ps


class FakeCompleted:
    def __init__(self, stdout='', stderr='', returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


class TestAirscanProbe:
    """Can the native eSCL backend answer for this scanner?"""

    def test_a_scanner_with_no_airscan_device_is_not_ready(self, monkeypatch):
        monkeypatch.setattr(diag.shutil, 'which', lambda n: '/usr/bin/scanimage')
        assert diag._airscan_ready({'namelike': 'Window'}) is False

    def test_a_blank_airscan_device_is_not_ready(self, monkeypatch):
        monkeypatch.setattr(diag.shutil, 'which', lambda n: '/usr/bin/scanimage')
        assert diag._airscan_ready({'airscan_device': ''}) is False

    def test_a_box_without_scanimage_is_not_ready(self, monkeypatch):
        monkeypatch.setattr(diag.shutil, 'which', lambda n: None)
        called = []
        monkeypatch.setattr(diag.subprocess, 'run',
                            lambda *a, **k: called.append(a))
        assert diag._airscan_ready(WINDOW) is False
        assert called == [], 'must not shell out when scanimage is absent'

    def test_it_only_asks_for_capabilities_never_a_scan(self, monkeypatch):
        seen = {}
        monkeypatch.setattr(diag.shutil, 'which', lambda n: '/usr/bin/scanimage')
        def run(args, **kwargs):
            seen['args'] = args
            seen['kwargs'] = kwargs
            return FakeCompleted(returncode=0)
        monkeypatch.setattr(diag.subprocess, 'run', run)
        assert diag._airscan_ready(WINDOW) is True
        assert seen['args'] == ['scanimage', '-d', WINDOW['airscan_device'], '--help']
        assert seen['kwargs']['timeout'] == diag.SCANNER_DIAG_TIMEOUT_SEC

    def test_a_nonzero_exit_is_not_ready(self, monkeypatch):
        monkeypatch.setattr(diag.shutil, 'which', lambda n: '/usr/bin/scanimage')
        monkeypatch.setattr(diag.subprocess, 'run',
                            lambda *a, **k: FakeCompleted(returncode=1))
        assert diag._airscan_ready(WINDOW) is False

    @pytest.mark.parametrize('exc', [
        OSError('backend gone'), TimeoutError('slow'), ValueError('weird'),
    ])
    def test_any_backend_failure_falls_back_cleanly(self, monkeypatch, exc):
        monkeypatch.setattr(diag.shutil, 'which', lambda n: '/usr/bin/scanimage')
        def boom(*a, **k):
            raise exc
        monkeypatch.setattr(diag.subprocess, 'run', boom)
        assert diag._airscan_ready(WINDOW) is False


class TestWindowsProbe:
    """scanner_diag.ps1: one launch, and every failure means 'couldn't ask'."""

    def test_a_missing_script_returns_none_rather_than_shelling_out(self, tmp_path, monkeypatch):
        called = []
        monkeypatch.setattr(diag.subprocess, 'run', lambda *a, **k: called.append(a))
        assert diag._run_scanner_diag_ps(WINDOW, '/run/WSL/x', str(tmp_path)) is None
        assert called == []

    def write_script(self, tmp_path):
        (tmp_path / 'scanner_diag.ps1').write_text('# stub')
        return str(tmp_path)

    def test_the_scan_tools_dir_is_the_one_it_was_handed(self, tmp_path, monkeypatch):
        """The directory is an argument now; the module has no opinion on it."""
        seen = {}
        d = self.write_script(tmp_path)
        def run(args, **kwargs):
            seen.update(kwargs)
            seen['args'] = args
            return FakeCompleted(stdout='{"stisvc":"Running"}')
        monkeypatch.setattr(diag.subprocess, 'run', run)
        assert diag._run_scanner_diag_ps(WINDOW, '/run/WSL/x', d) == {'stisvc': 'Running'}
        assert seen['cwd'] == d
        assert seen['env']['WSL_INTEROP'] == '/run/WSL/x'

    def test_it_passes_both_match_patterns_from_the_scanner_config(self, tmp_path, monkeypatch):
        d = self.write_script(tmp_path)
        seen = {}
        def run(args, **k):
            seen['args'] = args
            return FakeCompleted(stdout='{}')
        monkeypatch.setattr(diag.subprocess, 'run', run)
        diag._run_scanner_diag_ps(WINDOW, '/run/WSL/x', d)
        args = seen['args']
        assert args[args.index('-NameLike') + 1] == 'Window'
        assert args[args.index('-FriendlyLike') + 1] == 'HP OfficeJet'

    def test_a_config_missing_its_patterns_still_launches_with_blanks(self, tmp_path, monkeypatch):
        d = self.write_script(tmp_path)
        seen = {}
        def run(args, **k):
            seen['args'] = args
            return FakeCompleted(stdout='{}')
        monkeypatch.setattr(diag.subprocess, 'run', run)
        diag._run_scanner_diag_ps({}, '/run/WSL/x', d)
        assert seen['args'][seen['args'].index('-NameLike') + 1] == ''

    def test_skip_wia_is_only_appended_when_asked(self, tmp_path, monkeypatch):
        d = self.write_script(tmp_path)
        seen = []
        monkeypatch.setattr(diag.subprocess, 'run',
                            lambda args, **k: seen.append(args)
                            or FakeCompleted(stdout='{}'))
        diag._run_scanner_diag_ps(WINDOW, '/run/WSL/x', d)
        diag._run_scanner_diag_ps(WINDOW, '/run/WSL/x', d, skip_wia=True)
        assert '-SkipWia' not in seen[0]
        assert '-SkipWia' in seen[1]

    def test_only_the_last_stdout_line_is_parsed(self, tmp_path, monkeypatch):
        """PowerShell warnings ahead of the JSON must not defeat the probe."""
        d = self.write_script(tmp_path)
        monkeypatch.setattr(diag.subprocess, 'run', lambda *a, **k: FakeCompleted(
            stdout='WARNING: something\nVERBOSE: noise\n{"stisvc":"Running"}\n'))
        assert diag._run_scanner_diag_ps(WINDOW, '/run/WSL/x', d) == {'stisvc': 'Running'}

    @pytest.mark.parametrize('stdout', ['', '   \n  ', 'not json', 'WARNING: only'])
    def test_unusable_output_is_unknown_not_broken(self, tmp_path, monkeypatch, stdout):
        d = self.write_script(tmp_path)
        monkeypatch.setattr(diag.subprocess, 'run',
                            lambda *a, **k: FakeCompleted(stdout=stdout))
        assert diag._run_scanner_diag_ps(WINDOW, '/run/WSL/x', d) is None

    def test_a_launch_failure_is_unknown_not_broken(self, tmp_path, monkeypatch):
        d = self.write_script(tmp_path)
        def boom(*a, **k):
            raise OSError('interop dead')
        monkeypatch.setattr(diag.subprocess, 'run', boom)
        assert diag._run_scanner_diag_ps(WINDOW, '/run/WSL/x', d) is None

    def test_it_uses_the_shared_powershell_binary(self, tmp_path, monkeypatch):
        d = self.write_script(tmp_path)
        seen = {}
        def run(args, **k):
            seen['args'] = args
            return FakeCompleted(stdout='{}')
        monkeypatch.setattr(diag.subprocess, 'run', run)
        diag._run_scanner_diag_ps(WINDOW, '/run/WSL/x', d)
        assert seen['args'][0] == diag.WINDOWS_POWERSHELL


class TestWindowsReachability:
    """Windows checks are grey unless we both reached it AND it answered."""

    @pytest.mark.parametrize('interop_ok, ps_data', [
        (False, None),
        (False, healthy_ps()),   # a socket we could not use
        (True, None),            # a socket that produced no answer
    ])
    def test_windows_checks_are_grey_without_a_real_answer(self, interop_ok, ps_data):
        result = diag.build_scanner_diagnostics('window', interop_ok, ps_data)
        for check_id in ('service', 'driver', 'online', 'stale'):
            assert led(result, check_id)['state'] == 'unknown', check_id

    def test_stale_ps_data_cannot_turn_leds_green_without_interop(self):
        """A cached-looking healthy dict must not paint over a dead bridge."""
        result = diag.build_scanner_diagnostics('window', False, healthy_ps())
        assert led(result, 'bridge')['state'] == 'bad'
        assert led(result, 'service')['state'] == 'unknown'
        assert result['overall'] == 'bad'

    def test_a_reachable_windows_that_answered_is_read_normally(self):
        result = diag.build_scanner_diagnostics('window', True, healthy_ps())
        assert result['overall'] == 'ok'
        assert set(states(result).values()) == {'ok'}


class TestOverallPrecedence:
    """One red beats any number of yellows; grey is never green."""

    def test_red_wins_over_yellow(self):
        result = diag.build_scanner_diagnostics(
            'window', True, healthy_ps(wia='absent', stale_scans=3))
        assert result['overall'] == 'bad'

    def test_yellow_beats_green(self):
        result = diag.build_scanner_diagnostics(
            'window', True, healthy_ps(stale_scans=2))
        assert result['overall'] == 'warn'

    def test_grey_is_reported_as_yellow_never_green(self):
        """'We could not check' must never read as 'everything is fine'."""
        result = diag.build_scanner_diagnostics(
            'window', True, healthy_ps(driver_status='unknown'))
        assert led(result, 'driver')['state'] == 'unknown'
        assert result['overall'] == 'warn'

    def test_all_green_is_green(self):
        assert diag.build_scanner_diagnostics(
            'window', True, healthy_ps())['overall'] == 'ok'

    def test_every_led_carries_the_four_fields_the_ui_renders(self):
        result = diag.build_scanner_diagnostics('freezer', True, healthy_ps())
        for check in result['checks']:
            assert set(check) == {'id', 'label', 'state', 'detail'}
            assert check['detail'].strip(), check['id']
            assert check['state'] in ('ok', 'warn', 'bad', 'unknown')

    def test_led_ids_are_unique_within_a_snapshot(self):
        ids = [c['id'] for c in diag.build_scanner_diagnostics(
            'freezer', True, healthy_ps(hp_scan_doctor='Running'),
            {'reachable': True, 'categories': ['doorOpen'],
             'blocker': 'A door is open.', 'note': None})['checks']]
        assert len(ids) == len(set(ids))


class TestDriverLadder:
    @pytest.mark.parametrize('ps, state', [
        ({'driver_status': 'ok'}, 'ok'),
        ({'driver_status': 'absent'}, 'bad'),
        ({'driver_status': 'error'}, 'bad'),
        ({'driver_status': 'ERROR'}, 'bad'),
        ({'driver_status': ''}, 'unknown'),
        ({'driver_status': 'unknown'}, 'unknown'),
        ({'driver_status': 'degraded'}, 'warn'),
        ({'driver_status': 'ok', 'driver_present': False}, 'ok'),
        ({'driver_status': 'started', 'driver_present': False}, 'bad'),
    ])
    def test_the_ladder(self, ps, state):
        result = diag.build_scanner_diagnostics('window', True, ps)
        assert led(result, 'driver')['state'] == state

    def test_an_unrecognised_state_is_quoted_back_to_the_operator(self):
        result = diag.build_scanner_diagnostics(
            'window', True, {'driver_status': 'Degraded'})
        assert '"Degraded"' in led(result, 'driver')['detail']

    def test_a_missing_driver_names_the_installer(self):
        result = diag.build_scanner_diagnostics(
            'window', True, {'driver_status': 'absent'})
        assert 'HP Easy Start' in led(result, 'driver')['detail']


class TestOnlineLadder:
    @pytest.mark.parametrize('wia, state', [
        ('present', 'ok'), ('absent', 'bad'), ('busy', 'warn'),
        ('timeout', 'bad'), ('skipped', 'warn'), ('service-down', 'unknown'),
        ('gibberish', 'warn'), ('', 'warn'), ('PRESENT', 'ok'),
    ])
    def test_the_ladder(self, wia, state):
        result = diag.build_scanner_diagnostics('window', True, {'wia': wia})
        assert led(result, 'online')['state'] == state

    def test_a_skipped_check_says_a_scan_is_running_not_that_it_broke(self):
        result = diag.build_scanner_diagnostics('window', True, {'wia': 'skipped'})
        assert 'scan is in progress' in led(result, 'online')['detail']

    def test_a_wia_timeout_points_at_the_imaging_service(self):
        result = diag.build_scanner_diagnostics('window', True, {'wia': 'timeout'})
        assert 'stisvc' in led(result, 'online')['detail']


class TestAccessLadder:
    """Enumeration only proves Windows sees it; Connect() is the real test."""

    def test_the_led_is_absent_when_the_script_did_not_report_it(self):
        result = diag.build_scanner_diagnostics('window', True, {'wia': 'present'})
        assert led(result, 'access') is None

    @pytest.mark.parametrize('access, state', [
        ('ready', 'ok'), ('busy', 'bad'), ('timeout', 'bad'),
        ('skipped', 'unknown'), ('service-down', 'unknown'),
        ('not-tested', 'unknown'), ('surprise', 'bad'), ('', 'bad'),
    ])
    def test_the_ladder(self, access, state):
        result = diag.build_scanner_diagnostics(
            'window', True, {'wia': 'present', 'wia_connect': access})
        assert led(result, 'access')['state'] == state

    def test_an_exclusive_holder_is_red_even_though_windows_sees_it(self):
        """The 'all LEDs green, scan says busy' failure this LED was added for."""
        result = diag.build_scanner_diagnostics(
            'window', True, healthy_ps(wia_connect='busy'))
        assert led(result, 'online')['state'] == 'ok'
        assert led(result, 'access')['state'] == 'bad'
        assert result['overall'] == 'bad'


class TestHpScanDoctor:
    def test_the_led_is_absent_when_the_script_did_not_report_it(self):
        result = diag.build_scanner_diagnostics('window', True, healthy_ps())
        assert led(result, 'hp-doctor') is None

    @pytest.mark.parametrize('doctor, access, state', [
        ('Running', 'ready', 'warn'),
        ('Running', 'busy', 'bad'),
        ('Running', 'error', 'bad'),
        ('Running', 'timeout', 'bad'),
        ('Stopped', 'ready', 'ok'),
        ('absent', 'ready', 'ok'),
        ('Weird', 'ready', 'unknown'),
    ])
    def test_the_ladder(self, doctor, access, state):
        result = diag.build_scanner_diagnostics(
            'window', True, healthy_ps(hp_scan_doctor=doctor, wia_connect=access))
        assert led(result, 'hp-doctor')['state'] == state

    def test_a_running_doctor_that_is_holding_the_scanner_names_the_service(self):
        result = diag.build_scanner_diagnostics(
            'window', True, healthy_ps(hp_scan_doctor='Running', wia_connect='busy'))
        assert 'HPPrintScanDoctorService' in led(result, 'hp-doctor')['detail']


class TestStuckScans:
    @pytest.mark.parametrize('stale, state', [
        (0, 'ok'), (1, 'warn'), (9, 'warn'), (-1, 'unknown'), (None, 'unknown'),
    ])
    def test_the_ladder(self, stale, state):
        result = diag.build_scanner_diagnostics(
            'window', True, healthy_ps(stale_scans=stale))
        assert led(result, 'stale')['state'] == state

    def test_the_count_is_shown(self):
        result = diag.build_scanner_diagnostics(
            'window', True, healthy_ps(stale_scans=4))
        assert '4 stuck scan' in led(result, 'stale')['detail']


class TestImagingService:
    @pytest.mark.parametrize('stisvc, state', [
        ('Running', 'ok'), ('Stopped', 'bad'), ('StopPending', 'bad'),
        ('Paused', 'bad'), ('StartPending', 'bad'), ('Missing', 'unknown'),
        ('', 'unknown'),
    ])
    def test_the_ladder(self, stisvc, state):
        result = diag.build_scanner_diagnostics('window', True, {'stisvc': stisvc})
        assert led(result, 'service')['state'] == state

    def test_a_stopped_service_gives_the_command_to_restart_it(self):
        result = diag.build_scanner_diagnostics('window', True, {'stisvc': 'Stopped'})
        assert 'net start stisvc' in led(result, 'service')['detail']


class TestAirscanShortCircuit:
    """When eSCL answers, stale Windows state is irrelevant, not red."""

    def test_every_windows_led_goes_green_regardless_of_ps_data(self):
        result = diag.build_scanner_diagnostics(
            'window', False, {'stisvc': 'Stopped', 'driver_status': 'absent',
                              'wia': 'absent', 'stale_scans': 7},
            airscan_ready=True)
        assert result['overall'] == 'ok'
        assert set(states(result).values()) == {'ok'}

    def test_it_never_tells_the_operator_to_power_cycle_healthy_hardware(self):
        result = diag.build_scanner_diagnostics(
            'window', False, {'wia': 'absent'}, airscan_ready=True)
        joined = ' '.join(c['detail'] for c in result['checks'])
        assert 'power-cycle' not in joined.lower()
        assert 'reinstall' not in joined.lower()

    def test_hp_doctor_and_access_ladders_are_skipped_entirely(self):
        result = diag.build_scanner_diagnostics(
            'window', True, healthy_ps(hp_scan_doctor='Running', wia_connect='busy'),
            airscan_ready=True)
        assert led(result, 'hp-doctor') is None
        assert led(result, 'access')['state'] == 'ok'

    @pytest.mark.parametrize('airscan_ready', [
        False, None,
        # Truthy, but not an answered probe. The check is `is True` on purpose:
        # this branch declares six LEDs green sight-unseen, so only a probe that
        # actually succeeded may reach it. A caller that passes the device
        # string, or a dict it had lying around, must fall through to Windows
        # rather than paint a broken scanner green.
        'airscan:e0:Window Scanner', 1, {'stisvc': 'Stopped'}, ['ready'],
    ])
    def test_only_an_answered_probe_short_circuits(self, airscan_ready):
        result = diag.build_scanner_diagnostics(
            'window', True, {'stisvc': 'Stopped'}, airscan_ready=airscan_ready)
        assert led(result, 'service')['state'] == 'bad'

    def test_a_device_blocker_still_shows_through_the_short_circuit(self):
        result = diag.build_scanner_diagnostics(
            'freezer', False, None,
            {'reachable': True, 'categories': ['doorOpen'],
             'blocker': 'A door or cover is open on the printer.', 'note': None},
            airscan_ready=True)
        assert led(result, 'device')['state'] == 'bad'
        assert result['overall'] == 'bad'


class TestFreezerDeviceStatus:
    """The Freezer DeskJet is scanner-only: paper and ink are never its problem."""

    def test_a_print_only_note_produces_no_led_on_either_path(self):
        print_only = {'reachable': True, 'categories': ['trayEmpty'],
                      'blocker': None, 'note': 'it is out of paper'}
        for airscan in (True, None):
            result = diag.build_scanner_diagnostics(
                'freezer', True, healthy_ps(), print_only, airscan_ready=airscan)
            assert led(result, 'device') is None
            assert result['overall'] == 'ok'

    def test_the_window_scanner_never_gets_a_device_led(self):
        """That LED reads the DeskJet; the Window scanner is a different box."""
        result = diag.build_scanner_diagnostics(
            'window', True, healthy_ps(),
            {'reachable': True, 'categories': ['doorOpen'],
             'blocker': 'A door is open.', 'note': None})
        assert led(result, 'device') is None

    def test_no_device_status_at_all_produces_no_led(self):
        result = diag.build_scanner_diagnostics('freezer', True, healthy_ps(), None)
        assert led(result, 'device') is None

    def test_the_blocker_sentence_is_shown_verbatim(self):
        result = diag.build_scanner_diagnostics(
            'freezer', True, healthy_ps(),
            {'reachable': True, 'categories': [],
             'blocker': 'There is a paper jam. Clear it.', 'note': None})
        assert led(result, 'device')['detail'] == 'There is a paper jam. Clear it.'


class TestCompositionRoot:
    """server.scanner_diagnostics owns the scanners, the lock and the socket."""

    def test_the_rules_no_longer_live_in_server(self):
        assert diag.build_scanner_diagnostics.__module__ == 'hardware.scanner_diagnostics'
        assert server.build_scanner_diagnostics is diag.build_scanner_diagnostics

    def test_an_unknown_scanner_is_rejected_before_any_probe(self, monkeypatch):
        def boom(*a, **k):
            raise AssertionError('must not probe an unknown scanner')
        monkeypatch.setattr(server, '_airscan_ready', boom)
        monkeypatch.setattr(server, '_wsl_interop_socket', boom)
        result = server.scanner_diagnostics('nope')
        assert result['overall'] == 'bad'
        assert result['error'] == 'Unknown scanner: nope'

    def test_a_healthy_airscan_scanner_never_reaches_windows(self, monkeypatch):
        def boom(*a, **k):
            raise AssertionError('AirScan answered; Windows must not be asked')
        monkeypatch.setattr(server, '_airscan_ready', lambda cfg: True)
        monkeypatch.setattr(server, '_wsl_interop_socket', lambda: '/run/WSL/x')
        monkeypatch.setattr(server, '_run_scanner_diag_ps', boom)
        monkeypatch.setattr(server, 'read_deskjet_device_status',
                            lambda: {'reachable': True, 'categories': [],
                                     'blocker': None, 'note': None})
        assert server.scanner_diagnostics('freezer')['overall'] == 'ok'

    def test_it_hands_the_probe_the_servers_scan_tools_dir(self, monkeypatch):
        seen = {}
        monkeypatch.setattr(server, '_airscan_ready', lambda cfg: False)
        monkeypatch.setattr(server, '_wsl_interop_socket', lambda: '/run/WSL/x')
        monkeypatch.setattr(server, '_run_scanner_diag_ps',
                            lambda cfg, interop, tools, skip_wia=False:
                            seen.update(cfg=cfg, interop=interop, tools=tools,
                                        skip_wia=skip_wia) or healthy_ps())
        server.scanner_diagnostics('window')
        assert seen['tools'] == server.SCAN_TOOLS_DIR
        assert seen['interop'] == '/run/WSL/x'
        assert seen['cfg'] is server.SCANNERS['window']

    def test_no_interop_skips_the_windows_probe_but_still_answers(self, monkeypatch):
        def boom(*a, **k):
            raise AssertionError('no socket; must not launch powershell')
        monkeypatch.setattr(server, '_airscan_ready', lambda cfg: False)
        monkeypatch.setattr(server, '_wsl_interop_socket', lambda: None)
        monkeypatch.setattr(server, '_run_scanner_diag_ps', boom)
        result = server.scanner_diagnostics('window')
        assert led(result, 'bridge')['state'] == 'bad'

    def test_a_scan_in_progress_skips_wia_instead_of_interfering(self, monkeypatch):
        """Holding the lock is a real scan: probe with -SkipWia, never contend."""
        seen = {}
        monkeypatch.setattr(server, '_airscan_ready', lambda cfg: False)
        monkeypatch.setattr(server, '_wsl_interop_socket', lambda: '/run/WSL/x')
        monkeypatch.setattr(server, '_run_scanner_diag_ps',
                            lambda cfg, i, t, skip_wia=False:
                            seen.update(skip_wia=skip_wia) or {'wia': 'skipped'})
        monkeypatch.setattr(server, 'SCANNER_DIAG_LOCK_WAIT_SEC', 0.01)
        server._SCAN_LOCK.acquire()
        try:
            server.scanner_diagnostics('window')
        finally:
            server._SCAN_LOCK.release()
        assert seen['skip_wia'] is True

    def test_the_lock_is_released_after_a_normal_probe(self, monkeypatch):
        monkeypatch.setattr(server, '_airscan_ready', lambda cfg: False)
        monkeypatch.setattr(server, '_wsl_interop_socket', lambda: '/run/WSL/x')
        monkeypatch.setattr(server, '_run_scanner_diag_ps',
                            lambda *a, **k: healthy_ps())
        server.scanner_diagnostics('window')
        assert server._SCAN_LOCK.acquire(timeout=0.5)
        server._SCAN_LOCK.release()

    def test_the_lock_is_released_even_when_the_probe_raises(self, monkeypatch):
        """A leaked scan lock wedges every later scan on the box."""
        monkeypatch.setattr(server, '_airscan_ready', lambda cfg: False)
        monkeypatch.setattr(server, '_wsl_interop_socket', lambda: '/run/WSL/x')
        def boom(*a, **k):
            raise RuntimeError('probe exploded')
        monkeypatch.setattr(server, '_run_scanner_diag_ps', boom)
        with pytest.raises(RuntimeError):
            server.scanner_diagnostics('window')
        assert server._SCAN_LOCK.acquire(timeout=0.5)
        server._SCAN_LOCK.release()

    def test_only_the_freezer_asks_the_deskjet_how_it_is(self, monkeypatch):
        asked = []
        monkeypatch.setattr(server, '_airscan_ready', lambda cfg: True)
        monkeypatch.setattr(server, '_wsl_interop_socket', lambda: None)
        monkeypatch.setattr(server, 'read_deskjet_device_status',
                            lambda: asked.append(1) or {'reachable': True,
                                                        'categories': [],
                                                        'blocker': None,
                                                        'note': None})
        server.scanner_diagnostics('window')
        assert asked == []
        server.scanner_diagnostics('freezer')
        assert asked == [1]

    def test_the_scanner_key_travels_into_the_snapshot(self, monkeypatch):
        monkeypatch.setattr(server, '_airscan_ready', lambda cfg: True)
        monkeypatch.setattr(server, '_wsl_interop_socket', lambda: None)
        monkeypatch.setattr(server, 'read_deskjet_device_status',
                            lambda: {'reachable': True, 'categories': [],
                                     'blocker': None, 'note': None})
        assert server.scanner_diagnostics('freezer')['scanner'] == 'freezer'
