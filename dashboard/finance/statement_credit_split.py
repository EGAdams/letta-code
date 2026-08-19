"""Mirrors store_statement_transactions.py's split_expenses_and_credits, for
display purposes only.

The store stays the sole authority on what gets stored: Save All always
submits every row read off the page, unfiltered, and the store re-derives this
exact split from the complete row set when it decides what to keep or skip.
This module exists only to keep an obvious payment or a printed $0.00 line off
the operator's Prev/Next review list -- "PAYMENT - THANK YOU $2,900.00" and
"Interest Charge on Purchases $0.00" were never expenses needing a category,
and the store was always going to skip both; showing them as navigable items
just made the operator wonder what to file them under.
"""

from __future__ import annotations

import re

_CREDIT_PATTERN = re.compile(
    r"payment|autopay|thank you|\bcredit\b|\bdeposit\b|\brefund\b|\bcr\b",
    re.IGNORECASE,
)


def reviewable_flags(rows: list[tuple[float, str]]) -> list[bool]:
    """One flag per (amount, description) row, using the WHOLE page's signs.

    ``rows`` must be every row on the page, in order: the mixed-sign rule below
    only applies once at least one amount is positive AND at least one is
    negative (a page that is all-purchases, or the rarer all-credits, falls
    back to the same description pattern) -- exactly
    split_expenses_and_credits's own rule, over the same set.
    """
    amounts = [amount for amount, _ in rows]
    has_neg = any(amount < 0 for amount in amounts)
    has_pos = any(amount > 0 for amount in amounts)
    flags = []
    for amount, description in rows:
        if amount == 0:
            flags.append(False)
            continue
        if has_neg and has_pos:
            is_credit = amount > 0
        else:
            is_credit = bool(_CREDIT_PATTERN.search(description))
        flags.append(not is_credit)
    return flags
