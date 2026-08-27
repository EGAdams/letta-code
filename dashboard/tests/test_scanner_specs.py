"""`ScannerSpec`, and the silent mis-scans it makes unexpressible.

Round 13 of the server.py refactor (Registry). `SCANNERS` was a dict of dicts
in `server.py` with eight untyped string fields per scanner, several of which
have to agree with each other or with a PowerShell probe on another machine.

The golden literal below is what `server.py` carried at 75807d6b, inline so it
stays a real parity check rather than a restatement of the module under test.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from hardware import scanners
from hardware.scanners import SCANNER_SPECS, ScannerSpec

GOLDEN_SCANNERS = {
    'window': {
        'name': 'Window Scanner',
        'device': 'HPI297BEA (HP OfficeJet 8120e series)',
        'script': 'run_scan_window.sh',
        'output': 'window_scan.jpg',
        'namelike': 'HPI297BEA',
        'driver_match': 'OfficeJet 8120e',
        'airscan_device': 'airscan:e0:Window Scanner',
    },
    'freezer': {
        'name': 'Freezer Scanner',
        'device': 'HP063E28 (HP DeskJet 4100 series)',
        'script': 'run_scan_freezer.sh',
        'output': 'scan_freezer.jpg',
        'namelike': 'HP063E28',
        'driver_match': 'DeskJet 4100',
        'airscan_device': 'airscan:e1:Freezer Scanner',
    },
}


def _valid(**overrides) -> dict:
    base = dict(
        key='window', name='Window Scanner',
        device='HPI297BEA (HP OfficeJet 8120e series)',
        script='run_scan_window.sh', output='window_scan.jpg',
        namelike='HPI297BEA', driver_match='OfficeJet 8120e',
        airscan_device='airscan:e0:Window Scanner')
    base.update(overrides)
    return base


class TestGoldenParity:
    """The derived dict is what server.py always had, key for key, in order."""

    def test_the_derived_view_matches_the_literal(self):
        assert scanners.SCANNERS == GOLDEN_SCANNERS

    def test_the_scanner_order_is_unchanged(self):
        assert list(scanners.SCANNERS) == list(GOLDEN_SCANNERS)

    def test_each_spec_keeps_its_key_order(self):
        """`scanner_status` and the diagnostics builder iterate these dicts."""
        for key, golden in GOLDEN_SCANNERS.items():
            assert list(scanners.SCANNERS[key]) == list(golden)

    def test_server_serves_the_derived_view_under_the_historical_name(self):
        import server

        assert server.SCANNERS == GOLDEN_SCANNERS

    def test_the_dict_view_is_not_a_second_source(self):
        """Derived per spec, so it cannot drift — this is the whole point."""
        assert scanners.SCANNERS == {s.key: s.as_config() for s in SCANNER_SPECS}


class TestTheMatchersDescribeTheDeviceThatScans:
    """The defect worth the model: diagnostics probing the other scanner."""

    def test_the_live_specs_agree_with_themselves(self):
        for spec in SCANNER_SPECS:
            assert spec.namelike in spec.device
            assert spec.driver_match in spec.device
            assert spec.airscan_device.endswith(spec.name)

    def test_a_namelike_from_the_other_scanner_is_refused(self):
        """Reachable today: the Freezer's WIA id in the Window's entry made
        scanner_diag.ps1 report on the Freezer while run_scan_window.sh drove
        the Window — a green Diagnostics tab for a scanner that cannot scan."""
        with pytest.raises(ValidationError, match='does not appear in device'):
            ScannerSpec(**_valid(namelike='HP063E28'))

    def test_a_driver_match_for_the_wrong_model_is_refused(self):
        with pytest.raises(ValidationError, match='does not appear in device'):
            ScannerSpec(**_valid(driver_match='DeskJet 4100'))

    def test_an_airscan_device_naming_the_other_scanner_is_refused(self):
        with pytest.raises(ValidationError, match='does not name'):
            ScannerSpec(**_valid(airscan_device='airscan:e1:Freezer Scanner'))


class TestOutputAndScriptAreSafeToJoinAndRun:
    def test_an_output_with_a_path_separator_is_refused(self):
        """`output` is os.path.join'd to SCAN_TOOLS_DIR by four call sites and
        by ScannerPort.image_path; an absolute path would replace the root."""
        with pytest.raises(ValidationError, match='bare filename'):
            ScannerSpec(**_valid(output='/etc/passwd'))

    def test_an_output_that_climbs_out_of_the_tools_dir_is_refused(self):
        with pytest.raises(ValidationError, match='bare filename'):
            ScannerSpec(**_valid(output='../window_scan.jpg'))

    def test_a_script_that_is_not_a_shell_script_is_refused(self):
        with pytest.raises(ValidationError, match='not a .sh script'):
            ScannerSpec(**_valid(script='run_scan_window'))

    def test_a_blank_script_is_refused_rather_than_becoming_not_configured(self):
        """`run_scanner` answers 'not_configured' for a falsy script. That is
        the recovery path for a scanner nobody has wired yet — not a place to
        land because the entry was typed with a space in it."""
        with pytest.raises(ValidationError, match='must not be blank'):
            ScannerSpec(**_valid(script='   '))


class TestTwoScannersCannotCollide:
    def test_the_live_specs_share_nothing(self):
        scanners._check_no_two_scanners_collide()

    def test_a_shared_output_is_refused(self, monkeypatch):
        """The failure this prevents: the Freezer's intake page renders the
        Window's last scan, and dispatches that image to Mazda. There is an
        older assertion of this in tests/test_server.py; here it becomes an
        invariant of the registry rather than a fact about two entries."""
        clash = ScannerSpec(**_valid(
            key='freezer', name='Freezer Scanner',
            device='HP063E28 (HP DeskJet 4100 series)',
            script='run_scan_freezer.sh',
            output='window_scan.jpg',            # the Window's file
            namelike='HP063E28', driver_match='DeskJet 4100',
            airscan_device='airscan:e1:Freezer Scanner'))
        monkeypatch.setattr(
            scanners, 'SCANNER_SPECS', (SCANNER_SPECS[0], clash))
        with pytest.raises(ValueError, match='two scanners share a output'):
            scanners._check_no_two_scanners_collide()

    def test_a_shared_key_is_refused(self, monkeypatch):
        monkeypatch.setattr(
            scanners, 'SCANNER_SPECS', (SCANNER_SPECS[0], SCANNER_SPECS[0]))
        with pytest.raises(ValueError, match='two scanners share a key'):
            scanners._check_no_two_scanners_collide()


class TestTheModelIsStrict:
    def test_a_misspelled_field_is_refused_not_ignored(self):
        """As a dict, `'namelike_'` was simply a scanner with no namelike."""
        bad = _valid()
        bad['name_like'] = bad.pop('namelike')
        with pytest.raises(ValidationError):
            ScannerSpec(**bad)

    def test_a_missing_field_is_refused(self):
        bad = _valid()
        del bad['airscan_device']
        with pytest.raises(ValidationError):
            ScannerSpec(**bad)

    def test_it_is_frozen(self):
        with pytest.raises(ValidationError):
            SCANNER_SPECS[0].output = 'other.jpg'


class TestLookups:
    def test_by_key_finds_each_scanner(self):
        assert scanners.by_key('freezer').name == 'Freezer Scanner'

    def test_by_key_is_none_for_an_unknown_scanner(self):
        assert scanners.by_key('garage') is None

    def test_image_path_joins_the_tools_dir(self):
        assert scanners.image_path('window', '/tools') == '/tools/window_scan.jpg'

    def test_image_path_is_none_for_an_unknown_scanner(self):
        assert scanners.image_path('garage', '/tools') is None

    def test_image_path_agrees_with_the_scanner_port(self):
        """Two readers of the same fact; they must not diverge."""
        import server
        from http_app.registry import current_ports

        for key in scanners.SCANNERS:
            assert (current_ports().scanner.image_path(key)
                    == scanners.image_path(key, server.SCAN_TOOLS_DIR))
