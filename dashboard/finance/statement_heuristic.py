"""Pure heuristic: does OCR'd receipt text actually look like a statement?

"Prefill from OCR" already runs a zero-token local OCR pass before the
operator touches anything (parse_and_categorize.py's local fallback). This
module reads that same raw text -- no extra call, no extra cost -- and flags
when it looks less like one receipt and more like a multi-transaction
statement table, so the form can nudge the operator toward Break Up Document
instead of silently filling one field and hiding the rest of the page.

A receipt legitimately carries several dollar amounts (subtotal, tax, tip,
total) but rarely a DATE next to more than one of them -- a statement's
transaction table is the opposite: every row repeats a date beside its own
amount. Requiring both on the SAME line, over at least two separate lines, is
what keeps this from firing on an ordinary itemized grocery receipt.
"""
from __future__ import annotations

import re

_DATE_PATTERN = re.compile(r'\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b|\b\d{4}-\d{2}-\d{2}\b')
_AMOUNT_PATTERN = re.compile(r'\$\s?\d{1,3}(?:,\d{3})*\.\d{2}\b')

#: Two qualifying lines is enough to say "this isn't one transaction" --
#: a single date+amount pairing is exactly what an ordinary receipt's own
#: date/total line looks like, so one match alone proves nothing.
MULTI_TRANSACTION_LINE_THRESHOLD = 2


def count_dated_amount_lines(raw_text: str) -> int:
    """How many lines carry both a date-like token and a dollar amount."""
    if not raw_text:
        return 0
    return sum(
        1 for line in raw_text.splitlines()
        if _DATE_PATTERN.search(line) and _AMOUNT_PATTERN.search(line)
    )


def looks_like_multiple_transactions(raw_text: str) -> bool:
    """True when the OCR text reads like a statement's transaction table."""
    return count_dated_amount_lines(raw_text) >= MULTI_TRANSACTION_LINE_THRESHOLD
