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

The date half is the discriminating half, so it has to recognize every way a
date gets printed. It originally knew only 05/23 and 2025-05-23, which meant a
utility bill spelling its dates out ("Due September 05, 2025 $28.08") scored
zero and got no nudge at all.
"""
from __future__ import annotations

import re

#: Month names, full or abbreviated, so a bill that spells its dates out
#: ("Jul 14, 2025", "August 14, 2025") is read the same as one that prints
#: them numerically. Without this the whole DTE gas bill scored ZERO dated
#: lines and the Break Up Document nudge never fired -- see
#: test_dte_bill_with_month_name_dates_triggers.
_MONTH_NAMES = (
    r'jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|'
    r'jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|'
    r'nov(?:ember)?|dec(?:ember)?'
)
_DATE_PATTERN = re.compile(
    r'\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b'
    r'|\b\d{4}-\d{2}-\d{2}\b'
    rf'|\b(?:{_MONTH_NAMES})\.?\s+\d{{1,2}}(?:,?\s*\d{{4}})?\b',
    re.IGNORECASE,
)
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
