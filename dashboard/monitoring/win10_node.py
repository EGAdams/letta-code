"""The Win10 box, as one operational surface: reachable, dockerd, containers, revive.

The Win10 WSL node hosts Letta, the Frita SDK executor and the Logger API. When
it drops -- historically a stuck Tailscale session -- all three go red as
*symptoms*, and the dashboard collapses those into one actionable row by making
this module's reachability probe the root cause the others hang off (`blocked_by`).

Four questions about one machine travel together because they are the same
question asked at four depths, and each answer decides whether the next is even
worth asking:

  * `win10_node_health`      -- can we open a TCP socket to it at all?
  * `win10_docker_ok`        -- is its dockerd running? (True / False / None)
  * `win10_container_states` -- what does its `docker ps -a` say?
  * `container_status_for`   -- what does that mean for one server key?

plus the two recovery actions the dashboard offers as buttons,
`restart_win10_node` (revive the WSL node from the still-online Windows side)
and `ensure_win10_docker` (clear a stale docker.pid and start the unit).

Each of the three probes is an SSH or socket round trip to a box that is
frequently the *slow* kind of unreachable, so each is cached behind its own lock
for its own TTL. `Win10CacheEntry` below is why they are modelled rather than
kept as dicts.

Only one thing stays behind in server.py: the restart log, which every other
restart handler also writes to. It arrives in a `Collaborators` bundle built
fresh per call, never imported, so replacing `_log_restart` or `RESTART_LOG` on
`server` is honoured by the code that actually runs.
"""

from __future__ import annotations

import socket
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

from pydantic import BaseModel, ConfigDict

from hosts import LETTA_DOCKER_HOST
from monitoring.server_lifecycle import mark_server_starting

import os

# ── The box ──────────────────────────────────────────────────────────────────
#: The WSL side -- what Letta, Frita and the Logger API actually run on.
WIN10_NODE_HOST = (
    LETTA_DOCKER_HOST.split('@')[-1] if '@' in LETTA_DOCKER_HOST else '100.80.49.10')
#: The Windows side of the same box. It stays online when the WSL node drops,
#: which is the whole reason the Restart button can work at all.
WIN10_WINDOWS_HOST = os.environ.get('WIN10_WINDOWS_HOST', 'NewUser@100.69.80.89')
WIN10_WSL_DISTRO = os.environ.get('WIN10_WSL_DISTRO', 'Ubuntu-24.04')

#: Which containers back which server key. Indicator #2: Docker's own status
#: string carries the exit code and restart count, so "Exited (139) 54m ago"
#: (139 = OOM/segfault) or "Restarting (3x)" tells you it crashed or is
#: crash-looping rather than merely "down".
WIN10_CONTAINERS = {
    'letta': ['letta-server', 'letta-memfs'],
    'logger-api': ['logger-api-php', 'logger-api-mysql'],
    'frita-executor': ['frita-executor'],
}

WIN10_NODE_CACHE_TTL = 20
WIN10_CONTAINERS_CACHE_TTL = 20
WIN10_DOCKER_CACHE_TTL = 30


# ── The caches ───────────────────────────────────────────────────────────────
class Win10CacheEntry(BaseModel):
    """One cached probe result, and when it was taken.

    The three caches here used to be plain ``{'value': None, 'ts': 0.0}`` dicts
    tested for freshness as ``value is not None and now - ts < TTL``. That reads
    like "is there an entry?" but actually asks "is the entry's value non-None",
    and the two questions only happen to agree while None is not a legal value.

    For ``win10_docker_ok`` it is a legal value: the probe is deliberately
    three-state, and None means "cannot tell -- the SSH did not come back".
    An unknown answer could therefore never satisfy the freshness test, so it
    was written to the cache and then never served from it, and every health
    poll paid another 8-second SSH timeout against a box that had just finished
    proving it was not answering. That is the one case the cache exists for, and
    it was the one case that had no cache -- silently, because a slow dashboard
    looks like a slow network.

    Making the *entry* the presence sentinel (``None`` = never probed) separates
    "is there an entry" from "what does the entry say", so None caches like any
    other value. Frozen, and replaced whole rather than mutated field by field,
    for the same reason ``HealthCacheEntry`` is: a reader must never be able to
    see a new value stamped with an old timestamp.
    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    value: object = None
    ts: float = 0.0

    def is_fresh(self, now: float, ttl: float) -> bool:
        return (now - self.ts) < ttl


class _TtlCache:
    """One `Win10CacheEntry` behind its own lock, with a TTL.

    Separate instances rather than one shared dict: the three probes have
    different costs and different TTLs, and a slow `docker ps` must not hold up
    a cheap socket check.
    """

    def __init__(self, ttl: float):
        self._ttl = ttl
        self._lock = threading.Lock()
        self._entry: Optional[Win10CacheEntry] = None

    def hit(self) -> tuple[bool, object]:
        """Return `(True, value)` for a live entry, else `(False, None)`.

        The hit flag is separate from the value on purpose -- see
        `Win10CacheEntry`. A cached None is a hit.
        """
        with self._lock:
            entry = self._entry
            if entry is not None and entry.is_fresh(time.time(), self._ttl):
                return True, entry.value
            return False, None

    def put(self, value: object) -> object:
        with self._lock:
            self._entry = Win10CacheEntry(value=value, ts=time.time())
        return value

    def invalidate(self) -> None:
        """Drop the entry so the next call re-probes. Used after an action that
        makes any cached opinion about the box stale by definition."""
        with self._lock:
            self._entry = None


_NODE_CACHE = _TtlCache(WIN10_NODE_CACHE_TTL)
_CONTAINERS_CACHE = _TtlCache(WIN10_CONTAINERS_CACHE_TTL)
_DOCKER_CACHE = _TtlCache(WIN10_DOCKER_CACHE_TTL)


# ── What server.py still owns ────────────────────────────────────────────────
@dataclass(frozen=True)
class Collaborators:
    """server.py's half of this cluster, resolved per call.

    Only the restart log: every restart handler in server.py appends to it, so
    it cannot travel here. `log_restart` writes one line; `restart_log_path` is
    the same file opened directly, to catch the spawned ssh's own output.
    """

    log_restart: Callable[[str], None]
    restart_log_path: str


# ── Is the box there at all? ─────────────────────────────────────────────────
def win10_node_health(timeout=None):
    """Is the Win10 WSL node reachable at all? TCP-connect to its SSH port --
    cheap, and independent of any one service running on it."""
    hit, cached = _NODE_CACHE.hit()
    if hit:
        return cached
    t = timeout or 5
    try:
        s = socket.create_connection((WIN10_NODE_HOST, 22), timeout=t)
        s.close()
        res = {'ok': True, 'text': f'Win10 WSL node {WIN10_NODE_HOST} reachable (ssh:22).'}
    except Exception as e:
        res = {'ok': False,
               'text': f'Win10 WSL node {WIN10_NODE_HOST} OFFLINE — Letta, Frita SDK and '
                       f'Logger API are all blocked by this. Click Restart to revive the '
                       f'WSL node (restarts tailscaled via the Windows host). ({e})'}
    return _NODE_CACHE.put(res)


def restart_win10_node(*, deps: Collaborators):
    """Revive the Win10 WSL node by restarting tailscaled inside the distro from
    the (still-online) Windows host -- yesterday's manual recovery, as a button."""
    cmd = f'wsl.exe -d {WIN10_WSL_DISTRO} -u root -- bash -lc "systemctl restart tailscaled"'
    deps.log_restart(f'win10-node: ssh {WIN10_WINDOWS_HOST} {cmd}')
    try:
        with open(deps.restart_log_path, 'a') as logf:
            subprocess.Popen(
                ['ssh', '-o', 'ConnectTimeout=10', '-o', 'BatchMode=yes', WIN10_WINDOWS_HOST, cmd],
                stdout=logf, stderr=subprocess.STDOUT, start_new_session=True)
        mark_server_starting('win10-node')
        _NODE_CACHE.invalidate()   # force a fresh probe next poll
        return {'ok': True, 'text': f'Restarting tailscaled in WSL via {WIN10_WINDOWS_HOST} — '
                                    'node should reappear within ~15s.'}
    except Exception as e:
        return {'ok': False, 'text': f'win10-node restart error: {e}'}


# ── What are its containers doing? ───────────────────────────────────────────
def win10_container_states(timeout=10):
    """One cached `docker ps -a` on the box -> {container_name: status_string}.
    The status string already carries exit code + restart count from Docker."""
    hit, cached = _CONTAINERS_CACHE.hit()
    if hit:
        return cached
    states = {}
    try:
        r = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=8', '-o', 'BatchMode=yes', LETTA_DOCKER_HOST,
             'docker', 'ps', '-a', '--format', '{{.Names}}|{{.Status}}'],
            capture_output=True, text=True, timeout=timeout)
        for line in (r.stdout or '').splitlines():
            if '|' in line:
                name, status = line.split('|', 1)
                states[name.strip()] = status.strip()
    except Exception:
        states = {}
    return _CONTAINERS_CACHE.put(states)


def container_status_for(key, states):
    """Human container-status summary for a server key, or '' if not a Docker
    server or the probe failed. e.g. 'letta-server: Exited (139) 54 minutes ago'."""
    names = WIN10_CONTAINERS.get(key)
    if not names or not states:
        return ''
    parts = [f'{n}: {states[n]}' for n in names if n in states]
    return ' · '.join(parts)


# ── Is its dockerd up, and can we start it? ──────────────────────────────────
def ensure_win10_docker(timeout=45):
    """Recover the Win10 box's native dockerd when it dies on a stale pid file --
    the recurring failure behind "Frita HTTP 404 / :8799 down" (see
    frita_executor_ghost_container memory, 2026-06-22): remove the stale
    /var/run/docker.pid, reset the failed unit, start it. Idempotent + safe to
    call before any Win10-docker restart. Returns {ok, text}."""
    cmd = ('sudo -n rm -f /var/run/docker.pid; '
           'sudo -n systemctl reset-failed docker.service 2>/dev/null; '
           'sudo -n systemctl start docker.service 2>&1; '
           'sleep 2; systemctl is-active docker.service')
    try:
        r = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=10', '-o', 'BatchMode=yes',
             LETTA_DOCKER_HOST, 'bash', '-lc', cmd],
            capture_output=True, text=True, timeout=timeout)
        out = ((r.stdout or '') + (r.stderr or '')).strip()
        last = (r.stdout or '').strip().splitlines()[-1].strip() if (r.stdout or '').strip() else ''
        return {'ok': last == 'active', 'text': out[-200:] or 'no output'}
    except Exception as e:
        return {'ok': False, 'text': f'ensure docker error: {e}'}
    finally:
        # We just tried to start dockerd, so any cached opinion about dockerd is
        # stale whichever way it went. This is what keeps the now-cacheable
        # "unknown" (see Win10CacheEntry) from pinning a recovered box in the
        # host_unreachable state for the rest of its TTL.
        _DOCKER_CACHE.invalidate()


def win10_docker_ok(timeout=8):
    """Return True (active) / False (down) / None (unknown) for the Win10 dockerd.
    Cached for WIN10_DOCKER_CACHE_TTL so it doesn't SSH on every health poll --
    including when the answer is None, which is when it matters most."""
    hit, cached = _DOCKER_CACHE.hit()
    if hit:
        return cached
    val = None
    try:
        r = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=8', '-o', 'BatchMode=yes',
             LETTA_DOCKER_HOST, 'systemctl', 'is-active', 'docker.service'],
            capture_output=True, text=True, timeout=timeout)
        val = (r.stdout.strip() == 'active')
    except Exception:
        val = None
    return _DOCKER_CACHE.put(val)
