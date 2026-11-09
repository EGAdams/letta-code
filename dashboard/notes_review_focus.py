"""Persisted, non-rendered selection for the one pulsing deed review item."""
from __future__ import annotations

import re

_MARKER_RE = re.compile(r"^\s*<!--\s*notes-review-focus:\s*(.*?)\s*-->\s*$", re.I)


def focus_marker(source: str) -> tuple[str | None, bool]:
    """Return (exact target, marker_present); malformed/empty markers clear focus."""
    for line in source.splitlines():
        match = _MARKER_RE.match(line)
        if match:
            target = match.group(1)
            return (target if target else None), True
    return None, False


def is_marker_line(line: str) -> bool:
    return bool(_MARKER_RE.match(line))


def without_markers(source: str) -> str:
    """Remove focus metadata from a rendered/exported text representation."""
    return "\n".join(line for line in source.splitlines() if not is_marker_line(line))
