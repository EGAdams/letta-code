"""Can this dashboard still reach each machine on the tailnet?

Every other health check in this dashboard asks about a *service*: is Letta
answering, is the Logger API up, is dockerd running. This module asks the
question underneath all of them -- can we open a shell on the box at all --
and it is the only check with no proxy, relay or cached artefact to fall back
on. "down" here means SSH itself is broken to that host, which is why the
answer is worth its own poll loop and its own debounce.

What travels together, and why:

  * `SSH_CONNECTIONS`  -- the roster. It is not shared config: nothing outside
    this module and the two routes that render it ever reads a connection dict.
  * `ssh_test` / `tailscale_test` -- two probes for two kinds of peer. A phone
    and a Chromebook run no sshd, so their reachability is a tailnet question,
    not an SSH one; `connection_test` picks by `cfg['check']`.
  * `_ssh_health_cache` + `_poll_all_ssh_once` -- the debounce. One slow probe
    is not an outage: the Win10 WSL box is reached over a DERP relay whose
    round trip has been measured from 1.8s to 43s, so a single timeout must not
    turn the tab red. `SSH_HEALTH_FAIL_THRESHOLD` consecutive failures must.
  * `_ssh_log_cache` -- the per-connection tail the Connections panel shows.
    It exists so a flapping link can be *seen* flapping rather than caught in
    whatever state the last poll left it.

Nothing here needs a collaborator from `server.py`: the probes shell out and
the caches are this module's own. That is the whole reason the cluster was
worth moving -- it is a closed system with two outward-facing verbs
(`cached_ssh_health`, `run_manual_test`) and one roster.

`ssh_gateway.py` at the repo root is a *dead* second implementation of
`ssh_test` that nothing imports. Do not build on it before reading the note in
`ssh_test` below: its identity strategy picks the first key that exists on
disk, which is the bug `ssh_test` exists to avoid.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
from collections import deque
from datetime import datetime

# ── The roster ───────────────────────────────────────────────────────────────
# SSH connections this dashboard can reach for remote administration. Each
# entry is checked with a real `ssh ... echo CONNECTED` round trip -- there's
# no proxy/relay to fall back on, so "down" here means SSH itself is broken,
# not just a single service.
SSH_CONNECTIONS = [
    {
        'key': 'win10-host',
        'name': 'Windows 10 Host',
        'host': '100.69.80.89',
        'user': 'NewUser',
        # Prefer the dedicated key on the remote WSL dashboard host. The
        # fallback is the normal key on this WSL host, where that dedicated
        # key is not installed.
        'identity_files': ('~/.ssh/id_win10_host', '~/.ssh/id_ed25519_win10', '~/.ssh/id_ed25519'),
        'note': 'Windows side of the WSL host, for admin scripts run from /mnt/c (100.69.80.89)',
    },
    {
        'key': 'win10-wsl-letta',
        'name': 'Win10 WSL (Letta Docker Host)',
        'host': '100.80.49.10',
        'user': 'adamsl',
        # Reachable only via Tailscale DERP(ord) relay — observed RTT ranges from
        # 1.8s up to a real 43s+ round trip (see reference_tailscale_derp_relay_
        # 100_80_49_10 memory; re-measured 2026-07-09 at 43.1s worst case), far past
        # every other connection here. 30s previously caused false "down" flips —
        # give it its own generous timeout rather than penalizing fast hosts'
        # down-detection.
        'timeout': 55,
        'note': 'WSL side of the Win10 box — actual LETTA_DOCKER_HOST used for Letta server, '
                'Logger API, and Frita executor admin (100.80.49.10)',
    },
    {
        'key': 'win11',
        'name': 'Win11 (Lettabot/Dashboard)',
        'host': '100.102.209.100',
        'user': 'adamsl',
        'note': 'Lettabot + the live dashboard deployment. Was 100.72.158.63 '
                '(desktop-2obsqmc-24, the Ubuntu-24.04 stub) until that node went '
                'offline on 2026-08-05 — Ubuntu-26.04 (the real live distro) now '
                'registers its own Tailscale node "desktop-2obsqmc" directly at '
                '100.102.209.100, reachable over SSH with no wsl.exe hop needed.',
    },
    {
        'key': 'rosemary46',
        'name': 'Rosemary46',
        'host': '100.72.34.38',
        'user': 'adamsl',
        'note': 'Rosemary46 Linux box (100.72.34.38)',
    },
    {
        'key': 'android-phone',
        'name': 'Android Phone (Samsung)',
        'host': '100.111.161.7',
        'user': None,
        'check': 'tailscale',
        'note': 'Samsung phone — checked via `tailscale status` (no sshd). Must show '
                '"online" here for the tailnet-only live dashboard URL '
                '(desktop-2obsqmc-24.tailb8fc54.ts.net) to be reachable from it.',
    },
    {
        'key': 'chromebook-a13',
        'name': 'ChromeBook A13',
        'host': '100.82.55.63',
        'user': None,
        'check': 'tailscale',
        'note': 'Chromebook (tailnet device "octopus", eg1972@gmail.com, Android 13, '
                'Tailscale 1.96.4) — checked via `tailscale status` (no sshd).',
    },
]

SSH_CONNECT_TIMEOUT = 8          # default seconds given to `ssh` to connect + run the check
                                 # command; individual SSH_CONNECTIONS entries may override
                                 # via a 'timeout' key for known-slow paths (DERP relays etc).
SSH_HEALTH_POLL_INTERVAL = 30    # background poll cadence
SSH_HEALTH_FAIL_THRESHOLD = 2    # consecutive failures required before flipping to "down"
SSH_LOG_TAIL = 50                # how many past connection-test results to keep per connection

_ssh_health_cache = {}
_ssh_health_lock = threading.Lock()
_ssh_log_cache = {}    # key -> deque of {seq, text}
_ssh_log_seq = 0
_ssh_log_lock = threading.Lock()


def get_ssh_connection(key):
    """Return the SSH_CONNECTIONS config dict for a key, or None."""
    for c in SSH_CONNECTIONS:
        if c['key'] == key:
            return c
    return None


def _ssh_test_once(target, timeout, identity_file=None):
    """One `ssh ... echo CONNECTED` round trip, optionally pinned to identity_file."""
    cmd = ['ssh', '-o', f'ConnectTimeout={timeout}', '-o', 'BatchMode=yes',
           '-o', 'StrictHostKeyChecking=accept-new']
    if identity_file:
        cmd.extend(['-o', 'IdentitiesOnly=yes', '-i', identity_file])
    cmd.extend([target, 'echo CONNECTED && hostname'])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 10)
        out_lines = result.stdout.strip().splitlines()
        if result.returncode == 0 and out_lines and out_lines[0].strip() == 'CONNECTED':
            host = out_lines[1].strip() if len(out_lines) > 1 else '?'
            return {'ok': True, 'text': f'CONNECTED — {host}'}
        err_lines = (result.stderr or result.stdout or '').strip().splitlines()
        text = err_lines[-1][:160] if err_lines else f'ssh exited {result.returncode}'
        return {'ok': False, 'text': text}
    except subprocess.TimeoutExpired:
        return {'ok': False, 'text': f'ssh to {target} timed out after {timeout}s'}
    except Exception as e:
        return {'ok': False, 'text': f'ssh to {target} failed: {e}'}


def ssh_test(cfg, timeout=SSH_CONNECT_TIMEOUT):
    """Run a real `ssh ... echo CONNECTED` round trip against cfg. Returns {ok, text}.

    identity_files is an ordered preference list, not a single choice — a key
    can exist on disk but no longer be authorized on the remote end (rotated,
    revoked), so picking "the first file that exists" can wedge on a dead key
    forever even though a later one in the list still works. Try each in turn
    (mirrors the categorizer's provider fallback chain) and return the first
    one that actually authenticates.
    """
    target = f"{cfg['user']}@{cfg['host']}"
    identity_files = cfg.get('identity_files') or (cfg.get('identity_file', ''),)
    candidates = [
        os.path.expanduser(f) for f in identity_files
        if f and os.path.isfile(os.path.expanduser(f))
    ]
    if not candidates:
        return _ssh_test_once(target, timeout)
    last = None
    for identity_file in candidates:
        last = _ssh_test_once(target, timeout, identity_file)
        if last['ok']:
            return last
    return last


def _tailscale_cli():
    """Return the available Tailscale CLI, including the WSL host fallback.

    A freshly migrated WSL distro may not have the Linux package installed
    even though the Windows host is connected to the same tailnet.  WSL
    interop exposes that host client as ``tailscale.exe``; using it keeps the
    peer-only entries in SSH Connections meaningful during/after migration.
    """
    discovered = shutil.which('tailscale') or shutil.which('tailscale.exe')
    if discovered:
        return discovered
    # systemd user units intentionally use a Linux-only PATH, so WSL interop
    # executables are not discoverable there even though they remain runnable.
    windows_cli = '/mnt/c/Program Files/Tailscale/tailscale.exe'
    if os.path.isfile(windows_cli):
        return windows_cli
    return 'tailscale'


def _tailscale_ping_test(host, timeout):
    ping_timeout = f'{timeout}s' if isinstance(timeout, int) else str(timeout)
    cmd = [
        _tailscale_cli(), 'ping',
        '--c=1',
        '--until-direct=false',
        f'--timeout={ping_timeout}',
        host,
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 2,
        )
    except subprocess.TimeoutExpired:
        return {'ok': False, 'text': f'tailscale ping timed out after {timeout}s'}
    except Exception as e:
        return {'ok': False, 'text': f'tailscale ping failed: {e}'}

    out = (result.stdout or result.stderr or '').strip()
    first_line = out.splitlines()[0][:160] if out else f'tailscale ping exited {result.returncode}'
    return {'ok': result.returncode == 0, 'text': first_line}


def tailscale_test(cfg, timeout=SSH_CONNECT_TIMEOUT):
    """Check whether a Tailscale peer is actually reachable.

    `tailscale status` can briefly report mobile peers as offline even when a
    DERP ping succeeds, so fall back to a single Tailscale-layer ping before
    showing the dashboard red.
    """
    status_text = None
    try:
        result = subprocess.run(
            [_tailscale_cli(), 'status'],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        for line in result.stdout.splitlines():
            if line.split()[:1] == [cfg['host']]:
                status_text = line.strip()
                if 'offline' in line:
                    break
                return {'ok': True, 'text': status_text}
        if status_text is None:
            status_text = f"{cfg['host']} not found in tailscale status"
    except subprocess.TimeoutExpired:
        return {'ok': False, 'text': f'tailscale status timed out after {timeout}s'}
    except Exception as e:
        return {'ok': False, 'text': f'tailscale status failed: {e}'}

    ping = _tailscale_ping_test(cfg['host'], timeout)
    if ping.get('ok'):
        return {'ok': True, 'text': f"reachable by tailscale ping — {ping['text']}"}
    return {'ok': False, 'text': f"{status_text}; {ping['text']}"}


def connection_test(cfg, timeout=None):
    """Dispatch to the right health check based on cfg['check'] (default 'ssh').

    Uses cfg['timeout'] when set (for known-slow paths like DERP relays),
    falling back to SSH_CONNECT_TIMEOUT."""
    timeout = timeout if timeout is not None else cfg.get('timeout', SSH_CONNECT_TIMEOUT)
    if cfg.get('check') == 'tailscale':
        return tailscale_test(cfg, timeout=timeout)
    return ssh_test(cfg, timeout=timeout)


def _record_ssh_log(key, text):
    global _ssh_log_seq
    with _ssh_log_lock:
        _ssh_log_seq += 1
        buf = _ssh_log_cache.setdefault(key, deque(maxlen=SSH_LOG_TAIL))
        buf.append({'seq': _ssh_log_seq, 'text': text})


def connection_log_rows(key):
    """A snapshot of one connection's log tail, taken under the log lock.

    The route used to reach in and do this itself. It is a list *copy* on
    purpose: the deque is appended to by the poll thread, and iterating it
    directly while it is being trimmed is the classic mutation-during-iteration
    race -- one that would surface as an occasional 500 on a panel nobody is
    watching when it happens."""
    with _ssh_log_lock:
        return list(_ssh_log_cache.get(key, []))


def _poll_all_ssh_once():
    for cfg in SSH_CONNECTIONS:
        h = connection_test(cfg)
        with _ssh_health_lock:
            entry = _ssh_health_cache.get(cfg['key'], {'fails': 0, 'result': None})
            if h.get('ok'):
                entry['fails'] = 0
                entry['result'] = h
            else:
                entry['fails'] += 1
                if entry['result'] is None or entry['fails'] >= SSH_HEALTH_FAIL_THRESHOLD:
                    entry['result'] = h
            _ssh_health_cache[cfg['key']] = entry
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        _record_ssh_log(cfg['key'], f"[{ts}] {'OK' if h['ok'] else 'FAIL'} — {h['text']}")


def _ssh_poll_loop():
    """Background daemon thread body: keep the SSH connection cache fresh."""
    while True:
        _poll_all_ssh_once()
        time.sleep(SSH_HEALTH_POLL_INTERVAL)


def cached_ssh_health(cfg):
    """Debounced SSH health result for cfg from the background poll loop —
    requires SSH_HEALTH_FAIL_THRESHOLD consecutive failures before reporting
    down, since a single slow DERP-relayed probe isn't a real outage.

    Falls back to a synchronous (slow) probe on first access, before the
    background loop has populated the cache."""
    with _ssh_health_lock:
        entry = _ssh_health_cache.get(cfg['key'])
    if entry is not None:
        return entry['result']
    h = connection_test(cfg)
    with _ssh_health_lock:
        _ssh_health_cache[cfg['key']] = {'fails': 0 if h.get('ok') else 1, 'result': h}
    return h


def run_manual_test(cfg):
    """The Test button: probe now, publish the answer, journal it as manual.

    A human pressing Test is asking a different question from the poll loop --
    "is it back *yet*" -- so the answer bypasses the debounce entirely and is
    written straight into the cache as fails=1. That is deliberate: the
    threshold exists to stop one slow relay probe flipping an idle panel red,
    not to make someone press Test twice.
    """
    h = connection_test(cfg)
    with _ssh_health_lock:
        _ssh_health_cache[cfg['key']] = {'fails': 0 if h.get('ok') else 1, 'result': h}
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    _record_ssh_log(cfg['key'], f"[{ts}] {'OK' if h['ok'] else 'FAIL'} — {h['text']} (manual test)")
    return h
