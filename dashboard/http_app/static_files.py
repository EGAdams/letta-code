"""Containment for the static-file fallthrough.

The last rule in do_GET serves any file found under the dashboard directory or
the repo root. It used to build that path with a bare
`os.path.join(base, path.lstrip('/'))`, which resolves `..` segments happily:

    GET /../../../../etc/passwd  ->  200, with the file's contents

The dashboard binds 0.0.0.0 and is reachable over Tailscale, so that exposed
anything readable by the serving user — `~/.config/mazda/finance-db.env`,
SSH keys, OAuth tokens. This module is the fix: a request only ever resolves to
a file that really lives inside one of the allowed roots.

Fails closed by design. Anything ambiguous — an escape, a symlink pointing out
of tree, an absolute path, a NUL byte — returns None and the caller 404s. A
static asset that cannot be proven to be in-tree is not served.
"""
import os


def _contained(candidate: str, root: str) -> bool:
    """True only if `candidate` is `root` itself or genuinely beneath it.

    Compares realpath-resolved strings with a separator guard, so a sibling
    directory that merely shares a prefix (`/srv/dashboard-old` vs
    `/srv/dashboard`) is not mistaken for a child.
    """
    return candidate == root or candidate.startswith(root + os.sep)


def resolve_static_asset(url_path: str, roots) -> str | None:
    """Map a URL path onto a real file inside `roots`, or None.

    Deliberately does NOT percent-decode: the pre-fix behaviour did not either,
    so `%2e%2e` stays a literal filename rather than becoming a traversal, and
    no asset that worked before changes meaning.
    """
    if not url_path or '\x00' in url_path:
        return None
    relative = url_path.lstrip('/')
    if not relative:
        return None
    for root in roots:
        try:
            root_real = os.path.realpath(root)
            candidate = os.path.realpath(os.path.join(root_real, relative))
        except (OSError, ValueError):
            continue
        if not _contained(candidate, root_real):
            continue          # escaped the root: .., an absolute path, a symlink
        if os.path.isfile(candidate):
            return candidate
    return None
