"""Running a physical scanner's script and classifying the outcome.

Two HP scanners attached to the Win11 box, driven by the shared, parameterized
scan_device.ps1, which selects the target by NAME (`-NameLike`) -- NOT "first
device found" (WIA enumeration order is unstable). ``wsl_interop_socket`` is
threaded through ``Collaborators`` rather than imported directly because
tests drive the scan-dispatch call sites by faking it via its `server.` name.
"""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from typing import Callable

from hardware.scan_result import classify_scan_result


@dataclass(frozen=True)
class Collaborators:
    """What stays behind in server.py, handed over per call."""

    scanners: dict
    scan_tools_dir: str
    scan_lock: object
    scan_timeout_sec: float
    scanner_image_url_prefix: str
    wsl_interop_socket: Callable
    scan_output_ready: Callable


def reap_stale_scans(deps: Collaborators, scan_env):
    """Kill leaked scan_device.ps1 Windows processes (see invoke_scanner)."""
    reaper = os.path.join(deps.scan_tools_dir, 'reap_scans.ps1')
    if not os.path.isfile(reaper):
        return
    try:
        subprocess.run(
            ['/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe',
             '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', './reap_scans.ps1'],
            cwd=deps.scan_tools_dir, capture_output=True, text=True, timeout=20,
            env=scan_env,
        )
    except Exception:  # noqa: BLE001 — reaping is best-effort
        pass


def invoke_scanner(deps: Collaborators, key):
    """Run a scanner's script and classify the outcome.

    Returns {status, ...} where status is one of:
      ready          — transfer succeeded, scan image written (includes image_url)
      busy           — WIA device busy (needs power-cycle); reported FAST (no scan)
      offline        — named device not enumerated (powered off / disconnected)
      not_configured — no script wired for this scanner
      error          — anything else (interop missing, timeout, script error)

    This call backs only the manual scan (POST /api/scanner-scan). Runtime status
    polling is read-only and must never call it. Blocking; ReusableHTTPServer is
    threaded so the dashboard's other pollers are unaffected, and `scan_lock`
    keeps two transfers from colliding (concurrent transfers self-induce the
    "busy" error).

    Critically, every scan is preceded by `reap_stale_scans()`: on a Python
    timeout we can only kill the bash wrapper, not the Windows powershell.exe it
    launched via interop, so a hung scan leaks a Windows process that keeps the
    device busy and — if they pile up — wedges the whole WIA service (stisvc).
    Reaping under the lock (where no scan of ours is legitimately running) caps
    leaks at zero before each attempt.
    """
    cfg = deps.scanners.get(key)
    if not cfg:
        return {'status': 'error', 'error': f'Unknown scanner: {key}'}
    if not cfg.get('script'):
        return {'status': 'not_configured',
                'error': f"{cfg['name']} ({cfg['device']}) is not wired up yet."}
    script_path = os.path.join(deps.scan_tools_dir, cfg['script'])
    if not os.path.isfile(script_path):
        return {'status': 'error',
                'error': f'Scanner script not found: {script_path}'}
    uses_airscan = bool(cfg.get('airscan_device'))
    interop = deps.wsl_interop_socket()
    if not interop and not uses_airscan:
        return {'status': 'error',
                'error': 'No usable WSL interop socket — open a WSL session so the '
                         'service can launch the scanner.'}
    scan_env = os.environ.copy()
    if interop:
        scan_env['WSL_INTEROP'] = interop
    with deps.scan_lock:
        if not uses_airscan:
            reap_stale_scans(deps, scan_env)
        try:
            proc = subprocess.run(
                ['bash', cfg['script']],
                cwd=deps.scan_tools_dir,
                capture_output=True, text=True, timeout=deps.scan_timeout_sec,
                env=scan_env,
            )
        except subprocess.TimeoutExpired:
            # The bash wrapper is dead, but the Windows powershell.exe is not —
            # reap it so its WIA handle can't wedge the device/service.
            if not uses_airscan:
                reap_stale_scans(deps, scan_env)
            return {'status': 'error',
                    'error': f'Scan timed out after {deps.scan_timeout_sec}s '
                             '(scanner not responding).'}
        except Exception as exc:  # noqa: BLE001 — surface launch failures to the UI
            return {'status': 'error', 'error': f'Failed to start scan: {exc}'}
    log = ((proc.stdout or '') + (proc.stderr or '')).strip()
    img = os.path.join(deps.scan_tools_dir, cfg['output'])
    result = classify_scan_result(proc.returncode, log, deps.scan_output_ready(img))
    if result['status'] == 'ready':
        # Cache-bust so the browser reloads the freshly scanned image each time.
        result['image_url'] = (
            f'{deps.scanner_image_url_prefix}?scanner={key}&t={int(time.time())}')
    return result
