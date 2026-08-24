"""The DeskJet repair, now that its Windows access is an injected seam.

`tests/test_server.py` already covers the repair end to end through
`server.fix_deskjet_printer`, and those tests passing unchanged is most of the
evidence the move to hardware/printer.py was faithful. What they could not
reach is the seam itself: the module now takes the interop lookup as a
callable, and the whole reason it is a callable rather than a path is that
server.py must be able to swap the lookup after import. Nothing raises when
that binding is wrong -- the repair simply reports "needs Windows access" on a
box that has it, or shells out with a dead socket -- so it is pinned here.

Also pinned: the split between what Windows thinks and what the printer says.
Windows' PrinterStatus on this RAW port has SNMP off and reads "Normal"
forever, which is how "Printer fixed." was once shown for a DeskJet that had
been out of paper the whole time.
"""
import io
import subprocess

import pytest

import server
from hardware import printer


STATUS_XML = (
    '<?xml version="1.0"?>'
    '<psdyn:ProductStatusDyn xmlns:psdyn="http://www.hp.com/schemas/imaging/con/ledm/productstatusdyn/2007/10/31"'
    ' xmlns:pscat="http://www.hp.com/schemas/imaging/con/ledm/productstatuscategories/2007/10/31">'
    '{rows}'
    '</psdyn:ProductStatusDyn>'
)


def status_payload(*categories):
    rows = ''.join(f'<pscat:StatusCategory>{c}</pscat:StatusCategory>'
                   for c in categories)
    return STATUS_XML.format(rows=rows).encode()


def opener_for(*categories):
    """An injected urlopen that answers with the given LEDM categories."""
    def opener(url, timeout=None):
        return io.BytesIO(status_payload(*categories))
    return opener


class FakeCompleted:
    def __init__(self, stdout='', stderr='', returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def runner_for(stdout='{"ok":true,"status":"Normal","port":"IP_10.0.0.243"}',
               stderr='', returncode=0):
    calls = []

    def runner(args, **kwargs):
        calls.append((args, kwargs))
        return FakeCompleted(stdout, stderr, returncode)
    runner.calls = calls
    return runner


def healthy():
    return {'reachable': True, 'categories': [], 'blocker': None, 'note': None}


class TestInteropIsInjected:
    """The socket lookup arrives as a callable and is consulted per repair."""

    def test_no_socket_reports_that_windows_is_out_of_reach(self):
        result = printer.fix_deskjet_printer(
            lambda: None, runner=runner_for(), device_status=healthy)
        assert result['ok'] is False
        assert 'Windows access' in result['text']

    def test_no_socket_never_shells_out(self):
        runner = runner_for()
        printer.fix_deskjet_printer(
            lambda: None, runner=runner, device_status=healthy)
        assert runner.calls == []

    def test_the_socket_is_read_at_repair_time_not_at_call_time(self):
        """A lookup whose answer changes must be honoured on the second call."""
        answers = iter([None, '/run/WSL/9_interop'])
        lookup = lambda: next(answers)
        runner = runner_for()
        first = printer.fix_deskjet_printer(
            lookup, runner=runner, device_status=healthy)
        second = printer.fix_deskjet_printer(
            lookup, runner=runner, device_status=healthy)
        assert first['ok'] is False and 'Windows access' in first['text']
        assert second['ok'] is True

    def test_the_socket_reaches_the_subprocess_environment(self):
        runner = runner_for()
        printer.fix_deskjet_printer(
            lambda: '/run/WSL/7_interop', runner=runner, device_status=healthy)
        _args, kwargs = runner.calls[0]
        assert kwargs['env']['WSL_INTEROP'] == '/run/WSL/7_interop'

    def test_the_repair_does_not_mutate_the_process_environment(self, monkeypatch):
        monkeypatch.delenv('WSL_INTEROP', raising=False)
        printer.fix_deskjet_printer(
            lambda: '/run/WSL/7_interop', runner=runner_for(),
            device_status=healthy)
        import os
        assert 'WSL_INTEROP' not in os.environ

    def test_a_blocker_is_named_even_with_no_windows_access(self):
        """Far more actionable than telling the operator to open a WSL window."""
        result = printer.fix_deskjet_printer(
            lambda: None, runner=runner_for(),
            device_status=lambda: {'reachable': True, 'categories': ['jamInPrinter'],
                                   'blocker': 'There is a paper jam.', 'note': None})
        assert result == {'ok': False, 'text': 'There is a paper jam.'}

    def test_a_lookup_that_raises_is_not_swallowed(self):
        """A broken lookup is a bug in the caller, not a printer condition."""
        def boom():
            raise RuntimeError('interop probe exploded')
        with pytest.raises(RuntimeError):
            printer.fix_deskjet_printer(
                boom, runner=runner_for(), device_status=healthy)


class TestCompositionRoot:
    """server.fix_deskjet_printer wires this module's lookup, late."""

    def test_the_repair_no_longer_lives_in_server(self):
        assert printer.fix_deskjet_printer.__module__ == 'hardware.printer'
        assert server.read_deskjet_device_status.__module__ == 'hardware.printer'

    def test_the_factory_binds_the_lookup_late(self, monkeypatch):
        """Six existing tests replace server._wsl_interop_socket before calling.

        Binding the function object at import time would make every one of them
        silently exercise the real /run/WSL probe instead.
        """
        monkeypatch.setattr(server, '_wsl_interop_socket',
                            lambda: '/run/WSL/late_interop')
        runner = runner_for()
        server.fix_deskjet_printer(runner=runner, device_status=healthy)
        _args, kwargs = runner.calls[0]
        assert kwargs['env']['WSL_INTEROP'] == '/run/WSL/late_interop'

    def test_a_second_patch_wins_over_the_first(self, monkeypatch):
        monkeypatch.setattr(server, '_wsl_interop_socket', lambda: '/run/WSL/a')
        monkeypatch.setattr(server, '_wsl_interop_socket', lambda: '/run/WSL/b')
        runner = runner_for()
        server.fix_deskjet_printer(runner=runner, device_status=healthy)
        assert runner.calls[0][1]['env']['WSL_INTEROP'] == '/run/WSL/b'

    def test_the_powershell_binary_is_the_shared_one(self, monkeypatch):
        from hardware.wsl_interop import WINDOWS_POWERSHELL
        monkeypatch.setattr(server, '_wsl_interop_socket', lambda: '/run/WSL/x')
        runner = runner_for()
        server.fix_deskjet_printer(runner=runner, device_status=healthy)
        assert runner.calls[0][0][0] == WINDOWS_POWERSHELL
        assert server._WINDOWS_POWERSHELL == WINDOWS_POWERSHELL

    def test_default_device_status_is_the_modules_own_reader(self, monkeypatch):
        """Omitting device_status must ask the printer, not assume it is well."""
        seen = []
        monkeypatch.setattr(printer, 'read_deskjet_device_status',
                            lambda: seen.append(1) or healthy())
        printer.fix_deskjet_printer(lambda: '/run/WSL/x', runner=runner_for())
        assert seen == [1]


class TestDeviceStatusIsTheHonestSource:
    """Windows says Normal forever; the printer is asked instead."""

    def test_a_blocker_beats_a_normal_windows_status(self):
        result = printer.fix_deskjet_printer(
            lambda: '/run/WSL/x', runner=runner_for(),
            device_status=lambda: {'reachable': True, 'categories': ['doorOpen'],
                                   'blocker': 'A door or cover is open on the printer.',
                                   'note': None})
        assert result['ok'] is False
        assert 'Printer fixed' not in result['text']
        assert result['device_status'] == ['doorOpen']

    def test_a_blocker_sentence_is_lowercased_into_the_clause(self):
        result = printer.fix_deskjet_printer(
            lambda: '/run/WSL/x', runner=runner_for(),
            device_status=lambda: {'reachable': True, 'categories': [],
                                   'blocker': 'There is a paper jam.', 'note': None})
        assert result['text'].endswith('but there is a paper jam.')

    def test_a_silent_printer_is_never_reported_as_fixed(self):
        result = printer.fix_deskjet_printer(
            lambda: '/run/WSL/x', runner=runner_for(),
            device_status=lambda: {'reachable': False, 'categories': [],
                                   'blocker': None, 'note': None})
        assert result['ok'] is False
        assert 'did not answer' in result['text']

    def test_an_empty_tray_is_a_note_and_still_a_success(self):
        result = printer.fix_deskjet_printer(
            lambda: '/run/WSL/x', runner=runner_for(),
            device_status=lambda: {'reachable': True, 'categories': ['trayEmpty'],
                                   'blocker': None,
                                   'note': 'it is out of paper (printing only)'})
        assert result['ok'] is True
        assert 'ready to scan' in result['text']
        assert 'out of paper' in result['text']

    @pytest.mark.parametrize('stdout, expected', [
        ('', 'unreadable printer status'),
        ('not json at all', 'unreadable printer status'),
        ('{"ok":false,"status":"Offline","port":"IP_10.0.0.243"}', 'still Offline'),
    ])
    def test_windows_answers_that_cannot_be_trusted(self, stdout, expected):
        result = printer.fix_deskjet_printer(
            lambda: '/run/WSL/x', runner=runner_for(stdout=stdout),
            device_status=healthy)
        assert result['ok'] is False
        assert expected in result['text']

    def test_a_nonzero_exit_surfaces_stderr_and_is_capped(self):
        result = printer.fix_deskjet_printer(
            lambda: '/run/WSL/x',
            runner=runner_for(stderr='E' * 900, returncode=1),
            device_status=healthy)
        assert result['ok'] is False
        assert len(result['text']) == 500

    def test_a_timeout_is_reported_as_a_timeout(self):
        def runner(args, **kwargs):
            raise subprocess.TimeoutExpired(cmd='ps', timeout=35)
        result = printer.fix_deskjet_printer(
            lambda: '/run/WSL/x', runner=runner, device_status=healthy)
        assert result == {'ok': False, 'text': 'Printer repair timed out.'}

    def test_a_launch_failure_names_the_cause(self):
        def runner(args, **kwargs):
            raise FileNotFoundError('no powershell here')
        result = printer.fix_deskjet_printer(
            lambda: '/run/WSL/x', runner=runner, device_status=healthy)
        assert result['ok'] is False
        assert 'no powershell here' in result['text']

    def test_the_device_is_asked_only_after_the_queue_repair_ran(self):
        """Asking first would waste 8s of LAN timeout on an unreachable box."""
        order = []
        def runner(args, **kwargs):
            order.append('repair')
            return FakeCompleted('{"ok":true,"status":"Normal","port":"p"}')
        printer.fix_deskjet_printer(
            lambda: '/run/WSL/x', runner=runner,
            device_status=lambda: order.append('ask') or healthy())
        assert order == ['repair', 'ask']


class TestReadDeviceStatus:
    """The LEDM reader: a condition is a blocker, a note, or neither."""

    def test_a_door_open_is_device_wide(self):
        status = printer.read_deskjet_device_status(opener=opener_for('doorOpen'))
        assert status['reachable'] is True
        assert status['blocker'] == printer.DESKJET_BLOCKING_STATUS['dooropen']
        assert status['note'] is None

    def test_paper_is_print_only(self):
        status = printer.read_deskjet_device_status(opener=opener_for('trayEmpty'))
        assert status['blocker'] is None
        assert 'out of paper' in status['note']

    @pytest.mark.parametrize('category', [
        'DOOROPEN', 'doorOpen', 'DoorOpen', 'dooropen',
    ])
    def test_category_matching_ignores_case(self, category):
        status = printer.read_deskjet_device_status(opener=opener_for(category))
        assert status['blocker'] is not None

    def test_the_first_blocker_wins_and_a_note_still_surfaces(self):
        status = printer.read_deskjet_device_status(
            opener=opener_for('trayEmpty', 'mediaJam', 'doorOpen'))
        assert status['blocker'] == printer.DESKJET_BLOCKING_STATUS['mediajam']
        assert 'out of paper' in status['note']
        assert status['categories'] == ['trayEmpty', 'mediaJam', 'doorOpen']

    def test_a_ready_printer_has_neither(self):
        status = printer.read_deskjet_device_status(opener=opener_for('ready'))
        assert status == {'reachable': True, 'categories': ['ready'],
                          'blocker': None, 'note': None}

    def test_no_categories_at_all_is_still_reachable(self):
        status = printer.read_deskjet_device_status(opener=opener_for())
        assert status['reachable'] is True
        assert status['categories'] == []

    @pytest.mark.parametrize('body', [b'', b'<not-xml', b'{"json":"not xml"}'])
    def test_unparseable_answers_are_unknown_not_healthy(self, body):
        """`reachable: False` -- we cannot vouch for hardware we cannot read."""
        status = printer.read_deskjet_device_status(
            opener=lambda url, timeout=None: io.BytesIO(body))
        assert status == {'reachable': False, 'categories': [],
                          'blocker': None, 'note': None}

    def test_an_unreachable_printer_is_unknown_not_broken(self):
        def boom(url, timeout=None):
            raise OSError('no route to host')
        assert printer.read_deskjet_device_status(opener=boom)['reachable'] is False

    def test_the_reader_asks_the_printers_own_service(self):
        seen = {}
        def opener(url, timeout=None):
            seen['url'] = url
            seen['timeout'] = timeout
            return io.BytesIO(status_payload('ready'))
        printer.read_deskjet_device_status(opener=opener)
        assert seen['url'] == printer.DESKJET_STATUS_URL
        assert printer.DESKJET_PRINTER_IP in seen['url']
        assert seen['timeout'] == 8

    def test_namespaced_tags_are_matched_by_local_name(self):
        """ElementTree keeps `{ns}StatusCategory`; naive matching finds nothing."""
        assert printer._xml_localname('{http://example/x}StatusCategory') == 'StatusCategory'
        assert printer._xml_localname('StatusCategory') == 'StatusCategory'


class TestPowerShellScript:
    """The repair is the safe one: a port switch, never a driver change."""

    def script(self):
        runner = runner_for()
        printer.fix_deskjet_printer(
            lambda: '/run/WSL/x', runner=runner, device_status=healthy)
        return runner.calls[0][0][-1]

    def test_it_names_this_printer_and_its_ipv4_port(self):
        script = self.script()
        assert printer.DESKJET_PRINTER_NAME in script
        assert printer.DESKJET_PRINTER_IP in script
        assert printer.DESKJET_PRINTER_PORT in script

    def test_it_binds_the_existing_queue_rather_than_making_one(self):
        script = self.script()
        assert 'Set-Printer' in script
        assert 'Add-Printer ' not in script

    @pytest.mark.parametrize('destructive', [
        'Remove-Printer', 'Remove-PrinterDriver', 'Add-PrinterDriver',
        'Remove-PrintJob',
    ])
    def test_it_never_touches_drivers_or_queued_jobs(self, destructive):
        assert destructive not in self.script()

    def test_it_checks_the_raw_port_before_claiming_anything(self):
        assert 'Test-NetConnection' in self.script()
        assert '9100' in self.script()

    def test_it_runs_unelevated_friendly(self):
        """Spooler restart is best-effort: the port switch is the real repair."""
        script = self.script()
        assert 'Restart-Service Spooler' in script
        assert 'try {' in script

    def test_it_runs_without_a_profile_or_execution_policy(self):
        runner = runner_for()
        printer.fix_deskjet_printer(
            lambda: '/run/WSL/x', runner=runner, device_status=healthy)
        args = runner.calls[0][0]
        assert '-NoProfile' in args
        assert args[args.index('-ExecutionPolicy') + 1] == 'Bypass'
