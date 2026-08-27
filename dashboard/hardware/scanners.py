"""The two HP scanners, as typed specs the legacy `SCANNERS` dict derives from.

`server.py` carried this as a hand-maintained dict of dicts. Nothing checked it,
and every field in it is a string something else has to match:

* `script` selects the device **by name**, not "first device found" — WIA
  enumeration order is unstable (the busy Freezer often enumerates first), so
  the old first-device script kept grabbing the wrong scanner.
* `namelike` matches the WIA device Name in `scanner_diag.ps1`; `driver_match`
  matches the PnP Image-class FriendlyName, which is a *different* string (the
  model, not the WIA id).
* `output` is joined to `SCAN_TOOLS_DIR` to find the last image.
* `airscan_device` is the sane-airscan device string.

Get one of those wrong and the failure is silent: diagnostics go green against
one scanner while scans come off the other, or the page shows a stale image, or
nothing happens at all. `ScannerSpec` turns each of those into a
`ValidationError` at import.

The `SCANNERS` mapping below is a **derived view** — same keys, same nested
dicts, same order — so the sixteen call sites in `server.py`, the diagnostics
module and the tests that monkeypatch it are unchanged. `ScannerPort` in
`http_app/registry.py` reads the specs instead; that adapter is the only code
outside this module that needed to know a spec has an `output` key, which is why
round 12's port made this round cheap.
"""

from __future__ import annotations

import os

from pydantic import field_validator, model_validator

from contracts import StrictModel


class ScannerSpec(StrictModel):
    """One scanner's identity, its scan script, and its diagnostics matchers.

    Every field is required. There is no sensible default for any of them: a
    scanner with a missing `namelike` does not fall back to something safe, it
    makes the diagnostics tab describe a different device than the one that
    scans.
    """

    key: str
    name: str
    device: str
    script: str
    output: str
    namelike: str
    driver_match: str
    airscan_device: str

    @field_validator('key', 'name', 'device', 'script', 'output', 'namelike',
                     'driver_match', 'airscan_device')
    @classmethod
    def _not_blank(cls, value: str) -> str:
        # min_length=1 is not "not blank" when the consumer strips.
        if not value.strip():
            raise ValueError('must not be blank')
        return value

    @field_validator('output')
    @classmethod
    def _is_a_bare_filename(cls, value: str) -> str:
        """`output` is joined to SCAN_TOOLS_DIR; a path would escape it."""
        if os.path.basename(value) != value or value in ('.', '..'):
            raise ValueError(
                f'{value!r} must be a bare filename, not a path — it is joined '
                'to SCAN_TOOLS_DIR to locate the last scan')
        return value

    @field_validator('script')
    @classmethod
    def _is_a_shell_script(cls, value: str) -> str:
        if os.path.basename(value) != value:
            raise ValueError(f'{value!r} must be a bare filename')
        if not value.endswith('.sh'):
            raise ValueError(f'{value!r} is not a .sh script')
        return value

    @model_validator(mode='after')
    def _the_matchers_describe_this_device(self) -> ScannerSpec:
        """The diagnostics matchers must point at the device that scans.

        This is the defect worth the whole model. `namelike` and `driver_match`
        are consumed by `scanner_diag.ps1` on the Windows side, where a miss is
        reported as "device not found" — or worse, a near-miss matches the
        *other* HP on the same box and the Diagnostics tab goes green for a
        scanner that cannot scan.
        """
        if self.namelike not in self.device:
            raise ValueError(
                f'namelike {self.namelike!r} does not appear in device '
                f'{self.device!r} — diagnostics would probe different hardware '
                'than the scan script drives')
        if self.driver_match not in self.device:
            raise ValueError(
                f'driver_match {self.driver_match!r} does not appear in device '
                f'{self.device!r}')
        if not self.airscan_device.endswith(self.name):
            raise ValueError(
                f'airscan_device {self.airscan_device!r} does not name '
                f'{self.name!r}')
        return self

    def as_config(self) -> dict:
        """The legacy dict shape, key for key.

        `server.py` and `hardware/scanner_diagnostics.py` still pass these
        around as plain dicts. Keeping one function that produces that shape
        means the dict cannot drift from the spec.
        """
        return {
            'name': self.name,
            'device': self.device,
            'script': self.script,
            'output': self.output,
            'namelike': self.namelike,
            'driver_match': self.driver_match,
            'airscan_device': self.airscan_device,
        }


SCANNER_SPECS: tuple[ScannerSpec, ...] = (
    ScannerSpec(
        key='window',
        name='Window Scanner',
        device='HPI297BEA (HP OfficeJet 8120e series)',
        script='run_scan_window.sh',   # selects HPI297BEA by name
        output='window_scan.jpg',
        namelike='HPI297BEA',
        driver_match='OfficeJet 8120e',
        airscan_device='airscan:e0:Window Scanner',
    ),
    # The Freezer (HP063E28) is the non-default WIA device and is notorious for
    # "WIA device is busy" until power-cycled.
    ScannerSpec(
        key='freezer',
        name='Freezer Scanner',
        device='HP063E28 (HP DeskJet 4100 series)',
        script='run_scan_freezer.sh',  # selects HP063E28 by name (non-default)
        output='scan_freezer.jpg',
        namelike='HP063E28',
        driver_match='DeskJet 4100',
        airscan_device='airscan:e1:Freezer Scanner',
    ),
)


def _check_no_two_scanners_collide() -> None:
    """Two scanners sharing any identifying string is a silent mix-up.

    `output` is the one with a test already written against it
    (`tests/test_server.py`): two scanners writing to one file means the
    Freezer's page renders the Window's last scan, and intake dispatches the
    wrong image to Mazda.
    """
    for field in ('key', 'name', 'device', 'script', 'output', 'namelike',
                  'airscan_device'):
        values = [getattr(s, field) for s in SCANNER_SPECS]
        if len(set(values)) != len(values):
            raise ValueError(f'two scanners share a {field}: {values}')


_check_no_two_scanners_collide()


# The legacy view: key -> the same nested dict server.py always had, in the same
# order. Derived, so it cannot disagree with the specs above.
SCANNERS: dict[str, dict] = {s.key: s.as_config() for s in SCANNER_SPECS}


def by_key(key: str) -> ScannerSpec | None:
    """The spec for `key`, or None for an unknown scanner."""
    return next((s for s in SCANNER_SPECS if s.key == key), None)


def image_path(key: str, scan_tools_dir: str) -> str | None:
    """Where `key`'s last scan was written, or None for an unknown scanner.

    Returns the configured path whether or not a file is there yet — deciding
    what a missing file means is the caller's business.
    """
    spec = by_key(key)
    return os.path.join(scan_tools_dir, spec.output) if spec else None
