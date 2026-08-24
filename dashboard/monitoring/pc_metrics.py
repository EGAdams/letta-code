"""Per-machine RAM / disk / network, for the PC Monitor tab.

The collection is one POSIX-shell snippet run on the target -- locally for this
box, over the existing key-auth SSH for the others -- and everything that turns
its output into three bars is pure and lives here. Nothing in this module
touches the dashboard's state.

The Windows boxes are the reason the snippet is not simply `free`: read from
inside WSL, /proc/meminfo reports the WSL VM's memory limit, and `/` reports
the VHD's sparse 1TB root. Both are real numbers about the wrong thing. So RAM
comes from PowerShell against the physical host, and disk samples the actual
C: drive through the /mnt/c drvfs mount, falling back to `/` on a box without
one. Network still reflects the WSL VM's NICs -- a known limit, not an
oversight.
"""

from __future__ import annotations

import os
import subprocess
import time
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from hardware.wsl_interop import WINDOWS_POWERSHELL
from hosts import LETTA_DOCKER_HOST, R46_SSH_HOST

class PcMonitor(BaseModel):
    """One machine the PC Monitor tab reports on.

    `memory_source` is the field that matters: 'windows' runs the PowerShell
    query so the reading reflects the physical host, and 'linux' reads
    /proc/meminfo. Getting it wrong on a WSL box does not fail -- it quietly
    reports the WSL VM's memory limit as if it were the machine's RAM, which
    is a plausible-looking number that is not the one anybody wanted.
    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    label: str = Field(min_length=1)
    #: None means "this box"; anything else is an ssh destination.
    host: Optional[str] = None
    memory_source: Literal['windows', 'linux'] = 'linux'
    note: str = ''


PC_MONITORS: dict[str, PcMonitor] = {
    'win11': PcMonitor(
        label='Windows 11', host=None, memory_source='windows',
        note='This machine — Windows RAM and C: drive; network sampled via WSL.'),
    'win10': PcMonitor(
        label='Windows 10', host=LETTA_DOCKER_HOST, memory_source='windows',
        note='The Letta box (100.80.49.10) — Windows RAM and C: drive; '
             'network sampled via WSL.'),
    'moms46': PcMonitor(
        label='Moms 46', host=R46_SSH_HOST,
        note="Mom's Rosemary46 Linux box (100.72.34.38)."),
}

PC_ALERT_THRESHOLDS = {
    'ram': float(os.environ.get('PC_ALERT_RAM_PERCENT', '90')),
    # Disk alerts on FREE space, not percent: yellow under warn GB free,
    # red (critical) at crit GB free or less.
    'disk_free_warn_gb': float(os.environ.get('PC_ALERT_DISK_FREE_WARN_GB', '5')),
    'disk_free_crit_gb': float(os.environ.get('PC_ALERT_DISK_FREE_CRIT_GB', '2')),
    'net': float(os.environ.get('PC_ALERT_NET_PERCENT', '80')),
}
# Full scale for the Network Traffic bar: 100% = this many Mbit/s of rx+tx.
PC_NET_CAPACITY_MBPS = float(os.environ.get('PC_NET_CAPACITY_MBPS', '100'))

_PC_LINUX_MEM_SH = "grep -E 'MemTotal|MemAvailable' /proc/meminfo"
_PC_WINDOWS_MEM_SH = (
    f"{WINDOWS_POWERSHELL} -NoProfile -NonInteractive -Command '"
    "$os = Get-CimInstance Win32_OperatingSystem; "
    "\"MemTotal: $($os.TotalVisibleMemorySize) kB\"; "
    "\"MemAvailable: $($os.FreePhysicalMemory) kB\"' | tr -d '\\r'"
)
_PC_METRICS_SH_TEMPLATE = (
    "echo ===MEM===; {memory_command}; "
    "echo ===DISK===; df -kP /mnt/c 2>/dev/null || df -kP /; "
    "echo ===NET===; cat /proc/net/dev"
)


class PcMetric(BaseModel):
    """One bar on a PC's card.

    `level` and `alert` are redundant on purpose -- the frontend colours the
    bar from `level` and blinks the *tab* from `alert`, and they were computed
    separately at three call sites. Deriving `alert` from `level` here means a
    new level can never be added without deciding whether it blinks.
    """

    model_config = ConfigDict(extra='forbid')

    key: Literal['ram', 'disk', 'net']
    label: str
    percent: float
    text: str
    level: Literal['ok', 'warn', 'crit'] = 'ok'
    #: What the reader has to know to judge the number: the threshold itself.
    tip: str = ''

    @property
    def alert(self) -> bool:
        return self.level != 'ok'

    def to_payload(self) -> dict:
        out = self.model_dump()
        out['alert'] = self.alert
        # Restore the key order the card was built with.
        return {k: out[k] for k in
                ('key', 'label', 'percent', 'text', 'level', 'alert', 'tip')}


def pc_metrics_collector_command(cfg):
    """Build the WSL/Linux collector command for a configured PC."""
    memory_command = (_PC_WINDOWS_MEM_SH if cfg.memory_source == 'windows'
                      else _PC_LINUX_MEM_SH)
    return _PC_METRICS_SH_TEMPLATE.format(memory_command=memory_command)


def parse_pc_metrics_output(text):
    """Parse the ===MEM===/===DISK===/===NET=== collector output into raw
    numbers: memory kB, disk 1K blocks (the Windows C: drive via /mnt/c, or /
    on a non-WSL box), and cumulative rx/tx bytes summed over every interface
    except loopback. Pure — unit-tested."""
    out = {'mem_total_kb': None, 'mem_avail_kb': None,
           'disk_total_kb': None, 'disk_used_kb': None, 'disk_avail_kb': None,
           'disk_mount': None,
           'net_rx_bytes': 0, 'net_tx_bytes': 0}
    section = None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith('===') and s.endswith('===') and len(s) > 6:
            section = s.strip('=')
            continue
        if section == 'MEM':
            if s.startswith('MemTotal:'):
                out['mem_total_kb'] = int(s.split()[1])
            elif s.startswith('MemAvailable:'):
                out['mem_avail_kb'] = int(s.split()[1])
        elif section == 'DISK':
            parts = s.split()
            if len(parts) >= 6 and parts[-1] in ('/mnt/c', '/') and parts[1].isdigit():
                out['disk_total_kb'] = int(parts[1])
                out['disk_used_kb'] = int(parts[2])
                out['disk_avail_kb'] = int(parts[3])
                out['disk_mount'] = parts[-1]
        elif section == 'NET' and ':' in s:
            name, _, rest = s.partition(':')
            fields = rest.split()
            # /proc/net/dev: rx bytes is field 0, tx bytes is field 8.
            if name.strip() != 'lo' and len(fields) >= 9:
                out['net_rx_bytes'] += int(fields[0])
                out['net_tx_bytes'] += int(fields[8])
    return out


def _pc_gb(kb):
    return kb / (1024.0 * 1024.0)


def build_pc_metrics(parsed, prev_net, now, thresholds=None, net_capacity_mbps=None):
    """Pure: parsed collector numbers + the previous network sample →
    (metric rows, new network sample). Each row carries percent / human text /
    level ('ok'|'warn'|'crit') so the frontend only has to draw bars. Disk
    alerts on GB free (warn under 5, crit at 2 or less by default); RAM and
    network alert on percent. Network traffic is a rate, so it needs two
    samples — the first request shows 'measuring…'."""
    th = thresholds or PC_ALERT_THRESHOLDS
    cap_mbps = net_capacity_mbps or PC_NET_CAPACITY_MBPS
    metrics = []

    mem_total = parsed.get('mem_total_kb')
    if mem_total:
        used = mem_total - (parsed.get('mem_avail_kb') or 0)
        pct = round(100.0 * used / mem_total, 1)
        metrics.append(PcMetric(
            key='ram', label='RAM Usage', percent=pct,
            text=f'{_pc_gb(used):.1f} / {_pc_gb(mem_total):.1f} GB',
            level='warn' if pct >= th['ram'] else 'ok',
            tip=f"Alerts at {th['ram']:.0f}%").to_payload())

    disk_total = parsed.get('disk_total_kb')
    if disk_total:
        used = parsed.get('disk_used_kb') or 0
        free_gb = _pc_gb(parsed.get('disk_avail_kb') or 0)
        warn_gb = th.get('disk_free_warn_gb', 5.0)
        crit_gb = th.get('disk_free_crit_gb', 2.0)
        level = 'crit' if free_gb <= crit_gb else ('warn' if free_gb < warn_gb else 'ok')
        pct = round(100.0 * used / disk_total, 1)
        drive = 'C: ' if parsed.get('disk_mount') == '/mnt/c' else ''
        metrics.append(PcMetric(
            key='disk', label='Hard Drive Usage', percent=pct,
            text=f'{drive}{_pc_gb(used):.0f} / {_pc_gb(disk_total):.0f} GB'
                 f' ({free_gb:.1f} GB free)',
            level=level,
            tip=f'Yellow under {warn_gb:.0f} GB free, '
                f'red at {crit_gb:.0f} GB free or less').to_payload())

    total_bytes = parsed.get('net_rx_bytes', 0) + parsed.get('net_tx_bytes', 0)
    new_sample = (now, total_bytes)
    if prev_net and now > prev_net[0] and total_bytes >= prev_net[1]:
        rate_mbps = (total_bytes - prev_net[1]) * 8.0 / (now - prev_net[0]) / 1e6
        pct = round(min(100.0, 100.0 * rate_mbps / cap_mbps), 1)
        metrics.append(PcMetric(
            key='net', label='Network Traffic', percent=pct,
            text=f'{rate_mbps:.2f} Mbit/s (bar full at {cap_mbps:.0f})',
            level='warn' if pct >= th['net'] else 'ok',
            tip=f"Alerts at {th['net']:.0f}%").to_payload())
    else:
        metrics.append(PcMetric(
            key='net', label='Network Traffic', percent=0,
            text='measuring…',
            tip=f"Alerts at {th['net']:.0f}%").to_payload())
    return metrics, new_sample


_pc_metrics_cache = {}    # key → (timestamp, payload)
_pc_net_last = {}         # key → (timestamp, cumulative rx+tx bytes)
_pc_last_good = {}        # key → last ok payload, served (marked stale) on a failed sample
PC_METRICS_CACHE_TTL = 10  # seconds — also the effective network-rate window


def pc_metrics(key):
    """Payload for one PC: run the collector (local or SSH), derive the three
    metric bars, and cache briefly so the frontend's tab-colour polling doesn't
    trigger an SSH per tab per tick. A failed sample (the cross-box Tailscale
    path stalls now and then, esp. on the first attempt after idle) serves the
    last good reading marked stale instead of an error — the next poll retries."""
    cfg = PC_MONITORS.get(key)
    if not cfg:
        return {'ok': False, 'error': f'unknown pc {key}', 'alert': False}
    cached = _pc_metrics_cache.get(key)
    if cached and time.time() - cached[0] < PC_METRICS_CACHE_TTL:
        return cached[1]
    host = cfg.host
    collector = pc_metrics_collector_command(cfg)
    if host:
        cmd = ['ssh', '-o', 'ConnectTimeout=8', '-o', 'BatchMode=yes',
               '-o', 'ServerAliveInterval=5', '-o', 'ServerAliveCountMax=2',
               host, collector]
    else:
        cmd = ['sh', '-c', collector]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        if not (r.stdout or '').strip():
            raise RuntimeError((r.stderr or 'collector produced no output').strip()[:200])
        parsed = parse_pc_metrics_output(r.stdout)
        now = time.time()
        metrics, sample = build_pc_metrics(parsed, _pc_net_last.get(key), now)
        _pc_net_last[key] = sample
        levels = [m.get('level', 'ok') for m in metrics]
        level = 'crit' if 'crit' in levels else ('warn' if 'warn' in levels else 'ok')
        out = {'ok': True, 'key': key, 'label': cfg.label, 'note': cfg.note,
               'metrics': metrics, 'alert': level != 'ok', 'level': level, 'as_of': now}
        _pc_last_good[key] = out
    except Exception as e:
        good = _pc_last_good.get(key)
        if good:
            out = dict(good)
            out['stale'] = True
            out['stale_error'] = str(e)
        else:
            out = {'ok': False, 'key': key, 'label': cfg.label, 'error': str(e),
                   'alert': False, 'level': 'ok'}
    _pc_metrics_cache[key] = (time.time(), out)
    return out


