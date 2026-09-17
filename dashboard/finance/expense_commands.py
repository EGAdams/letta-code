"""The other three Verified-Transactions row commands: Search, Delete, Add 6%.

Siblings of ``finance.expense_edit_service.edit_stored_expense`` — same
boundary discipline, same reasoning for the ``Collaborators`` bundle (server.py
still owns the receipt-index cache, the archived-image renamer, and the
vendor-prefix helper, each extensively monkeypatched by its `server.` name in
tests).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from pydantic import ValidationError

from finance import sales_tax
from finance.expense_edit_model import ExpenseEdit, ExpenseNotFound
from finance.expense_edit_repository import (
    readable_validation_error,
    records_as_json,
    search_criteria_from_request,
)
from finance.http_coercion import as_int


@dataclass(frozen=True)
class Collaborators:
    """What stays behind in server.py, handed over per call."""

    get_expense_edit_repository: Callable
    invalidate_receipt_index: Callable
    synchronize_recent_report_image: Callable
    vendor_prefix: Callable


def search_stored_expenses(deps: Collaborators, data, repository=None):
    """POST /api/expense-search: rows behind the Edit Expense button.

    Read-only. A criteria error is the operator's to fix ("enter a merchant, a
    date range, or an amount"), so it comes back as a message rather than a
    500; a database failure does not, so it is reported as itself.
    """
    repo = repository or deps.get_expense_edit_repository()
    try:
        criteria = search_criteria_from_request(data)
    except (ValueError, ValidationError) as exc:
        return {'ok': False, 'error': readable_validation_error(exc)}
    try:
        records = repo.search(criteria)
    except Exception as exc:  # noqa: BLE001 - surfaced to the operator verbatim
        return {'ok': False, 'error': f'{type(exc).__name__}: {exc}'}
    return {'ok': True, 'records': records_as_json(records)}


def delete_stored_expense(deps: Collaborators, data, repository=None):
    """POST /api/expense-delete: remove one stored row.

    The Delete button on a Verified Transactions row. Deliberately narrower
    than edit_stored_expense: the only thing an operator can say here is
    *which* row, so the only thing to coerce is an id. Confirmation is the
    browser's job (a dialog naming the merchant), not this function's -- a
    request that reaches here has already been agreed to.
    """
    data = data or {}
    repo = repository or deps.get_expense_edit_repository()
    try:
        expense_id = as_int(data.get('expense_id'), 'expense_id')
    except ValueError as exc:
        return {'ok': False, 'error': str(exc)}
    if expense_id <= 0:
        return {'ok': False, 'error': 'expense_id must be a positive row id'}
    try:
        deletion = repo.delete(expense_id)
    except ExpenseNotFound as exc:
        return {'ok': False, 'error': str(exc)}
    except Exception as exc:  # noqa: BLE001 - surfaced to the operator verbatim
        return {'ok': False, 'error': f'{type(exc).__name__}: {exc}'}
    # The receipt index keys off (date, amount) per row; a removed row must
    # stop answering "View Receipt" for the file it used to claim.
    deps.invalidate_receipt_index()
    image_sync = deps.synchronize_recent_report_image(
        expense_id, deleted=True,
        fallback_vendor_key=deps.vendor_prefix(deletion.record.id_light),
        fallback_date=deletion.record.transaction_date,
    )
    response = {'ok': True,
        'record': records_as_json([deletion.record])[0],
        'line_item_ids': list(deletion.line_item_ids)}
    if image_sync.get('path') or image_sync.get('warning'):
        response['image'] = image_sync
    return response


def add_sales_tax_to_expense(deps: Collaborators, data, repository=None):
    """POST /api/expense-add-tax: put sales tax back on one stored row.

    The "Add 6%" button. The row is re-read here and the new amount computed
    here rather than sent up from the browser, for two reasons that are really
    the same reason: the rate is a fact about Michigan (finance/sales_tax.py
    owns it, so it cannot drift between the page and the reports), and the
    arithmetic is exact Decimal rather than a float multiply in a script tag.
    The write then goes through the ordinary edit path, so a taxed row picks up
    the same id_light linkage warning any other amount change earns.
    """
    data = data or {}
    repo = repository or deps.get_expense_edit_repository()
    try:
        expense_id = as_int(data.get('expense_id'), 'expense_id')
        # This endpoint is the concrete "Add 6%" command, not a general tax
        # calculator.  Ignore no caller-controlled rate because allowing one
        # would let the button's invariant be bypassed by a crafted request.
        rate = sales_tax.MICHIGAN_SALES_TAX_RATE
    except ValueError as exc:
        return {'ok': False, 'error': str(exc)}
    if expense_id <= 0:
        return {'ok': False, 'error': 'expense_id must be a positive row id'}
    try:
        before = repo.read(expense_id)
    except ExpenseNotFound as exc:
        return {'ok': False, 'error': str(exc)}
    except Exception as exc:  # noqa: BLE001 - surfaced to the operator verbatim
        return {'ok': False, 'error': f'{type(exc).__name__}: {exc}'}
    taxed = sales_tax.with_sales_tax(before.total_amount, rate)
    # Preserve the stored category id directly. Sending its display name back
    # through today's taxonomy can reject an otherwise valid historical row
    # after a category rename, even though this command changes only amount.
    try:
        result = repo.apply_edit(ExpenseEdit(
            expense_id=expense_id,
            merchant_name=before.description,
            transaction_date=before.transaction_date,
            total_amount=float(taxed),
            category_id=before.category_id,
        ))
    except (ExpenseNotFound, ValidationError) as exc:
        return {'ok': False, 'error': readable_validation_error(exc)}
    except Exception as exc:  # noqa: BLE001 - surfaced to the operator verbatim
        return {'ok': False, 'error': f'{type(exc).__name__}: {exc}'}
    deps.invalidate_receipt_index()
    image_sync = deps.synchronize_recent_report_image(
        expense_id,
        fallback_vendor_key=deps.vendor_prefix(result.record.id_light),
        fallback_date=result.record.transaction_date,
    )
    return {
        'ok': True,
        'record': records_as_json([result.record])[0],
        'changed_fields': list(result.changed_fields),
        'warnings': list(result.warnings),
        'tax_added': float(sales_tax.tax_on(before.total_amount, rate)),
        'rate': float(rate),
        'previous_amount': before.total_amount,
        'image': image_sync,
    }
