"""Where this checkout lives, and where the tools it shells out to live.

Pulled out of server.py so a module can know its own filesystem layout without
importing the whole service layer -- which, since server.py imports those
modules back, would be a cycle.

`LETTA_CODE_BUN` is an absolute path with an env override rather than a bare
`shutil.which('bun')` for one reason: dashboard-server.service runs with a
deliberately minimal PATH, and Bun's user install directory is not on it. A
lookup that works in an interactive shell finds nothing under systemd.
"""

from __future__ import annotations

import os

#: The dashboard/ directory itself.
HERE = os.path.dirname(os.path.abspath(__file__))

#: The letta-code checkout containing it.
REPO_ROOT = os.path.dirname(HERE)

#: Bun's stable user install path. Checked for existence before use; callers
#: fall back to PATH, then to a built letta.js.
LETTA_CODE_BUN = os.environ.get(
    'LETTA_CODE_BUN', os.path.expanduser('~/.bun/bin/bun'))

#: The rol_finances checkout the finance pipeline lives in. Not part of this
#: repo -- the dashboard reads its .env, its tools, and its own virtualenv.
ROL_FINANCES_DIR = os.path.expanduser('~/rol_finances')
