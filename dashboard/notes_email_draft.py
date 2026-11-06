"""Build an email-ready draft from a note. This never sends anything.

``build_email_draft`` only returns text: a subject, a plain-text body with
every markup token stripped (notes_formatting.plain_text), and a ``mailto:``
URL that opens in whoever reviews it's own mail client with that subject
and body prefilled. There is no SMTP client, no stored credential, and no
other code path here that can transmit a message -- sending it is a human
action in their own mail client, every time, which is the actual
"never send without explicit approval" guarantee: the capability to send
from this repository does not exist.
"""
from __future__ import annotations

from urllib.parse import quote

import notes_formatting

_SUBJECT_MAX = 120


def _subject(filename: str, note_text: str) -> str:
    for line in note_text.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped:
            return stripped[:_SUBJECT_MAX]
    return filename


def build_email_draft(filename: str, note_text: str, *, to: str = "") -> dict:
    subject = _subject(filename, note_text)
    body_text = notes_formatting.plain_text(note_text)
    query = f"subject={quote(subject)}&body={quote(body_text)}"
    recipient = quote(to) if to else ""
    return {
        "subject": subject,
        "body_text": body_text,
        "mailto_url": f"mailto:{recipient}?{query}",
    }
