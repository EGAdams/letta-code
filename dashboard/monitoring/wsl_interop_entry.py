"""Is the WSLInterop binfmt entry registered on each WSL box?

WSL runs a Windows `.exe` by handing it to `/init` through a binfmt_misc entry
named `WSLInterop`. With `systemd=true` in /etc/wsl.conf, `systemd-binfmt`
can skip itself at boot ("start condition unmet"), and then the entry is
simply never registered. Nothing complains: every `.exe` -- powershell.exe,
cmd.exe, rundll32.exe -- just fails with `Exec format error` the next time
something tries to launch one. On 2026-10-28 that silently broke the
browser-open ADW on Rosemary46; this check exists so the next time shows up
on the dashboard instead of in a failed run.

One shell snippet, run locally for this box and over the existing key-auth SSH
for the others (the same machines the PC Monitor tab watches). Parsing it is
pure and unit-tested.
"""

from __future__ import annotations

import subprocess
import time
from typing import Literal

from pydantic import BaseModel, ConfigDict

from monitoring.pc_metrics import PC_MONITORS

#: The line that re-registers the entry. Shown on the page verbatim, so it is
#: named once here rather than typed into the frontend.
REGISTER_COMMAND = (
    "sudo sh -c 'echo :WSLInterop:M::MZ::/init:PF "
    "> /proc/sys/fs/binfmt_misc/register'")

_ENTRY = '/proc/sys/fs/binfmt_misc/WSLInterop'

COLLECTOR_SH = (
    "echo ===KERNEL===; cat /proc/sys/kernel/osrelease; "
    f"echo ===ENTRY===; cat {_ENTRY} 2>/dev/null || echo __MISSING__; "
    "echo ===BINFMT===; systemctl is-active systemd-binfmt 2>/dev/null || true"
)

#: The dashboard polls every 30s; caching for slightly less keeps the two
#: callers (tab colour and open page) from doubling the SSH traffic.
CACHE_TTL = 25


class InteropEntryStatus(BaseModel):
    """One machine's answer.

    `level` drives the tab colour: 'crit' is red (the entry is gone or
    disabled, so Windows exes cannot run), 'warn' is yellow (we could not
    ask), 'ok' is green. A non-WSL box is 'ok' with `wsl=False` -- there is
    nothing there to register.
    """

    model_config = ConfigDict(extra='forbid')

    key: str
    label: str
    host: str
    state: Literal['enabled', 'disabled', 'missing', 'not-wsl', 'unreachable']
    level: Literal['ok', 'warn', 'crit']
    wsl: bool = True
    binfmt_service: str = ''
    detail: str = ''
    as_of: float = 0.0


def parse_collector_output(text: str) -> dict:
    """Split the ===KERNEL===/===ENTRY===/===BINFMT=== output into
    {wsl, state, binfmt_service, detail}. Pure."""
    sections: dict[str, list[str]] = {}
    current = None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith('===') and s.endswith('===') and len(s) > 6:
            current = s.strip('=')
            sections[current] = []
            continue
        if current is not None and s:
            sections[current].append(s)
    kernel = ' '.join(sections.get('KERNEL', []))
    entry = sections.get('ENTRY', [])
    wsl = 'microsoft' in kernel.lower()
    if not wsl:
        state = 'not-wsl'
    elif not entry or entry[0] == '__MISSING__':
        state = 'missing'
    elif entry[0] == 'enabled':
        state = 'enabled'
    else:
        state = 'disabled'
    return {
        'wsl': wsl,
        'state': state,
        'binfmt_service': ' '.join(sections.get('BINFMT', [])),
        'detail': '; '.join(entry) if state in ('enabled', 'disabled') else '',
    }


_LEVELS = {'enabled': 'ok', 'not-wsl': 'ok', 'disabled': 'crit',
           'missing': 'crit', 'unreachable': 'warn'}

_cache: dict[str, tuple[float, InteropEntryStatus]] = {}


def _collect(key: str) -> InteropEntryStatus:
    cfg = PC_MONITORS[key]
    if cfg.host:
        cmd = ['ssh', '-o', 'ConnectTimeout=8', '-o', 'BatchMode=yes',
               '-o', 'ServerAliveInterval=5', '-o', 'ServerAliveCountMax=2',
               cfg.host, COLLECTOR_SH]
    else:
        cmd = ['sh', '-c', COLLECTOR_SH]
    base = {'key': key, 'label': cfg.label, 'host': cfg.host or 'this box',
            'as_of': time.time()}
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        if '===ENTRY===' not in (r.stdout or ''):
            raise RuntimeError(
                (r.stderr or 'no output').strip()[:200] or 'no output')
    except Exception as e:  # noqa: BLE001 -- any failure is "could not ask"
        return InteropEntryStatus(**base, state='unreachable', level='warn',
                                  detail=str(e))
    parsed = parse_collector_output(r.stdout)
    return InteropEntryStatus(**base, level=_LEVELS[parsed['state']], **parsed)


def interop_status(key: str) -> InteropEntryStatus:
    cached = _cache.get(key)
    if cached and time.time() - cached[0] < CACHE_TTL:
        return cached[1]
    status = _collect(key)
    _cache[key] = (time.time(), status)
    return status


def wsl_interop_payload() -> dict:
    """Every machine's status, the worst level across them, and the fix."""
    machines = [interop_status(key) for key in PC_MONITORS]
    levels = [m.level for m in machines]
    level = 'crit' if 'crit' in levels else ('warn' if 'warn' in levels else 'ok')
    return {
        'level': level,
        'machines': [m.model_dump() for m in machines],
        'register_command': REGISTER_COMMAND,
    }
