"""Resolving one report row's receipt and source-document metadata.

``lookup_receipt`` backs the "View Receipt" button: given a report row's
date/amount/vendor identity, find the matching expense and whatever receipt
or source document is on file for it. Everything it touches has an owning
module of its own, but each is either defined in server.py (the live DB
connection factory, the annotation-cache document resolvers) or extensively
monkeypatched by its `server.` name in tests to drive this function without a
real database or filesystem -- so all of it arrives as a ``Collaborators``
bundle built fresh per call, same reasoning as
``intake.mazda_dispatch.Collaborators``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable
from urllib.parse import urlparse


@dataclass(frozen=True)
class Collaborators:
    """What stays behind in server.py, handed over per call."""

    get_connection: Callable
    norm_amount: Callable
    matching_expense: Callable
    resolve_local_supporting_document: Callable
    viewable_supporting_document: Callable
    document_machine_origin: Callable
    source_document_path: Callable
    resolve_expense_receipt_path: Callable
    receipt_url_for_path: Callable


def lookup_receipt(deps: Collaborators, date_str, signed_amount, vendor_key,
                   description='', report_path='', expense_id=None):
    """Return receipt and source-document metadata for one report row."""
    amt = deps.norm_amount(signed_amount)
    if amt is None and expense_id in (None, ''):
        return {'ok': False, 'error': f'Bad amount: {signed_amount!r}'}
    chosen = None
    resolve_date = date_str
    try:
        with deps.get_connection() as cnx:
            with cnx.cursor() as cur:
                chosen = deps.matching_expense(
                    cur, date_str, amt, vendor_key, description, expense_id)
                if chosen is not None and expense_id not in (None, ''):
                    resolve_date = str(chosen.get('expense_date') or date_str)
                    amt = deps.norm_amount(chosen.get('amount')) or amt
                if chosen is None and date_str and expense_id in (None, ''):
                    try:
                        base = datetime.strptime(date_str, '%Y-%m-%d').date()
                        for delta in (-1, 1, -2, 2, -3, 3):
                            alt = (base + timedelta(days=delta)).isoformat()
                            c = deps.matching_expense(cur, alt, amt, vendor_key, description)
                            if c:
                                chosen = c
                                resolve_date = alt
                                break
                    except (ValueError, AttributeError):
                        pass
    except Exception as e:
        return {'ok': False, 'error': f'DB error: {e}'}

    document_reference = (
        (chosen.get('document_url') or '').strip() if chosen else '')
    resolved_document = (
        deps.resolve_local_supporting_document(document_reference, 'source')
        if document_reference else None)
    if (not resolved_document and document_reference
            and urlparse(document_reference).scheme in {'http', 'https'}
            and deps.viewable_supporting_document(document_reference)):
        resolved_document = document_reference
    metadata = {
        'expense_id': chosen['id'] if chosen else '',
        'receipt_url': '',
        'receipt_path': '',
        'notes': (chosen.get('notes') or '') if chosen else '',
        'address': (chosen.get('address') or '') if chosen else '',
        'map_link': (chosen.get('map_link') or '') if chosen else '',
        'machine_origin': deps.document_machine_origin(),
        # Ask Mazda must use the expense's database-backed source association.
        # The report directory is only a legacy fallback for old rows.
        'source_document_path': (
            resolved_document or deps.source_document_path(report_path)),
    }
    if chosen is None:
        return dict(metadata, ok=False,
                    error='No matching expense in DB for that date/amount (bank-only row).')
    ru = (chosen.get('receipt_url') or '').strip()
    if not ru:
        return dict(metadata, ok=False, error='No receipt on file for this expense.')
    fp = deps.resolve_expense_receipt_path(resolve_date, amt, ru)
    if not fp:
        return dict(metadata, ok=False,
                    error=f'Receipt recorded ({ru}) but the file was not found on disk.')
    metadata.update(
        ok=True,
        receipt_url=deps.receipt_url_for_path(fp),
        receipt_path=fp,
        source_document_path=(
            resolved_document or deps.source_document_path(report_path, fp)),
    )
    return metadata
