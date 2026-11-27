"""GET /api/live-activity?machine=NAME&after=CURSOR -- agents and supervisors, as they work.

The reading is done by agent_blocks' `adws/adw_live_activity.py` (read-only, credential-filtered, SSH for
other machines); this adapter runs it and caches the answer briefly, so several open tabs cost one read and
another machine is not asked more than every few seconds. It owns no data and writes nothing.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path

LOCAL_CACHE_SECONDS = 0.5
REMOTE_CACHE_SECONDS = 4.0
TIMEOUT_SECONDS = 30
_cache: dict[tuple[str, int | None], tuple[float, dict]] = {}
_lock = threading.Lock()
_NAME = re.compile(r"^[A-Za-z0-9]{1,16}$")


def _command(after: int | None, machine: str) -> list[str]:
    package = Path(os.environ.get("ADW_AGENT_BLOCKS_PACKAGE", "~/agent_blocks/lancedb_memory")).expanduser()
    argv = [str(package / ".venv" / "bin" / "python"), str(package.parent / "adws" / "adw_live_activity.py")]
    if machine:
        argv += ["--machine", machine]
    if after is not None:
        argv += ["--after", str(after)]
    return argv


def _failed(machine: str, why: str, after: int | None) -> dict:
    return {"ok": False, "error": why, "machine": machine or "this machine", "cursor": after or 0,
            "agent_events": [], "supervisor_events": [], "gaps": [f"{machine or 'this machine'}: {why}"]}


def read(after: int | None, machine: str, run=subprocess.run, clock=time.monotonic) -> dict:
    if machine and not _NAME.match(machine):
        return _failed("", "not a machine name", after)
    key, now = (machine, after), clock()
    ttl = REMOTE_CACHE_SECONDS if machine else LOCAL_CACHE_SECONDS
    with _lock:
        held = _cache.get(key)
        if held and now - held[0] < ttl:
            return held[1]
    try:
        done = run(_command(after, machine), capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
        value = json.loads(done.stdout)
        if not isinstance(value, dict):
            raise ValueError("unexpected answer")
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        value = _failed(machine, f"live activity unavailable: {type(error).__name__}", after)
    with _lock:
        if len(_cache) > 64:
            _cache.clear()
        _cache[key] = (now, value)
    return value


def payload(query: dict) -> dict:
    try:
        after = max(0, int(query.get("after", [""])[0]))
    except (TypeError, ValueError, IndexError):
        after = None
    return read(after, (query.get("machine") or [""])[0].strip())
