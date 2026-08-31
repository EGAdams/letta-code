"""Where a manually-entered document is expected to be filed.

Pure naming/path computation only -- no I/O, no subprocess. Split out of
finance/manual_entry.py (which orchestrates the actual save subprocess) once
that file passed ~250 lines: this is a distinct seam, computation vs
orchestration, and staying pure keeps it cheap enough to call on every form
field change for a live path preview.
"""
from __future__ import annotations

import calendar
import os
import re
from datetime import date

# 'receipt' is the only kind parse_and_categorize.py --save actually writes
# to today -- it has no --archive-root flag, so a document saved through the
# manual-entry form always lands under readable_documents/receipts
# regardless of what the operator picks in the form's "File as" dropdown.
# 'scanned_document' has no writer at all yet: it exists so the path preview
# can show operators an *intended* destination for multi-expense documents,
# not a real one -- see preview_archive_path.
ARCHIVE_ROOTS = {
    'receipt': os.path.expanduser('~/rol_finances/readable_documents/receipts'),
    'scanned_document': os.path.expanduser(
        '~/rol_finances/readable_documents/scanned_documents'),
}
REAL_ARCHIVE_KINDS = frozenset({'receipt'})


def slugify_like_receipt_tool(value: str) -> str:
    """Exact port of parse_and_categorize.py's slugify(): lowercase, '/' ->
    space, non-alphanumeric -> '_', collapse repeats, strip.

    Ported rather than imported -- parse_and_categorize.py has heavy
    top-level imports (Gemini engine, DB repos, the receipt_scanner
    package), too heavy to load just for two pure string functions that
    need to run cheaply on every form field change.
    """
    value = (value or '').lower().replace('/', ' ')
    formatted = ''.join(ch if ch.isalnum() else '_' for ch in value)
    while '__' in formatted:
        formatted = formatted.replace('__', '_')
    return formatted.strip('_')


def build_id_light(merchant_or_vendor_key: str, transaction_date: str,
                   total_amount: float) -> str:
    """Exact port of parse_and_categorize.py's _build_id_light(), for the
    ISO-date/numeric-amount shape the manual-entry form always has.
    Byte-for-byte compatible so a preview here always matches the filename
    --save produces for the same inputs.
    """
    slug = slugify_like_receipt_tool(merchant_or_vendor_key) or 'receipt'
    parsed = date.fromisoformat(transaction_date)
    date_token = parsed.strftime('%m_%d_%y')
    amount_token = f'{float(total_amount):.2f}'.replace('.', '_')
    return f'{slug}_{date_token}_{amount_token}'


_ID_LIGHT_DATE_AMOUNT_SUFFIX = re.compile(r'_\d{2}_\d{2}_\d{2}_\d+_\d+$')


def vendor_prefix_from_id_light(id_light: str) -> str:
    """The vendor slug half of an id_light, with its _MM_DD_YY_D_CC suffix
    stripped -- the part build_id_light needs to reuse when only the date or
    amount changed, so a corrected row keeps the vendor identity its receipt
    was actually filed under rather than one re-derived from a possibly-edited
    description."""
    return _ID_LIGHT_DATE_AMOUNT_SUFFIX.sub('', id_light or '')


def preview_archive_path(image_path: str, merchant_or_vendor_key: str,
                         transaction_date: str, total_amount: float,
                         archive_kind: str = 'receipt',
                         custom_root: str | None = None) -> dict:
    """Where this document is expected to be filed.

    Mirrors move_receipt_to_month_day_dir()'s
    {year}/{month_name}/{month_name}_{DD}/ nesting exactly. Returns
    {'path', 'is_real_destination'} -- is_real_destination is True only for
    archive_kind='receipt', the one kind the real --save call actually
    writes to today (see ARCHIVE_ROOTS above); the caller should show a
    "preview only" note for anything else. custom_root (an operator-typed
    "Other folder" path) is never a real destination either, for the same
    reason -- it overrides only where the preview shows the file going, not
    where --save actually puts it.
    """
    root = (custom_root or '').strip() or ARCHIVE_ROOTS.get(
        archive_kind, ARCHIVE_ROOTS['receipt'])
    parsed = date.fromisoformat(transaction_date)
    id_light = build_id_light(merchant_or_vendor_key, transaction_date, total_amount)
    month_name = calendar.month_name[parsed.month].lower()
    day_token = f'{parsed.day:02d}'
    extension = os.path.splitext(image_path or '')[1] or '.jpg'
    path = f'{root}/{parsed.year}/{month_name}/{month_name}_{day_token}/{id_light}{extension}'
    is_real = not (custom_root or '').strip() and archive_kind in REAL_ARCHIVE_KINDS
    return {'path': path, 'is_real_destination': is_real}
