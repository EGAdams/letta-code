"""POST /api/add-expense-entry: the Add Expense page's Save button.

``submit_manual_expense_entry`` stores the human-entered fields through
``finance.manual_entry`` (the exact tool the Add Expense page shares with the
Recent Report dialog's Save All, just with no image_path/File As/Will Be
Filed As at all -- see finance/manual_entry.py's ManualExpenseEntry and
rol_finances' manual_expense_entry.py), then reads the saved row back the
same way manual_receipt_intake.py does so the response carries a `record`
the Verified Transactions table can append immediately, with the correct
category color.

Named to mirror ``manual_receipt_intake`` (the HTTP-shaped orchestration)
against ``finance.manual_entry`` (the record/save primitive both share). This
one skips everything specific to a scanned/PDF document: no
merge_recent_intake_event (there is no intake this expense belongs to), no
receipt-index invalidation, no image sync.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from pydantic import ValidationError

from finance import manual_entry
from finance.expense_edit_repository import records_as_json
from finance.http_coercion import as_float, as_int


@dataclass(frozen=True)
class Collaborators:
    """What stays behind in server.py, handed over per call."""

    resolve_reporting_category: Callable
    get_expense_edit_repository: Callable


def submit_manual_expense_entry(deps: Collaborators, data):
    data = data or {}
    try:
        total_amount = as_float(data.get('total_amount'), 'total_amount')
    except ValueError as exc:
        return {'ok': False, 'error': str(exc)}
    category_name = str(data.get('category_name') or '').strip()
    category_id = None
    # Matches css_class_for_report_name's own fallback: an unresolved/blank
    # category renders exactly as an explicit "Uncategorized" pick.
    category_cls = 'cat-uncategorized'
    if category_name:
        category_id, category_cls = deps.resolve_reporting_category(category_name)
        if category_cls is None:
            return {'ok': False, 'error': f'Unknown category: {category_name!r}'}
    try:
        org_id = as_int(data.get('org_id') or 1, 'org_id')
    except ValueError as exc:
        return {'ok': False, 'error': str(exc)}
    try:
        entry = manual_entry.ManualExpenseEntry(
            merchant_name=data.get('merchant_name', ''),
            transaction_date=data.get('transaction_date', ''),
            total_amount=total_amount,
            category_id=category_id,
            org_id=org_id,
            vendor_key=str(data.get('vendor_key') or '').strip(),
            learn_vendor=bool(data.get('learn_vendor')),
        )
    except ValidationError as exc:
        return {'ok': False, 'error': str(exc)}

    ok, payload = manual_entry.submit_manual_expense_entry(entry)
    if not ok:
        return {'ok': False, **payload}
    report = payload.get('report') or {}
    expense_id = report.get('expense_id')
    duplicate = bool(report.get('duplicate'))
    record = None
    if expense_id is not None:
        try:
            stored = deps.get_expense_edit_repository().read(int(expense_id))
            record = records_as_json([stored])[0]
        except Exception:  # noqa: BLE001 - retain the validated saved values
            pass
        if record is not None:
            # ExpenseRecord/records_as_json carry no notion of CSS -- that is
            # a browser-only concern -- so the class this same save already
            # resolved above is merged onto the plain dict here rather than
            # widening the shared record shape for one field. See
            # verified-transaction-rows.js's addExpense, which colors the row
            # this record backs the moment Save All appends it live.
            record['category_class'] = category_cls
    return {
        'ok': True,
        'expense_id': expense_id,
        'duplicate': duplicate,
        'vendor_remembered': report.get('vendor_remembered'),
        'record': record,
    }
