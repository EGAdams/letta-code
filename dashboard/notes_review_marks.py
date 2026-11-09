"""The Personal Representative's Deed page's *review marks*, for Bridge callers.

The browser (``js/boot/notes.js`` ``deedReviewKind``) paints a yellow ``<mark>`` on any line of that one
document that still holds something unresolved -- a ``[BRACKETED]`` placeholder, "NOT VERIFIED" or
"VERIFY". Nothing is saved in the note for this, so ``notes_highlights`` (persisted spans) cannot see it.
This module applies the *same rule* to the saved text so ChatGPT and Toyota can read exactly what the page
shows, and clear a mark the way a person does: by resolving the text. Clearing is therefore an ordinary
edit; the mark disappears on the page's next 3 s poll.

It is a port, so ``tests/test_notes_review_marks.py`` runs both implementations over the same fixture and
fails if they ever disagree.
"""
from __future__ import annotations

import re

import notes_review_focus

UNRESOLVED = re.compile(r"\[[^\]\n]*\]|not\s+verified|\bverify\b", re.I)
_PREPARER = re.compile(r"prepared\s+by|preparer|personal representative|\bpr\b")
_LEGAL = re.compile(r"legal description|property description|parcel description|parcel\s+(?:no|number)|tax parcel")
_TAX = re.compile(r"transfer[- ]tax|property[- ]tax|tax exemption|tax-exempt|uncapping")
_BANNER = re.compile(r"items in \[brackets\]", re.I)
_BLANK = re.compile(r"\[_*[A-Z]*_*\]")
_STILL_OPEN = re.compile(r"not\s+verified|\bverify\b|\[[^\]\n]*[A-Za-z][^\]\n]*\]", re.I)
_DEED_TITLE = re.compile(r"personal representative(?:'s)?\s+deed|deed of distribution", re.I)
_HEADING = re.compile(r"^#{1,4}\s+(.*)$")
_ITEM = re.compile(r"^[-*]\s+(.*)$")
WHY = {
    "preparer": "the preparer / personal representative line still has an open placeholder",
    "legal-description": "the legal description / parcel line still has an open placeholder",
    "tax-language": "the tax language still has an open placeholder",
    "open-item": "an open placeholder, NOT VERIFIED or VERIFY note still needs a person",
}


def is_deed(filename: str, source: str) -> bool:
    return "deed" in (filename or "").lower() and bool(_DEED_TITLE.search(source or ""))


def review_kind(line: str) -> str:
    if not UNRESOLVED.search(line):
        return ""
    text = line.lower()
    if _PREPARER.search(text):
        return "preparer"
    if _LEGAL.search(text):
        return "legal-description"
    if _TAX.search(text):
        return "tax-language"
    if _BANNER.search(line):
        return ""
    if not _STILL_OPEN.search(_BLANK.sub("", line)):
        return ""
    return "open-item"


def review_marks(filename: str, source: str) -> list[dict]:
    """One entry per line the browser would mark, in reading order. Empty for any other note."""
    if not is_deed(filename, source):
        return []
    marks, in_mermaid = [], False
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
        heading, item = _HEADING.match(raw), _ITEM.match(raw)
        line = heading.group(1) if heading else item.group(1) if item else raw
        kind = review_kind(line)
        if kind:
            marks.append({"line": number, "kind": kind, "text": line, "reason": WHY[kind],
                          "to_clear": "edit this line so no [bracket], NOT VERIFIED or VERIFY text remains"})
    return marks
