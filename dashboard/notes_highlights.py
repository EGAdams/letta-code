"""Read-only derivation of a note's persisted highlights, for the Bridge.

"Highlighted" here means only what ``notes_formatting.iter_highlight_spans``
finds in the note's own saved text -- a ``{{highlight:name}}text{{/highlight}}``
span that travels inline with the text itself, so it is reconstructed the
same way on every read and never drifts from a separate offset store across
a save/reopen. A browser's current (unsaved) textarea selection has no way
to reach this module -- it never leaves the browser -- so it can never be
confused with one of these.

The Personal Representative's Deed page also renders auto-generated
``<mark>`` review highlighting (``js/boot/notes.js`` ``deedReviewKind``) for
sentences that merely look like a preparer line, legal description, or tax
language -- a view-only rendering decision keyed off the saved text's
content, not a span stored in it. Those are deliberately excluded here: this
module answers only "what highlight markup is actually saved in this note,"
not "how the browser currently decorates it for review."
"""
from __future__ import annotations

from dataclasses import dataclass

from notes_formatting import iter_highlight_spans, parse_segments

_CONTEXT_CHARS = 40


@dataclass(frozen=True)
class Highlight:
    text: str
    color: str
    line: int  # 1-based line number in the saved note text
    start: int  # character offset of `text` within the full note text
    end: int
    context_before: str
    context_after: str


def _line_context(raw_line: str, text: str) -> tuple[str, str]:
    """Surrounding text on the same line, with markup stripped (via
    parse_segments -- the same parser the preview/export/email renderers
    use) so a Bridge read-back never speaks ``{{highlight:...}}`` syntax.
    """
    plain_line = "".join(segment.text for segment in parse_segments(raw_line))
    pos = plain_line.find(text)
    if pos == -1:
        return "", ""
    before = plain_line[max(0, pos - _CONTEXT_CHARS):pos]
    after = plain_line[pos + len(text):pos + len(text) + _CONTEXT_CHARS]
    return before, after


def extract_highlights(note_text: str) -> list[Highlight]:
    """Every persisted highlight span in note_text, in reading order."""
    lines = note_text.splitlines()
    highlights = []
    for color, text, start, end in iter_highlight_spans(note_text):
        line_number = note_text.count("\n", 0, start) + 1
        raw_line = lines[line_number - 1] if 0 < line_number <= len(lines) else ""
        before, after = _line_context(raw_line, text)
        highlights.append(Highlight(text=text, color=color, line=line_number, start=start, end=end,
                                     context_before=before, context_after=after))
    return highlights


def highlights_payload(note_text: str) -> list[dict]:
    """JSON-safe shape for the Bridge façade: one dict per Highlight."""
    return [
        {"text": h.text, "color": h.color, "line": h.line, "start": h.start, "end": h.end,
         "context_before": h.context_before, "context_after": h.context_after}
        for h in extract_highlights(note_text)
    ]
