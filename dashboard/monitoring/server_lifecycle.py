"""Two clocks the Server Management tab reads, and nothing else.

Both answer a question a single health probe cannot: *how long* has this been
true? A probe says "down right now"; these say "down for 54 minutes, and that
is long enough that someone should have noticed" and "restarted 8 seconds ago,
so red is a lie -- show yellow".

They are kept together because they are the same state machine seen from two
sides. `mark_server_starting` opens a grace window in which a failing probe is
forgiven; `track_down_duration` is the clock that runs once that forgiveness
has expired. Splitting them would let the two disagree about what 'starting'
means.

`SERVERS`, the probes and the restart handlers all stay in server.py -- this
module knows only server *keys*, so it has no import back and its tests need
no live server config.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Literal

from pydantic import TypeAdapter

#: The four states `compute_server_status` reduces a health result to.
#: `track_down_duration` has to branch on this vocabulary, so it is declared
#: once, here, rather than spelled out again as a tuple of strings inside the
#: branch -- see the validation note on `track_down_duration`.
ServerStatus = Literal['up', 'concern', 'starting', 'down']

_SERVER_STATUS = TypeAdapter(ServerStatus)

#: Non-healthy for longer than this and the tab escalates: nobody is watching.
#: Ten minutes is the observed gap between Letta dying and a human noticing.
SERVER_STALE_DOWN_SECONDS = 600

#: How long after a Restart click a failing probe is still read as 'starting'.
STARTING_WINDOW_SECONDS = 120

#: Servers currently inside the starting window. { key: datetime_marked }
_starting_servers: dict[str, datetime] = {}
_starting_lock = threading.Lock()

#: When each server was first seen non-healthy. { key: epoch_seconds }
#: Cleared on 'up'; the age of the entry is what "down for 54m" reports.
_server_down_since: dict[str, float] = {}
_server_down_lock = threading.Lock()


def track_down_duration(key, status):
    """Update/return how long `key` has been non-healthy. 'up' clears the clock;
    'starting' (transient) doesn't start one. Returns (down_for_seconds, stale).

    `status` is validated against `ServerStatus` rather than trusted. The two
    forgiven states are named positively here, so anything else -- a fifth
    state added to `compute_server_status`, a renamed one, a typo -- would fall
    through to the `else` and start a stale clock on a server that is fine,
    escalating a healthy tab after ten minutes with nothing to point at. That
    failure is invisible; a ValidationError is not.
    """
    _SERVER_STATUS.validate_python(status)
    with _server_down_lock:
        now = time.time()
        if status in ('up', 'starting'):
            if status == 'up':
                _server_down_since.pop(key, None)
            since = _server_down_since.get(key)
            return ((int(now - since), (now - since) >= SERVER_STALE_DOWN_SECONDS)
                    if since else (0, False))
        since = _server_down_since.get(key)
        if since is None:
            _server_down_since[key] = since = now
        dur = now - since
        return (int(dur), dur >= SERVER_STALE_DOWN_SECONDS)


def mark_server_starting(key):
    """Mark a server as 'starting' for the next STARTING_WINDOW_SECONDS."""
    with _starting_lock:
        _starting_servers[key] = datetime.now()


def clear_server_starting(key):
    """Drop the 'starting' mark — call this once a real health check succeeds
    so the UI can flip to 'up' immediately instead of waiting out the window."""
    with _starting_lock:
        _starting_servers.pop(key, None)


def is_server_starting(key):
    """Check if a server is in the 'starting' window."""
    with _starting_lock:
        if key not in _starting_servers:
            return False
        elapsed = (datetime.now() - _starting_servers[key]).total_seconds()
        if elapsed > STARTING_WINDOW_SECONDS:
            del _starting_servers[key]
            return False
        return True
