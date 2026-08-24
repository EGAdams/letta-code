"""The scanner health LEDs: probing a scanner, then mapping what came back.

Split deliberately in two. `build_scanner_diagnostics` is pure -- raw probe
results in, LED rows out -- because the rules it encodes are the part that has
actually been wrong: a stale Windows WIA record turning the dashboard red while
the hardware was fine, an open ink door showing up as a mystery rather than a
sentence. Rules that decide what an operator is told belong somewhere a test
can reach without a scanner on the desk.

The two probe helpers above it do the I/O, and take the paths they need as
arguments rather than importing the server. Nothing here ever starts a scan;
`scanimage --help` fetches capabilities and scanner_diag.ps1 is read-only.
"""

import json
import os
import shutil
import subprocess

from hardware.wsl_interop import WINDOWS_POWERSHELL

# "We keep having to reset everything" -- this makes every failure point in the
# scan workflow visible as an LED instead of a mystery. The Windows-side checks
# come from ONE scanner_diag.ps1 launch.
SCANNER_DIAG_TIMEOUT_SEC = 30
SCANNER_DIAG_LOCK_WAIT_SEC = 8


def _airscan_ready(cfg):
    """Return True when the native eSCL backend can query this scanner.

    Both HP devices expose eSCL directly on the LAN. This path avoids Windows
    WIA/WSD, whose stale Problem-45 device records used to leave the dashboard
    red even while the scanner hardware was healthy. `--help` only fetches
    capabilities; it never starts a scan.
    """
    device = cfg.get('airscan_device')
    if not device or not shutil.which('scanimage'):
        return False
    try:
        proc = subprocess.run(
            ['scanimage', '-d', device, '--help'],
            capture_output=True, text=True, timeout=SCANNER_DIAG_TIMEOUT_SEC)
    except Exception:  # noqa: BLE001 — unavailable backend is a clean fallback
        return False
    return proc.returncode == 0


def _run_scanner_diag_ps(cfg, interop, scan_tools_dir, skip_wia=False):
    """Launch scanner_diag.ps1 via Windows PowerShell; return its parsed dict.

    Returns None if the script is missing or the launch failed/was unparseable —
    the caller renders those Windows-side checks as 'unknown' (grey), not red,
    because "we couldn't ask Windows" is not the same as "the scanner is broken".

    `scan_tools_dir` is passed in rather than imported: the scripts live in the
    caller's tree, and this module has no opinion about where that is.
    """
    script_path = os.path.join(scan_tools_dir, 'scanner_diag.ps1')
    if not os.path.isfile(script_path):
        return None
    env = os.environ.copy()
    env['WSL_INTEROP'] = interop
    args = [WINDOWS_POWERSHELL, '-NoProfile', '-ExecutionPolicy', 'Bypass',
            '-File', './scanner_diag.ps1',
            '-NameLike', cfg.get('namelike', ''),
            '-FriendlyLike', cfg.get('driver_match', '')]
    if skip_wia:
        args.append('-SkipWia')
    try:
        proc = subprocess.run(
            args, cwd=scan_tools_dir, capture_output=True, text=True,
            timeout=SCANNER_DIAG_TIMEOUT_SEC, env=env)
    except Exception:  # noqa: BLE001 — any failure just means "couldn't ask"
        return None
    out = (proc.stdout or '').strip()
    if not out:
        return None
    try:
        return json.loads(out.splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return None


def _diag_check(check_id, label, state, detail):
    """One LED row: state is 'ok' | 'warn' | 'bad' | 'unknown'."""
    return {'id': check_id, 'label': label, 'state': state, 'detail': detail}


def build_scanner_diagnostics(
        key, interop_ok, ps_data, device_status=None, airscan_ready=None):
    """Pure map of raw probe results -> the scanner's health LEDs.

    No I/O so it is fully unit-testable. `ps_data` is scanner_diag.ps1's parsed
    JSON (or None when Windows was unreachable); `device_status` is
    read_deskjet_device_status()'s dict for the Freezer (or None). The checks are
    ordered as the workflow depends on them, top to bottom.
    """
    checks = []

    # The live scan scripts use native eSCL/AirScan first. When that backend can
    # query the scanner, stale Windows WIA state is irrelevant and must not turn
    # the LEDs red or tell the user to power-cycle healthy hardware.
    if airscan_ready is True:
        checks.extend([
            _diag_check(
                'bridge', 'Scanner Backend', 'ok',
                'The dashboard can drive this scanner directly over the network.'),
            _diag_check(
                'service', 'Scanner Service', 'ok',
                'The native AirScan service is available; Windows WIA is not required.'),
            _diag_check(
                'driver', 'Driver Health', 'ok',
                'The scanner returned valid eSCL capabilities.'),
            _diag_check(
                'online', 'Scanner Online', 'ok',
                'The scanner is powered on, connected, and answering directly.'),
            _diag_check(
                'access', 'Scanner Access', 'ok',
                'The dashboard can open this scanner without Windows WIA.'),
            _diag_check(
                'stale', 'No Stuck Scans', 'ok',
                'The direct scanner backend has no Windows scan processes to leak.'),
        ])
        # This DeskJet is scanner-only. Suppress its printing subsystem state
        # (paper, ink, tray and printer-status reachability); none of it affects
        # AirScan and surfacing it makes a healthy scanner look unhealthy.
        # Retain only device-wide blockers that can prevent scanning too.
        if (key == 'freezer' and device_status is not None
                and device_status.get('blocker')):
            checks.append(_diag_check(
                'device', 'Scanner Hardware', 'bad', device_status['blocker']))
        states = [c['state'] for c in checks]
        overall = 'bad' if 'bad' in states else (
            'warn' if 'warn' in states or 'unknown' in states else 'ok')
        return {'scanner': key, 'checks': checks, 'overall': overall}

    ps = ps_data or {}
    # Windows-side checks are only meaningful once we can actually reach Windows.
    windows_reachable = bool(interop_ok) and ps_data is not None

    # 1. WSL bridge — the systemd service borrows an interop socket from an
    #    interactive WSL session; with none open it can't launch Windows at all.
    if interop_ok:
        checks.append(_diag_check(
            'bridge', 'WSL Bridge', 'ok',
            'The dashboard service can reach Windows to drive the scanner.'))
    else:
        checks.append(_diag_check(
            'bridge', 'WSL Bridge', 'bad',
            'No WSL session is open, so the service cannot reach Windows to '
            'scan. Open a WSL terminal on the live box, then refresh.'))

    # 2. Windows Image Acquisition service (stisvc) — the classic "wedge".
    stisvc = (ps.get('stisvc') or '').lower()
    if not windows_reachable:
        checks.append(_diag_check('service', 'Imaging Service', 'unknown',
            'Could not read the Windows Image Acquisition service.'))
    elif stisvc == 'running':
        checks.append(_diag_check('service', 'Imaging Service', 'ok',
            'Windows Image Acquisition (stisvc) is running.'))
    elif stisvc in ('stopped', 'stoppending', 'paused', 'startpending'):
        checks.append(_diag_check('service', 'Imaging Service', 'bad',
            'Windows Image Acquisition (stisvc) is not running. Restart it from '
            'an elevated shell: net stop stisvc & net start stisvc.'))
    else:
        checks.append(_diag_check('service', 'Imaging Service', 'unknown',
            f'Windows Image Acquisition service state: {ps.get("stisvc") or "unknown"}.'))

    # HP's diagnostic utility installs an auto-start background service. It can
    # exclusively hold one scanner while WIA enumeration, PnP, and stisvc all
    # remain healthy — the exact "all LEDs green, scan says busy" failure.
    if 'hp_scan_doctor' in ps:
        hp_doctor = (ps.get('hp_scan_doctor') or '').lower()
        if hp_doctor == 'running':
            access = (ps.get('wia_connect') or '').lower()
            if access in ('busy', 'error', 'timeout'):
                checks.append(_diag_check('hp-doctor', 'HP Scan Doctor', 'bad',
                    'HP Print Scan Doctor is running and may be holding this '
                    'scanner busy. Stop and disable HPPrintScanDoctorService.'))
            else:
                checks.append(_diag_check('hp-doctor', 'HP Scan Doctor', 'warn',
                    'HP Print Scan Doctor is running, but Windows can currently '
                    'open this scanner. Disable the service if busy errors return.'))
        elif hp_doctor in ('stopped', 'absent'):
            checks.append(_diag_check('hp-doctor', 'HP Scan Doctor', 'ok',
                'HP Print Scan Doctor is not holding the scanner.'))
        else:
            checks.append(_diag_check('hp-doctor', 'HP Scan Doctor', 'unknown',
                f'HP Print Scan Doctor service state: '
                f'{ps.get("hp_scan_doctor") or "unknown"}.'))

    # 3. Driver health — this is the "may need to reinstall the driver" LED.
    dstat = (ps.get('driver_status') or '').lower()
    if not windows_reachable:
        checks.append(_diag_check('driver', 'Driver Health', 'unknown',
            'Could not read the scanner driver state.'))
    elif dstat == 'ok':
        checks.append(_diag_check('driver', 'Driver Health', 'ok',
            'The imaging driver for this scanner reports healthy.'))
    elif dstat == 'absent' or ps.get('driver_present') is False:
        checks.append(_diag_check('driver', 'Driver Health', 'bad',
            'Windows has no imaging driver for this scanner. Reinstall the HP '
            'driver (HP Smart / HP Easy Start), then refresh.'))
    elif dstat == 'error':
        checks.append(_diag_check('driver', 'Driver Health', 'bad',
            'The scanner driver reports an error. Reinstall the HP driver '
            '(HP Smart / HP Easy Start), then refresh.'))
    elif dstat in ('', 'unknown'):
        checks.append(_diag_check('driver', 'Driver Health', 'unknown',
            'Could not read the scanner driver state.'))
    else:
        checks.append(_diag_check('driver', 'Driver Health', 'warn',
            f'The scanner driver reports "{ps.get("driver_status")}" — '
            'if scans fail, reinstall the HP driver.'))

    # 4. Online — is the named device enumerated by WIA right now?
    wia = (ps.get('wia') or '').lower()
    if not windows_reachable:
        checks.append(_diag_check('online', 'Scanner Online', 'unknown',
            'Could not check whether the scanner is online.'))
    elif wia == 'present':
        checks.append(_diag_check('online', 'Scanner Online', 'ok',
            'Windows sees the scanner — it is powered on and connected.'))
    elif wia == 'absent':
        checks.append(_diag_check('online', 'Scanner Online', 'bad',
            'Windows does not see the scanner. It is powered off, asleep, or '
            'disconnected — power-cycle it, then refresh.'))
    elif wia == 'busy':
        checks.append(_diag_check('online', 'Scanner Online', 'warn',
            'The scanner is busy. If it stays busy, close any open cover or ink '
            'door and power-cycle it.'))
    elif wia == 'timeout':
        checks.append(_diag_check('online', 'Scanner Online', 'bad',
            'WIA did not respond — the imaging service is likely wedged. Restart '
            'stisvc (or kill it from an elevated shell so it auto-restarts).'))
    elif wia == 'skipped':
        checks.append(_diag_check('online', 'Scanner Online', 'warn',
            'A scan is in progress — the online check was skipped to avoid '
            'interfering with it.'))
    elif wia == 'service-down':
        checks.append(_diag_check('online', 'Scanner Online', 'unknown',
            'Skipped — the imaging service is not running (see above).'))
    else:
        checks.append(_diag_check('online', 'Scanner Online', 'warn',
            'WIA enumeration could not confirm the scanner.'))

    # Enumeration only proves that Windows can see the device. Connect() is the
    # first operation an actual scan performs and exposes exclusive holders.
    if 'wia_connect' in ps:
        access = (ps.get('wia_connect') or '').lower()
        if access == 'ready':
            checks.append(_diag_check('access', 'Scanner Access', 'ok',
                'Windows can open this scanner for a scan.'))
        elif access == 'busy':
            checks.append(_diag_check('access', 'Scanner Access', 'bad',
                'Windows sees the scanner, but another app or service is holding '
                'it busy. Close scanner apps and stop HP Print Scan Doctor.'))
        elif access == 'timeout':
            checks.append(_diag_check('access', 'Scanner Access', 'bad',
                'Windows could not open the scanner before the health check '
                'timed out. Restart the imaging service.'))
        elif access in ('skipped', 'service-down', 'not-tested'):
            checks.append(_diag_check('access', 'Scanner Access', 'unknown',
                'Scanner access could not be tested; resolve the earlier red '
                'health check first.'))
        else:
            checks.append(_diag_check('access', 'Scanner Access', 'bad',
                'Windows sees the scanner but could not open it. Close HP/Windows '
                'scan apps, then restart the imaging service.'))

    # 5. No stuck scan processes — leaked scans keep the device busy and,
    #    piled up, wedge stisvc. Cleared before each scan, but worth surfacing.
    stale = ps.get('stale_scans')
    if not windows_reachable or stale is None or stale == -1:
        checks.append(_diag_check('stale', 'No Stuck Scans', 'unknown',
            'Could not check for leaked scan processes.'))
    elif stale == 0:
        checks.append(_diag_check('stale', 'No Stuck Scans', 'ok',
            'No stuck scan processes are holding the device.'))
    else:
        checks.append(_diag_check('stale', 'No Stuck Scans', 'warn',
            f'{stale} stuck scan process(es) are leaked. They are cleared before '
            'the next scan, but repeated leaks wedge the imaging service.'))

    # Freezer is scanner-only: show only hardware faults that can block scans,
    # never printing-only paper/ink/tray status.
    if (key == 'freezer' and device_status is not None
            and device_status.get('blocker')):
        checks.append(_diag_check('device', 'Scanner Hardware', 'bad',
            device_status['blocker']))

    states = [c['state'] for c in checks]
    if 'bad' in states:
        overall = 'bad'
    elif 'warn' in states or 'unknown' in states:
        overall = 'warn'
    else:
        overall = 'ok'
    return {'scanner': key, 'checks': checks, 'overall': overall}
