"""Per-connection SSH/Tailscale warning silencer.

Lets EG mute an SSH Connections tab's down-warning (e.g. the Chromebook A13
is a tablet that sleeps/roams off the tailnet constantly, so its "down" blink
is noise, not a real problem) without hiding the connection's actual reachability
on its detail panel -- muting only downgrades the *status* used for tab coloring.

Persisted as a flat {connection_key: true} JSON file so a mute survives a
dashboard restart. Mirrors model_stats_mute.py exactly -- same shape, same
overlay contract -- because this is the same problem (a noisy status driving a
blinking tab) on a different roster (SSH_CONNECTIONS instead of
MODEL_STAT_SOURCES). Deliberately doesn't import SSH_CONNECTIONS from
monitoring.ssh_checks -- `key` is just whatever the caller already validated
against that roster.
"""

from __future__ import annotations

import json
import os
import threading

from contracts import StrictModel

SSH_CONNECTION_MUTE_FILE = os.path.expanduser('~/.mazda/ssh_connection_muted.json')
_lock = threading.Lock()


class SshConnectionMuteRequest(StrictModel):
    """Body of POST /api/ssh-connection-mute."""

    key: str
    muted: bool


def _read() -> dict[str, bool]:
    try:
        with open(SSH_CONNECTION_MUTE_FILE, encoding='utf-8') as fh:
            data = json.load(fh)
        return {k: True for k, v in data.items() if v}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write(state: dict[str, bool]) -> None:
    os.makedirs(os.path.dirname(SSH_CONNECTION_MUTE_FILE), exist_ok=True)
    tmp = f'{SSH_CONNECTION_MUTE_FILE}.tmp.{os.getpid()}'
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(state, fh)
    os.replace(tmp, SSH_CONNECTION_MUTE_FILE)


def is_muted(key: str) -> bool:
    return _read().get(key, False)


def set_muted(key: str, muted: bool) -> bool:
    """Set the mute flag for `key`; returns the resulting value."""
    with _lock:
        state = _read()
        if muted:
            state[key] = True
        else:
            state.pop(key, None)
        _write(state)
    return muted


def apply_mute_overlay(conn: dict, key: str) -> dict:
    """Return a copy of a connection-health entry with `muted` attached and,
    while muted, its tab-facing `status` downgraded from 'down' to 'up' so the
    SSH Connections tab stops blinking -- the connection detail panel and its
    log tail read straight from monitoring.ssh_checks and never pass through
    this overlay, so they keep showing what's actually going on."""
    view = dict(conn)
    muted = is_muted(key)
    view['muted'] = muted
    if muted and view.get('status') == 'down':
        view['raw_status'] = view['status']
        view['status'] = 'up'
    return view
