"""What a Letta agent or conversation id is allowed to look like.

One pattern, in one place, because two very different call sites depend on it
and both are reachable from a browser.

`terminal/` types the id straight into a pty as part of a shell command line,
so anything outside this class is command injection with a shell already
waiting for it. `letta_code/runner.py` passes it as an argv element to the CLI,
where the risk is lower but the guard is the same one.

Deliberately narrower than "whatever Letta accepts": the set is
`[A-Za-z0-9_-]`, anchored at both ends, which excludes the space, quote,
backtick, `$(`, `;`, `|`, `&`, backslash and `..` that the terminal tests
enumerate one by one.
"""

from __future__ import annotations

import re

TERMINAL_ID_RE = re.compile(r'^[A-Za-z0-9_-]+$')

#: Historical name; the terminal upgrade path and its tests reach it as
#: `srv._TERMINAL_ID_RE`.
_TERMINAL_ID_RE = TERMINAL_ID_RE
