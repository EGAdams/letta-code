"""Vendor review: pick a vendor_key for a receipt that saved with no category.

Companion to the FAIL-CLOSED CATEGORY RULE in build_mazda_scan_message(): when
Mazda can't resolve a vendor/category, parse_and_categorize.py now still saves
the receipt image + an expense row with category_id=NULL,
expense_status='NEEDS_VENDOR_KEY' (see save_receipt_pending_vendor_review() in
rol_finances) instead of dropping the document. These functions back the
dashboard's "pick a vendor" dialog that finishes the save later.

get_connection, receipt_url_for_path and vendor_lookup are server.py's, so all
three are injected rather than imported back -- keeping this module's tests
independent of a live database, of server.py's receipt-mount configuration,
and of the real vendor_category.yaml.
"""
from __future__ import annotations

from typing import Callable, Optional

from pydantic import BaseModel, ConfigDict


class PendingVendorReviewRow(BaseModel):
    """One row of the 'pick a vendor' dialog's list.

    `image_url` is None both when there is no source_file on record AND when
    the file has since gone missing on disk -- the two are indistinguishable
    to the dialog, which just omits the thumbnail either way.
    """
    model_config = ConfigDict(extra='forbid')
    expense_id: int
    expense_date: str = ''
    amount: str = ''
    description: str = ''
    receipt_url: str = ''
    image_url: Optional[str] = None


def list_vendor_keys(vendor_category_lookup: Callable):
    """Every known vendor_key + category, for the "pick a vendor" dialog."""
    try:
        return {'ok': True, 'vendor_keys': vendor_category_lookup().list_vendor_keys()}
    except Exception as e:
        return {'ok': False, 'error': f'Could not load vendor_category.yaml: {e}', 'vendor_keys': []}


def list_pending_vendor_review(get_connection: Callable, receipt_url_for_path: Callable,
                                path_isfile: Callable = None):
    """Expenses saved with no category (expense_status=NEEDS_VENDOR_KEY)."""
    import os
    path_isfile = path_isfile or os.path.isfile

    try:
        with get_connection() as cnx:
            with cnx.cursor() as cur:
                cur.execute(
                    "SELECT id, expense_date, amount, description, receipt_url, "
                    "document_url, moms_ledger, source_file "
                    "FROM expenses WHERE expense_status='NEEDS_VENDOR_KEY' "
                    "ORDER BY expense_date DESC"
                )
                rows = cur.fetchall()
    except Exception as e:
        return {'ok': False, 'error': f'DB error: {e}', 'rows': []}

    out = []
    for r in rows:
        image_url = None
        source_file = r.get('source_file')
        if source_file and path_isfile(source_file):
            try:
                image_url = receipt_url_for_path(source_file)
            except Exception:
                image_url = None
        out.append(PendingVendorReviewRow(
            expense_id=r['id'],
            expense_date=str(r.get('expense_date') or ''),
            amount=str(r.get('amount') or ''),
            description=r.get('description') or '',
            receipt_url=r.get('receipt_url') or '',
            image_url=image_url,
        ).model_dump())
    return {'ok': True, 'rows': out}


def set_receipt_vendor(get_connection: Callable, vendor_category_lookup: Callable,
                        expense_id, vendor_key):
    """Resolve a human-picked vendor_key to a category_id and finish the save."""
    try:
        expense_id = int(expense_id)
    except (TypeError, ValueError):
        return {'ok': False, 'error': f'Bad expense_id: {expense_id!r}'}
    vendor_key = (vendor_key or '').strip()
    if not vendor_key:
        return {'ok': False, 'error': 'vendor_key is required'}

    try:
        category_id = vendor_category_lookup().get_category_id(vendor_key)
    except Exception as e:
        return {'ok': False, 'error': f'Could not load vendor_category.yaml: {e}'}
    if category_id is None:
        return {'ok': False, 'error': f'Unknown vendor_key: {vendor_key}'}

    try:
        with get_connection() as cnx:
            with cnx.cursor() as cur:
                cur.execute(
                    "UPDATE expenses SET category_id=%s, expense_status='NONE' WHERE id=%s",
                    (category_id, expense_id),
                )
    except Exception as e:
        return {'ok': False, 'error': f'DB error: {e}'}

    return {'ok': True, 'expense_id': expense_id, 'category_id': category_id}
