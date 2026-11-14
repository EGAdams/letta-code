"""/api/nav-status — a change signature for the top-level sidebar.

dashboard.html is served fresh from disk on every request already (see the
CODE_WATCH_PATHS note in server.py: HTML/CSS/JS need no restart to take
effect). This just hashes the `<nav id="nav-main">` block of the file
currently on disk, so an already-open dashboard can poll for "the sidebar
changed" and patch itself, instead of the user having to notice and reload.
No caching, no process-wide state — whatever is on disk right now is the
answer.
"""
import hashlib
import os
import re

from paths import HERE

DASHBOARD_HTML = os.path.join(HERE, 'dashboard.html')

_NAV_MAIN_RE = re.compile(r'<nav id="nav-main">.*?</nav>', re.DOTALL)


def _nav_main_markup():
    try:
        with open(DASHBOARD_HTML, 'r', encoding='utf-8') as f:
            html = f.read()
    except OSError:
        return ''
    match = _NAV_MAIN_RE.search(html)
    return match.group(0) if match else ''


def nav_signature_payload():
    markup = _nav_main_markup()
    return {'signature': hashlib.sha256(markup.encode('utf-8')).hexdigest()}
