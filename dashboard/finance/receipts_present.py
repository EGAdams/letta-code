"""The red 'has a receipt' / scanned-statement corner markers.

Both functions take the same shape of rows and answer the same shape of
question -- "does a persisted document back this row" -- against two
different evidence slots (a receipt file vs. a scanned-statement photo). One
FS index + one DB read total per call.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable


@dataclass(frozen=True)
class Collaborators:
    """What stays behind in server.py, handed over per call."""

    get_connection: Callable
    norm_amount: Callable
    select_matching_expense: Callable
    resolve_expense_receipt_path: Callable
    resolve_local_supporting_document: Callable


def receipts_present(deps: Collaborators, rows):
    """Given [{date, signed_amount, vendor_key, description}, ...] return
    {'ok': True, 'present': [bool, ...]} -- True where a receipt file resolves for the
    row. Drives the red 'has a receipt' corner marker."""
    expense_map = {}
    try:
        with deps.get_connection() as cnx:
            with cnx.cursor() as cur:
                cur.execute(
                    "SELECT id, expense_date, amount, id_light, description, receipt_url "
                    "FROM expenses"
                )
                for r in cur.fetchall():
                    key = (str(r['expense_date']), str(r['amount']))
                    expense_map.setdefault(key, []).append(r)
    except Exception:
        expense_map = {}
    out = []
    for row in rows or []:
        amt = deps.norm_amount(row.get('signed_amount'))
        date_str = (row.get('date') or '').strip()
        present = False
        if amt is not None:
            vk = row.get('vendor_key', '')
            desc = row.get('description', '')
            chosen = deps.select_matching_expense(
                expense_map.get((date_str, amt), []), vk, desc)
            resolve_date = date_str
            # Credit-card posting dates are often 1-3 days after the purchase date
            # stored in the DB (from the actual receipt). Try nearby dates when exact
            # lookup finds nothing.
            if chosen is None and date_str:
                try:
                    base = datetime.strptime(date_str, '%Y-%m-%d').date()
                    for delta in (-1, 1, -2, 2, -3, 3):
                        alt = (base + timedelta(days=delta)).isoformat()
                        candidates = expense_map.get((alt, amt), [])
                        if candidates:
                            c = deps.select_matching_expense(candidates, vk, desc)
                            if c:
                                chosen = c
                                resolve_date = alt
                                break
                except (ValueError, AttributeError):
                    pass
            ru = (chosen.get('receipt_url') or '').strip() if chosen else ''
            present = bool(deps.resolve_expense_receipt_path(resolve_date, amt, ru))
        out.append(present)
    return {'ok': True, 'present': out}


def scanned_statements_present(deps: Collaborators, rows):
    """Same shape/contract as receipts_present, for the SCANNED_STATEMENT slot.

    Drives a row marker distinct from the receipt corner: a row backed by a
    scan of a printed statement EG has physically reviewed, independent of
    whether it also has a receipt or the bank's own downloaded source."""
    expense_map = {}
    try:
        with deps.get_connection() as cnx:
            with cnx.cursor() as cur:
                cur.execute(
                    "SELECT id, expense_date, amount, id_light, description, "
                    "scanned_statement_url FROM expenses"
                )
                for r in cur.fetchall():
                    key = (str(r['expense_date']), str(r['amount']))
                    expense_map.setdefault(key, []).append(r)
    except Exception:
        expense_map = {}
    out = []
    for row in rows or []:
        amt = deps.norm_amount(row.get('signed_amount'))
        date_str = (row.get('date') or '').strip()
        present = False
        if amt is not None:
            vk = row.get('vendor_key', '')
            desc = row.get('description', '')
            chosen = deps.select_matching_expense(
                expense_map.get((date_str, amt), []), vk, desc)
            ref = (chosen.get('scanned_statement_url') or '').strip() if chosen else ''
            present = bool(
                ref and deps.resolve_local_supporting_document(ref, 'scanned_statement'))
        out.append(present)
    return {'ok': True, 'present': out}
