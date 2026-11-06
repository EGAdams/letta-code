"""A strict allowlist rich-text markup for notes -- not HTML.

The browser preview (js/boot/notes.js), the Word export
(notes_docx_export.py) and the email draft (notes_email_draft.py) all need
the same answer for "what does this note's markup mean." A note is plain
Markdown (headings, `-`/`*` bullets, **bold**, `` `code` ``) plus one more
inline span for color:

    {{color:red}}text{{/color}}
    {{highlight:yellow}}text{{/highlight}}

``name`` must be one of COLORS below. This is the sanitizer, not a separate
pass over it: nothing here ever emits a tag a note's own text supplied, so
an unknown color name or an unclosed span just renders as the literal
characters it is, rather than raising or producing markup the writer did
not intend. Color spans do not nest further markup (no **bold** inside a
color span) -- kept simple on purpose, since every consumer needs to agree.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

#: Fixed palette. A note's text names one of these; it never supplies its
#: own hex/CSS, so there is no color value to sanitize beyond this allowlist.
COLORS = {
    "red": "C0392B",
    "orange": "D35400",
    "yellow": "B7950B",
    "green": "1E8449",
    "blue": "1F618D",
    "purple": "6C3483",
    "gray": "616A6B",
    "black": "000000",
}

_SPAN = re.compile(r"\{\{(color|highlight):([a-z]+)\}\}(.*?)\{\{/\1\}\}")
_TOKEN = re.compile(r"\*\*(.+?)\*\*|`([^`]+)`|\*(?!\*)(.+?)(?<!\*)\*(?!\*)")


@dataclass(frozen=True)
class Segment:
    text: str
    bold: bool = False
    italic: bool = False
    code: bool = False
    color: str | None = None
    highlight: str | None = None


def _markdown_segments(text: str) -> list[Segment]:
    """Bold/italic/code only; no color span at this level (see module docstring)."""
    segments: list[Segment] = []
    pos = 0
    for match in _TOKEN.finditer(text):
        if match.start() > pos:
            segments.append(Segment(text[pos:match.start()]))
        bold, code, italic = match.groups()
        if bold is not None:
            segments.append(Segment(bold, bold=True))
        elif code is not None:
            segments.append(Segment(code, code=True))
        else:
            segments.append(Segment(italic, italic=True))
        pos = match.end()
    if pos < len(text) or not segments:
        segments.append(Segment(text[pos:]))
    return segments


def parse_segments(line: str) -> list[Segment]:
    """One line of note text -> ordered Segments. Never raises."""
    segments: list[Segment] = []
    pos = 0
    for match in _SPAN.finditer(line):
        if match.start() > pos:
            segments.extend(_markdown_segments(line[pos:match.start()]))
        kind, name, inner = match.group(1), match.group(2), match.group(3)
        if name in COLORS:
            segments.append(Segment(inner, color=name if kind == "color" else None,
                                     highlight=name if kind == "highlight" else None))
        else:
            # Unknown color name: the literal markup text, not a span.
            segments.append(Segment(line[match.start():match.end()]))
        pos = match.end()
    if pos < len(line):
        segments.extend(_markdown_segments(line[pos:]))
    return segments or [Segment("")]


def iter_highlight_spans(note_text: str):
    """Every ``{{highlight:name}}text{{/highlight}}`` span in note_text, in
    document order, with the exact character offsets of its inner text
    within note_text itself -- computed fresh from the string on every call,
    so there is no separate offset store that can drift from the text it
    describes across a save/reopen.

    Yields ``(name, text, start, end)``. An unknown color name is not a
    highlight (see module docstring) and is skipped, matching parse_segments.
    """
    for match in _SPAN.finditer(note_text):
        kind, name, inner = match.group(1), match.group(2), match.group(3)
        if kind == "highlight" and name in COLORS:
            yield name, inner, match.start(3), match.end(3)


def plain_text(note_text: str) -> str:
    """Note text with every markup token stripped, line breaks preserved."""
    lines = ("".join(segment.text for segment in parse_segments(line))
              for line in note_text.splitlines())
    return "\n".join(lines)
