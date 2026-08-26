"""The typed shapes behind the PC Monitor tab, and the seams under them.

`PC_MONITORS` and the metric rows were dicts assembled by hand. The rows in
particular carried `level` and `alert` as two independently-computed fields at
three call sites, which is one edit away from a bar that turns red without the
tab blinking. `PcMetric` derives `alert` from `level`, so the two cannot
disagree.

The payloads are compared against the exact dicts the old literals produced.
The frontend reads these keys directly, so a rename here is invisible in Python
and visible only as a blank bar in a browser.

`tests/test_server.py` already covers the collector's behaviour end to end --
the shell snippet, the SSH path, the stale-last-good fallback. What is pinned
here is the typing, the alert arithmetic, and the patch targets.
"""
import pytest
from pydantic import ValidationError

import server
from hardware.wsl_interop import WINDOWS_POWERSHELL
from monitoring import pc_metrics as pc
from monitoring.pc_metrics import PcMetric, PcMonitor

#: Enough collector output to produce all three bars. 8 GB total / 2 GB free,
#: a 100 GB disk with 50 GB free, and one busy NIC beside loopback.
SAMPLE = """===MEM===
MemTotal: 8388608 kB
MemAvailable: 2097152 kB
===DISK===
Filesystem 1024-blocks Used Available Capacity Mounted on
C:\\ 104857600 52428800 52428800 50% /mnt/c
===NET===
Inter-|   Receive                    |  Transmit
 face |bytes    packets errs drop fifo frame compressed multicast|bytes
    lo: 999999 10 0 0 0 0 0 0 999999 10 0 0 0 0 0 0
  eth0: 1000000 10 0 0 0 0 0 0 2000000 20 0 0 0 0 0 0
"""

THRESHOLDS = {'ram': 90.0, 'disk_free_warn_gb': 5.0,
              'disk_free_crit_gb': 2.0, 'net': 80.0}


class TestTheMonitorRegistry:
    def test_every_monitor_parses(self):
        assert set(pc.PC_MONITORS) == {'win11', 'win10', 'moms46'}

    def test_the_two_windows_boxes_read_memory_through_powershell(self):
        """Not a style choice: /proc/meminfo inside WSL reports the VM's
        memory limit, which is a real number about the wrong machine."""
        for key in ('win11', 'win10'):
            assert pc.PC_MONITORS[key].memory_source == 'windows'

    def test_the_linux_box_defaults_to_proc_meminfo(self):
        assert pc.PC_MONITORS['moms46'].memory_source == 'linux'

    def test_an_unknown_memory_source_is_rejected(self):
        """The failure it prevents is silent: an unrecognised value would have
        fallen through to the Linux branch and reported the WSL VM's RAM."""
        with pytest.raises(ValidationError):
            PcMonitor(label='x', memory_source='wmic')

    def test_a_misspelled_field_is_rejected_rather_than_ignored(self):
        with pytest.raises(ValidationError):
            PcMonitor(label='x', hostname='somewhere')

    def test_a_monitor_cannot_be_mutated(self):
        with pytest.raises(ValidationError):
            pc.PC_MONITORS['win11'].host = 'somewhere-else'

    def test_this_box_has_no_host_and_the_others_do(self):
        assert pc.PC_MONITORS['win11'].host is None
        assert pc.PC_MONITORS['win10'].host and pc.PC_MONITORS['moms46'].host

    def test_the_two_remote_hosts_come_from_the_shared_table(self):
        """One definition of each machine's address, in hosts.py. Three
        modules used to read the same env var with their own fallback."""
        from hosts import LETTA_DOCKER_HOST, R46_SSH_HOST
        assert pc.PC_MONITORS['win10'].host == LETTA_DOCKER_HOST
        assert pc.PC_MONITORS['moms46'].host == R46_SSH_HOST


class TestTheCollectorCommand:
    def test_a_windows_box_gets_the_powershell_memory_query(self):
        cmd = pc.pc_metrics_collector_command(pc.PC_MONITORS['win11'])
        assert WINDOWS_POWERSHELL in cmd
        assert 'Win32_OperatingSystem' in cmd

    def test_a_linux_box_reads_proc_meminfo(self):
        cmd = pc.pc_metrics_collector_command(pc.PC_MONITORS['moms46'])
        assert '/proc/meminfo' in cmd
        assert WINDOWS_POWERSHELL not in cmd

    def test_there_is_one_definition_of_the_powershell_path(self):
        """It used to be spelled out twice, here and in the interop code. Two
        copies of an absolute path is one Windows update away from a bug that
        only shows on one tab."""
        import inspect
        assert 'System32' not in inspect.getsource(pc)

    def test_disk_prefers_the_real_c_drive_and_falls_back(self):
        cmd = pc.pc_metrics_collector_command(pc.PC_MONITORS['win11'])
        assert 'df -kP /mnt/c' in cmd and 'df -kP /' in cmd

    def test_all_three_sections_are_requested_in_order(self):
        cmd = pc.pc_metrics_collector_command(pc.PC_MONITORS['moms46'])
        assert cmd.index('===MEM===') < cmd.index('===DISK===') < cmd.index('===NET===')


class TestMetricRowPayload:
    def test_a_row_dumps_the_seven_keys_the_card_reads_in_order(self):
        got = PcMetric(key='ram', label='RAM Usage', percent=70.7,
                       text='11.2 / 15.8 GB', tip='Alerts at 90%').to_payload()
        assert list(got) == ['key', 'label', 'percent', 'text', 'level',
                             'alert', 'tip']
        assert got == {'key': 'ram', 'label': 'RAM Usage', 'percent': 70.7,
                       'text': '11.2 / 15.8 GB', 'level': 'ok', 'alert': False,
                       'tip': 'Alerts at 90%'}

    @pytest.mark.parametrize('level, alert', [
        ('ok', False), ('warn', True), ('crit', True)])
    def test_alert_is_derived_from_level_and_cannot_disagree_with_it(
            self, level, alert):
        """The bar's colour and the tab's blink came from two separately
        computed fields at three call sites."""
        row = PcMetric(key='disk', label='Hard Drive Usage', percent=1.0,
                       text='x', level=level)
        assert row.alert is alert and row.to_payload()['alert'] is alert

    def test_an_unknown_level_is_rejected(self):
        with pytest.raises(ValidationError):
            PcMetric(key='ram', label='x', percent=1.0, text='x', level='red')

    def test_an_unknown_metric_key_is_rejected(self):
        """The frontend draws one bar per known key; an unknown one would be
        collected, serialised, and then silently not rendered."""
        with pytest.raises(ValidationError):
            PcMetric(key='gpu', label='x', percent=1.0, text='x')


class TestTheBarsTheyProduce:
    def parse(self, text=SAMPLE):
        return pc.parse_pc_metrics_output(text)

    def build(self, parsed=None, prev=None, now=100.0, th=None):
        return pc.build_pc_metrics(parsed if parsed is not None else self.parse(),
                                   prev, now, thresholds=th or THRESHOLDS)

    def test_the_three_bars_come_out_in_order(self):
        metrics, _ = self.build()
        assert [m['key'] for m in metrics] == ['ram', 'disk', 'net']

    def test_ram_reports_used_not_available(self):
        metrics, _ = self.build()
        ram = metrics[0]
        assert ram['percent'] == 75.0            # 6 GB used of 8
        assert ram['text'] == '6.0 / 8.0 GB'

    def test_ram_alerts_on_percent(self):
        metrics, _ = self.build(th=dict(THRESHOLDS, ram=70.0))
        assert metrics[0]['level'] == 'warn' and metrics[0]['alert'] is True

    def test_disk_alerts_on_free_gigabytes_not_percent(self):
        """A 90%-full 4 TB disk has 400 GB free and is fine; a 90%-full 20 GB
        disk has 2 GB free and is not. Percent cannot tell them apart."""
        metrics, _ = self.build()
        disk = metrics[1]
        assert disk['percent'] == 50.0 and disk['level'] == 'ok'

    @pytest.mark.parametrize('free_kb, level', [
        (50 * 1024 * 1024, 'ok'),
        (4 * 1024 * 1024, 'warn'),      # under the 5 GB warn line
        (2 * 1024 * 1024, 'crit'),      # at the 2 GB crit line -- inclusive
        (1024 * 1024, 'crit'),
    ])
    def test_the_disk_ladder(self, free_kb, level):
        parsed = dict(self.parse(), disk_avail_kb=free_kb)
        metrics, _ = self.build(parsed)
        assert metrics[1]['level'] == level

    def test_the_c_drive_is_named_in_the_text_when_that_is_what_was_sampled(self):
        metrics, _ = self.build()
        assert metrics[1]['text'].startswith('C: ')

    def test_a_non_wsl_box_reports_the_root_filesystem_unlabelled(self):
        parsed = dict(self.parse(), disk_mount='/')
        metrics, _ = self.build(parsed)
        assert not metrics[1]['text'].startswith('C: ')

    def test_the_first_network_sample_says_it_is_measuring(self):
        """Traffic is a rate; one cumulative counter is not a rate. Showing
        0% would read as an idle link."""
        metrics, sample = self.build(prev=None)
        assert metrics[2]['text'] == 'measuring…'
        assert sample == (100.0, 3_000_000)

    def test_the_second_sample_reports_a_rate(self):
        metrics, _ = self.build(prev=(90.0, 2_000_000), now=100.0)
        # 1 MB in 10s = 0.8 Mbit/s against a 100 Mbit/s full-scale bar.
        assert metrics[2]['text'].startswith('0.80 Mbit/s')
        assert metrics[2]['percent'] == 0.8

    def test_a_counter_reset_falls_back_to_measuring_rather_than_a_negative_rate(self):
        """Interface counters reset on reboot or when a NIC is recreated. The
        guard is `total >= prev`, and without it the bar goes backwards."""
        metrics, _ = self.build(prev=(90.0, 9_000_000), now=100.0)
        assert metrics[2]['text'] == 'measuring…'

    def test_two_samples_at_the_same_instant_do_not_divide_by_zero(self):
        metrics, _ = self.build(prev=(100.0, 1_000_000), now=100.0)
        assert metrics[2]['text'] == 'measuring…'

    def test_the_rate_bar_is_clamped_at_full_scale(self):
        metrics, _ = pc.build_pc_metrics(
            self.parse(), (99.0, 0), 100.0,
            thresholds=THRESHOLDS, net_capacity_mbps=1.0)
        assert metrics[2]['percent'] == 100.0

    def test_a_machine_that_reported_no_memory_omits_the_bar_rather_than_showing_zero(self):
        parsed = dict(self.parse(), mem_total_kb=None)
        metrics, _ = self.build(parsed)
        assert [m['key'] for m in metrics] == ['disk', 'net']


class TestParsingTheCollectorOutput:
    def test_loopback_is_excluded_from_the_traffic_total(self):
        """lo carries every local request the dashboard itself makes; counting
        it would make the box look busy whenever anyone opened the page."""
        parsed = pc.parse_pc_metrics_output(SAMPLE)
        assert parsed['net_rx_bytes'] == 1_000_000
        assert parsed['net_tx_bytes'] == 2_000_000

    def test_the_mount_that_was_actually_sampled_is_recorded(self):
        assert pc.parse_pc_metrics_output(SAMPLE)['disk_mount'] == '/mnt/c'

    def test_empty_output_parses_to_nothing_rather_than_raising(self):
        parsed = pc.parse_pc_metrics_output('')
        assert parsed['mem_total_kb'] is None
        assert parsed['net_rx_bytes'] == 0

    def test_a_truncated_transfer_yields_no_bars_instead_of_wrong_ones(self):
        parsed = pc.parse_pc_metrics_output('===MEM===\nMemTotal: 8388608 kB\n')
        metrics, _ = pc.build_pc_metrics(parsed, None, 100.0, thresholds=THRESHOLDS)
        assert [m['key'] for m in metrics] == ['ram', 'net']
        assert metrics[0]['text'] == '8.0 / 8.0 GB'   # avail unknown => all used


class TestTheRollup:
    def test_an_unknown_pc_is_named_rather_than_crashing(self):
        out = pc.pc_metrics('not-a-pc')
        assert out['ok'] is False and 'not-a-pc' in out['error']
        assert out['alert'] is False

    def test_crit_beats_warn_in_the_tab_colour(self, monkeypatch):
        parsed = dict(pc.parse_pc_metrics_output(SAMPLE),
                      disk_avail_kb=1024 * 1024)          # 1 GB free -> crit
        metrics, _ = pc.build_pc_metrics(
            parsed, None, 100.0, thresholds=dict(THRESHOLDS, ram=70.0))
        levels = [m['level'] for m in metrics]
        assert 'warn' in levels and 'crit' in levels


class TestThePatchTargetTrap:
    """The caches and thresholds live on this module, not on `server`.

    server.py re-exports the names, but the collector closes over its own
    module globals. Patching the copy on `server` isolates nothing while
    looking exactly like it does -- which is what four tests in
    test_server.py were doing until this module moved out.
    """

    @pytest.mark.parametrize('name', [
        '_pc_metrics_cache', '_pc_net_last', '_pc_last_good',
        'PC_ALERT_THRESHOLDS', 'PC_NET_CAPACITY_MBPS',
    ])
    def test_the_global_lives_on_its_own_module(self, name):
        assert name in vars(pc)

    def test_patching_thresholds_on_server_does_not_change_the_verdict(
            self, monkeypatch):
        monkeypatch.setattr(server, 'PC_ALERT_THRESHOLDS',
                            dict(THRESHOLDS, ram=1.0))
        metrics, _ = pc.build_pc_metrics(
            pc.parse_pc_metrics_output(SAMPLE), None, 100.0)
        assert metrics[0]['level'] == 'ok'      # the real 90% threshold applied


class TestServerReExports:
    @pytest.mark.parametrize('name', [
        'build_pc_metrics', 'parse_pc_metrics_output',
        'pc_metrics_collector_command',
        'PC_ALERT_THRESHOLDS', 'PC_NET_CAPACITY_MBPS', 'PC_METRICS_CACHE_TTL',
    ])
    def test_the_historical_name_still_resolves(self, name):
        assert getattr(server, name) is getattr(pc, name)

    @pytest.mark.parametrize('name', ['pc_metrics', 'PC_MONITORS'])
    def test_the_names_only_the_pc_tab_used_are_gone(self, name):
        """Round 12: GET /api/pc-metrics and /api/pc-monitors import these from
        monitoring.pc_metrics, so server.py held them for nobody. Patch here,
        not there — `monkeypatch.setattr(server, 'pc_metrics', ...)` would now
        raise, which is the friendly failure; before round 12 it silently
        patched a name the route had already read."""
        assert not hasattr(server, name)
