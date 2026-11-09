"""Compute the deed's one active passage from persisted focus, with legacy fallback.

The browser (``js/boot/notes.js`` ``isActiveAttorneyWarning``/``ACTIVE_ATTORNEY_WARNING_RE``) paints
exactly one kind of line with a blinking background instead of the ordinary static yellow
``<mark>``: a bracketed "...VERIFY WITH ... ATTORNEY/PROBATE COURT..." sentence, but only while it
sits inside the "Authority of the Personal Representative" section. Every other open placeholder on
the page -- the ten ``notes_review_marks.py`` categories (preparer, legal-description, tax-language,
open-item) -- stays a plain static mark and never blinks. The two are never the same line: the
browser only considers a line for the active/blinking treatment after it has already qualified as a
review-mark line (``deedReviewKind``), so this module calls ``notes_review_marks.review_kind`` for
that first test rather than re-deriving it.

This is a port, so ``tests/test_notes_active_warning.py`` includes a cross-check that runs both
implementations over the same fixture and fails if they ever disagree.
"""
from __future__ import annotations

import re

import notes_review_focus
from notes_review_marks import is_deed, review_kind

_ACTIVE_WARNING_RE = re.compile(
    r"^\s*\[.*\bVERIFY WITH\b.*\b(?:ATTORNEY|PROBATE COURT)\b.*\]\s*$", re.I
)
_AUTHORITY_SECTION_RE = re.compile(r"authority\s+of\s+the\s+personal\s+representative", re.I)
_HEADING = re.compile(r"^#{1,4}\s+(.*)$")
_ITEM = re.compile(r"^[-*]\s+(.*)$")


def is_active_warning(line: str, section_heading: str) -> bool:
    """Mirrors js/boot/notes.js's isActiveAttorneyWarning exactly."""
    return bool(_AUTHORITY_SECTION_RE.search(section_heading or "")) and bool(
        _ACTIVE_WARNING_RE.match(line)
    )


def active_warnings(filename: str, source: str) -> list[dict]:
    """Every line the browser renders with the blinking ``.notes-deed-review-active-line`` class, in
    reading order. Empty for any note other than the Personal Representative's Deed, and empty
    whenever that note currently holds no such line -- it is never guessed or assumed present."""
    if not is_deed(filename, source):
        return []
    focus, explicit_focus = notes_review_focus.focus_marker(source)
    found: list[dict] = []
    section_heading = ""
    in_mermaid = False
    for number, raw in enumerate(re.split(r"\r?\n", source), 1):
        if notes_review_focus.is_marker_line(raw):
            continue
        if raw.strip() == "```mermaid":
            in_mermaid = True
            continue
        if in_mermaid:
            in_mermaid = raw.strip() != "```"
            continue
        if not raw.strip():
            continue
        heading = _HEADING.match(raw)
        item = _ITEM.match(raw)
        if heading:
            section_heading = heading.group(1)
        line = heading.group(1) if heading else item.group(1) if item else raw
        selected = (
            review_kind(line) and (line == focus)
            if explicit_focus
            else is_active_warning(line, section_heading)
        )
        if selected:
            found.append({"line": number, "text": line})
    if explicit_focus and len(found) != 1:
        return []
    return found


def active_warning(filename: str, source: str) -> dict | None:
    """The single active/blinking passage, or ``None`` if the note holds none right now.

    The live deed note is expected to hold at most one such line, but this function never assumes
    that -- if more than one line currently qualifies, it returns the first in reading order, not
    "the" count. Call ``active_warnings`` for every qualifying line.
    """
    found = active_warnings(filename, source)
    return found[0] if found else None
