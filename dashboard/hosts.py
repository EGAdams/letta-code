"""The other machines this dashboard talks to.

Three modules independently needed the same two SSH destinations -- the Letta
box and mom's Rosemary46 -- and each had its own `os.environ.get` with its own
hardcoded fallback. That is a quiet way to end up polling one address and
reporting another after somebody overrides the env var in only one unit file.
They are read once, here.

Both are ssh destinations in `user@host` form, not bare hostnames: they are
passed straight to `ssh` as an argument, never joined into a URL.
"""

from __future__ import annotations

import os

#: The Windows 10 box running the Letta server stack (100.80.49.10).
LETTA_DOCKER_HOST = os.environ.get('LETTA_DOCKER_HOST', 'adamsl@100.80.49.10')

#: Mom's Rosemary46 Linux box (100.72.34.38). Reached over Tailscale, which
#: relays through DERP -- expect seconds of latency, not milliseconds.
R46_SSH_HOST = os.environ.get('R46_SSH_HOST', 'adamsl@100.72.34.38')

#: The Letta API this dashboard drives. A URL, unlike the two above -- it is
#: joined with request paths, so the trailing slash is stripped once here
#: rather than at each of the ~40 call sites.
LETTA_BASE_URL = os.environ.get(
    'LETTA_BASE_URL', 'http://100.80.49.10:8283').rstrip('/')
