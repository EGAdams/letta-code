"""Exactly one Mazda dispatch per (scanner, image file, image mtime).

Both the server's own post-scan auto-dispatch and the frontend's
POST /api/process-document funnel through process_scanned_document; whichever
arrives second sees the claim and skips the dispatch. ``claims``/``claims_lock``
are the shared in-process claim table, handed over by reference (not rebuilt)
since a lock only works against exactly one contended resource.
"""

from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass
from typing import Callable

#: How long a byte-identical rescan is treated as "the same dispatch action
#: retried" (the frontend's own POST racing the server's auto-dispatch, or an
#: old browser retrying after a mid-scan restart) rather than "the operator
#: genuinely rescanned this page again". Past this window a matching hash no
#: longer proves it's the same action, so the scan must reach Mazda and go
#: through the real (date, amount) duplicate check like any other document --
#: suppressing it here forever, silently, is the bug this guards against.
SCAN_DISPATCH_DEDUP_WINDOW_SEC = 300


@dataclass(frozen=True)
class Collaborators:
    """What stays behind in server.py, handed over per call."""

    get_scanner_intake: Callable
    claims: dict
    claims_lock: object
    dedup_window_sec: float = SCAN_DISPATCH_DEDUP_WINDOW_SEC


def scan_content_sha256(image_path):
    try:
        digest = hashlib.sha256()
        with open(image_path, 'rb') as src:
            for chunk in iter(lambda: src.read(1024 * 1024), b''):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return ''


def may_retry_terminal_scan(deps: Collaborators, previous, content_sha256):
    """Retry-policy Strategy for a byte-identical scanner document.

    A successful or active intake owns its fingerprint *for a short window*
    (see SCAN_DISPATCH_DEDUP_WINDOW_SEC) — long enough to absorb the known
    same-action double-fire, not long enough to permanently swallow a later,
    legitimate rescan. A terminal failure never owns its fingerprint:
    operators must always be able to retry the same legitimate page after
    its infrastructure or orchestration failure is repaired.
    """
    if not previous or previous.get('content_sha256') != content_sha256:
        return True
    if str(previous.get('status') or '').lower() in {'fail', 'stalled'}:
        return True
    dispatched_at = previous.get('dispatched_at')
    if not dispatched_at:
        return False
    return (time.time() - dispatched_at) > deps.dedup_window_sec


def claim_scan_dispatch(deps: Collaborators, key, image_path, content_sha256=None):
    """Claim a scanner image once, including across dashboard restarts."""
    try:
        stat = os.stat(image_path)
    except OSError:
        return False
    content_sha256 = content_sha256 or scan_content_sha256(image_path)
    claim = (image_path, stat.st_mtime_ns, stat.st_size, content_sha256)
    with deps.claims_lock:
        if deps.claims.get(key) == claim:
            return False
        # The in-memory claim is lost on a service restart. The per-scanner
        # intake pointer persists the immutable content fingerprint, so an old
        # browser cannot redispatch the same output file after the restart.
        previous = deps.get_scanner_intake(key)
        if (content_sha256 and
                not may_retry_terminal_scan(deps, previous, content_sha256)):
            return False
        deps.claims[key] = claim
        return True


def release_scan_dispatch(deps: Collaborators, key, image_path):
    """Undo a claim whose dispatch failed (e.g. staging error) so a retry of
    the same image can dispatch."""
    with deps.claims_lock:
        claimed = deps.claims.get(key)
        if claimed and claimed[0] == image_path:
            del deps.claims[key]
