"""Parsing for receipt filenames the intake pipeline writes.

Pure parsing only -- no I/O, no subprocess -- mirroring finance/archive_path.py's
split (which builds this same <vendor>_MM_DD_YY_<dollars>_<cents>.<ext> filename
shape from a date/amount; this module recovers the date/amount from an existing
filename, the other direction of the same contract). Split out of server.py's
_build_receipt_index(), which walks the real receipts/ tree on disk, so the
parsing rule itself is unit-testable without touching disk.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict

_RECEIPT_FILENAME_RE = re.compile(
    r'_(?P<mm>\d{2})_(?P<dd>\d{2})_(?P<yy>\d{2})_(?P<dollars>\d+)_(?P<cents>\d{2})'
    r'\.[A-Za-z0-9]+$')


class ReceiptMatchKey(BaseModel):
    """The (date, amount) join key embedded in a receipt filename -- the same
    pair _resolve_expense_receipt_path uses to link a receipt file back to an
    expenses row by (expense_date, amount) when receipt_url is missing/stale.

    A real calendar date via Pydantic's `date` type, rather than the raw regex
    digit groups trusted as-is: a filename with an impossible date (bad OCR-driven
    rename, hand-edited file) is rejected up front instead of silently entering
    the index under a key nothing will ever look up correctly.
    """
    model_config = ConfigDict(frozen=True)

    expense_date: date
    #: Kept as the exact 'D.CC' string the expenses.amount column and every
    #: caller's amount_str compare against -- a float would reintroduce the
    #: rounding drift this key exists to avoid.
    amount: str

    def index_key(self) -> tuple[str, str]:
        """The (str-date, str-amount) tuple the by_da index is keyed on."""
        return (self.expense_date.isoformat(), self.amount)


def parse_receipt_filename(filename: str) -> Optional[ReceiptMatchKey]:
    """Recover the (date, amount) key from a receipt filename, or None if it
    doesn't match the <vendor>_MM_DD_YY_<dollars>_<cents>.<ext> convention
    parse_and_categorize.py writes (e.g. a manually-dropped file with an
    unrelated name) or embeds an impossible calendar date."""
    match = _RECEIPT_FILENAME_RE.search(filename or '')
    if not match:
        return None
    try:
        parsed_date = date(2000 + int(match['yy']), int(match['mm']), int(match['dd']))
    except ValueError:
        return None
    return ReceiptMatchKey(
        expense_date=parsed_date,
        amount=f"{match['dollars']}.{match['cents']}",
    )
