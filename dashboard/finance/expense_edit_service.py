"""Applying one Edit Expense correction (the body of POST /api/expense-edit).

``edit_stored_expense`` is the implementation behind
``server._edit_stored_expense``; the public command
(``server.edit_stored_expense``) wraps it with auditing. Mirrors
``finance.manual_receipt_intake.submit_manual_receipt_entry``'s boundary
discipline exactly -- coerce the untrusted JSON shape here, then let the
strict Pydantic model be the single place the three field rules are enforced.

``repository``/``namer``/``report_sync`` are already dependency-injected via
the function's own arguments (existing callers/tests pass fakes directly).
Everything else server.py still owns -- receipt-index invalidation, the
archived-image renamer, the vendor-prefix helper, and the static-report
synchronizer class -- is extensively monkeypatched by its `server.` name in
tests, so it arrives as a ``Collaborators`` bundle built fresh per call, same
reasoning as ``finance.recategorize.Collaborators``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from pydantic import ValidationError

from finance import vendor_lookup
from finance.expense_edit_model import ExpenseEdit, ExpenseNotFound
from finance.expense_edit_repository import readable_validation_error, records_as_json
from finance.http_coercion import as_float, as_int


@dataclass(frozen=True)
class Collaborators:
    """What stays behind in server.py, handed over per call."""

    get_expense_edit_repository: Callable
    taxonomy_category_namer: Callable
    invalidate_receipt_index: Callable
    synchronize_recent_report_image: Callable
    vendor_prefix: Callable
    static_expense_report_synchronizer: Callable
    rol_finances_reports_parent: str


def edit_stored_expense(deps: Collaborators, data, repository=None, namer=None,
                        report_sync=None):
    """Apply one correction; the public command wraps this with auditing."""
    data = data or {}
    repo = repository or deps.get_expense_edit_repository()
    resolver = namer or deps.taxonomy_category_namer()
    try:
        expense_id = as_int(data.get('expense_id'), 'expense_id')
        total_amount = as_float(data.get('total_amount'), 'total_amount')
        category_id = resolver.id_for(data.get('category_name'))
    except ValueError as exc:
        return {'ok': False, 'error': str(exc)}
    try:
        edit = ExpenseEdit(
            expense_id=expense_id,
            merchant_name=data.get('merchant_name', ''),
            transaction_date=data.get('transaction_date', ''),
            total_amount=total_amount,
            category_id=category_id,
        )
    except ValidationError as exc:
        return {'ok': False, 'error': readable_validation_error(exc)}
    learning_vendor_key = ''
    vendor_remembered = None
    if data.get('learn_vendor'):
        learning_vendor_key = str(data.get('vendor_key') or '').strip()
        if not learning_vendor_key or category_id is None:
            return {
                'ok': False,
                'error': 'A new vendor requires vendor_key and category.',
            }
        try:
            vendor_remembered = vendor_lookup.remember_vendor(
                edit.merchant_name, category_id,
                learning_vendor_key).model_dump()
        except Exception as exc:  # noqa: BLE001 - no DB write happened yet
            return {
                'ok': False,
                'error': f'Could not learn vendor: {type(exc).__name__}: {exc}',
            }
        if not vendor_remembered.get('remembered'):
            reason = vendor_remembered.get('reason') or 'the vendor rule was not persisted'
            returned_key = vendor_remembered.get('vendor_key')
            # remember() may return an existing stored key chosen from a broad
            # human entry. Accept that safe repeat only when a real key and
            # the precise "already known" result are both present.
            if not returned_key or reason != 'vendor_key already known':
                return {'ok': False, 'error': f'Could not learn vendor: {reason}'}
    before = None
    try:
        if hasattr(repo, 'read'):
            before = repo.read(expense_id)
        result = repo.apply_edit(edit)
    except ExpenseNotFound as exc:
        return {'ok': False, 'error': str(exc)}
    except Exception as exc:  # noqa: BLE001 - surfaced to the operator verbatim
        return {'ok': False, 'error': f'{type(exc).__name__}: {exc}'}
    # An edit can move a row's date/amount, which is what every report.html
    # row and the receipt index key off -- drop the cached index so "View
    # Receipt" re-resolves against the new values, same as a fresh save does.
    deps.invalidate_receipt_index()
    image_sync = deps.synchronize_recent_report_image(
        expense_id,
        vendor_key=str(data.get('vendor_key') or ''),
        transaction_date=edit.transaction_date,
        fallback_vendor_key=deps.vendor_prefix(result.record.id_light),
        fallback_date=result.record.transaction_date,
        replace_identity='expense_date' in result.changed_fields,
    )
    warnings = list(result.warnings)
    if before is not None:
        try:
            synchronizer = report_sync or deps.static_expense_report_synchronizer(
                deps.rol_finances_reports_parent)
            synchronizer.synchronize(before, result.record)
        except Exception as exc:  # the database edit already succeeded
            warnings.append(
                f'Expense saved, but static reports were not updated: '
                f'{type(exc).__name__}: {exc}')
    if image_sync.get('path'):
        warnings = [warning for warning in warnings
                    if 'receipt file on disk was not renamed' not in warning]
    if image_sync.get('warning'):
        warnings.append(image_sync['warning'])
    return {
        'ok': True,
        'record': records_as_json([result.record])[0],
        'changed_fields': list(result.changed_fields),
        'warnings': warnings,
        'vendor_remembered': vendor_remembered,
        'image': image_sync,
    }
