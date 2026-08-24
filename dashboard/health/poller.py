"""Debounced, background-polled server health cache.

/api/server-health is hit by the frontend every 5s. Probing every configured
server synchronously inside that request made the status LED flap red/green
as individual probes randomly raced the request's timeout. Instead a
background thread polls all active-check servers on its own cadence, and a
server only flips to "down" after HEALTH_FAIL_THRESHOLD consecutive
failures -- a single slow/dropped probe no longer flashes the LED red.

`SERVERS` and `server_health` stay in server.py (the SSH-checks / server-mgmt
registry clusters), so both are passed in rather than imported, to avoid a
cycle and to keep this module's tests independent of live server config.
"""

import threading
import time
from typing import Callable, Optional

from pydantic import BaseModel, ConfigDict

HEALTH_POLL_INTERVAL = 8
HEALTH_CHECK_TIMEOUT = 10
HEALTH_FAIL_THRESHOLD = 2


class HealthCacheEntry(BaseModel):
    """One server's debounced status.

    `result` only replaces the last-good result on a fresh success, or once
    `fails` reaches HEALTH_FAIL_THRESHOLD -- an isolated failed probe keeps
    showing the previous good result rather than flipping the LED on a
    single miss.
    """
    model_config = ConfigDict(extra='forbid')
    fails: int = 0
    result: Optional[dict] = None


class HealthPoller:
    """Owns the cache and its lock. server.py wires one instance at boot."""

    def __init__(self):
        self._cache: dict[str, HealthCacheEntry] = {}
        self._lock = threading.Lock()

    def poll_all_once(self, servers, server_health: Callable):
        for cfg in servers:
            if not (cfg.get('health_url') or cfg.get('tcp_check') or cfg.get('check')):
                continue
            h = server_health(cfg, timeout=HEALTH_CHECK_TIMEOUT)
            with self._lock:
                entry = self._cache.get(cfg['key'], HealthCacheEntry())
                if h.get('ok'):
                    entry = HealthCacheEntry(fails=0, result=h)
                else:
                    fails = entry.fails + 1
                    result = h if (entry.result is None or fails >= HEALTH_FAIL_THRESHOLD) else entry.result
                    entry = HealthCacheEntry(fails=fails, result=result)
                self._cache[cfg['key']] = entry

    def poll_loop(self, servers_getter: Callable, server_health: Callable):
        """Background daemon thread body: keep the health cache fresh."""
        while True:
            self.poll_all_once(servers_getter(), server_health)
            time.sleep(HEALTH_POLL_INTERVAL)

    def cached(self, cfg, server_health: Callable):
        """Debounced health result for cfg from the background poll loop.

        Falls back to a synchronous (slow) probe on first access, before the
        background loop has populated the cache. Returns None for configs
        with neither health_url nor tcp_check, like server_health does.
        """
        if not (cfg.get('health_url') or cfg.get('tcp_check') or cfg.get('check')):
            return None
        with self._lock:
            entry = self._cache.get(cfg['key'])
        if entry is not None:
            return entry.result
        h = server_health(cfg, timeout=HEALTH_CHECK_TIMEOUT)
        with self._lock:
            self._cache[cfg['key']] = HealthCacheEntry(fails=0 if h.get('ok') else 1, result=h)
        return h
