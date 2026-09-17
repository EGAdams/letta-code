"""POST /api/manual-receipt-entry: the needs_human_review form's Save button.

``submit_manual_receipt_entry`` stores the human-entered fields through
``finance.manual_entry`` (the exact tool Mazda's own pipeline uses, just with
--engine local instead of her LLM turn), then folds a STEP-8-shaped event into
the intake record -- same as Mazda's own /api/expense-stored callback -- so
expense_ids populate (the Verified Transactions table and the
archive-verification terminal both key off that), and status flips from
needs_human_review to complete. A failure leaves the intake queued so the form
reappears, same as the statement review dialog's "pops up again" contract.

Named ``manual_receipt_intake`` rather than ``manual_receipt_entry`` to keep
it distinct from ``finance.manual_entry``, the lower-level module it calls
into -- this one is the HTTP-shaped orchestration, that one is the record/save
primitive shared with Mazda's own pipeline.
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
    invalidate_receipt_index: Callable
    merge_recent_intake_event: Callable
    get_expense_edit_repository: Callable
    synchronize_recent_report_image: Callable
    vendor_prefix: Callable


def submit_manual_receipt_entry(deps: Collaborators, data):
    data = data or {}
    # HTTP JSON is untrusted shape, not just untrusted value: coerce here, at
    # the boundary, before the strict Pydantic model -- ManualReceiptEntry's
    # strict=True deliberately rejects a numeric field arriving as a string
    # rather than silently coercing it.
    try:
        total_amount = as_float(data.get('total_amount'), 'total_amount')
    except ValueError as exc:
        return {'ok': False, 'error': str(exc)}
    category_name = str(data.get('category_name') or '').strip()
    category_id = None
    if category_name:
        category_id, category_cls = deps.resolve_reporting_category(category_name)
        if category_cls is None:
            return {'ok': False, 'error': f'Unknown category: {category_name!r}'}
    try:
        org_id = as_int(data.get('org_id') or 1, 'org_id')
    except ValueError as exc:
        return {'ok': False, 'error': str(exc)}
    try:
        entry = manual_entry.ManualReceiptEntry(
            image_path=data.get('image_path', ''),
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

    ok, payload = manual_entry.submit_manual_receipt_entry(entry)
    if not ok:
        return {'ok': False, **payload}

    # A successful --save just moved a receipt file into readable_documents/
    # out-of-process (the parse_and_categorize.py subprocess), invisible to
    # this process's in-memory index until the 300s TTL expires. Without this,
    # the archive-verification terminal and the View Receipt button that fire
    # immediately after this call see a stale index and report no receipt at
    # all -- same as record_stored_expense (Mazda's callback) and
    # reprocess_report already do for their own out-of-process receipt writes.
    deps.invalidate_receipt_index()
    report = payload.get('report') or {}
    expense_id = report.get('expense_id')
    duplicate = bool(report.get('duplicate'))
    conversation_id = str(data.get('conversation_id') or '').strip()
    deps.merge_recent_intake_event({
        'conversation_id': conversation_id,
        'document_path': entry.image_path,
        'expense_ids': [] if expense_id is None else [expense_id],
        'duplicate_expense_ids': [expense_id] if duplicate and expense_id is not None else [],
        'parsed': 1,
        'stored': 0 if duplicate else 1,
        'doc_kind': 'receipt',
        'vendor': entry.merchant_name,
        'status': 'complete',
        'status_detail': (f'Entered manually by operator — expense_id={expense_id}'
                          if not duplicate
                          else f'Matched an existing expense (id={expense_id}); not double-entered.'),
    })
    record = {
        'id': int(expense_id),
        'transaction_date': entry.transaction_date,
        'total_amount': entry.total_amount,
        'description': entry.merchant_name,
        'id_light': '',
        'category_id': category_id,
        'category_name': category_name,
    } if expense_id is not None else None
    image_sync = {'renamed': False}
    if expense_id is not None:
        try:
            stored = deps.get_expense_edit_repository().read(int(expense_id))
            record = records_as_json([stored])[0]
        except Exception:  # noqa: BLE001 - retain the validated saved values
            pass
        image_sync = deps.synchronize_recent_report_image(
            int(expense_id),
            vendor_key=entry.vendor_key,
            transaction_date=entry.transaction_date,
            fallback_vendor_key=deps.vendor_prefix(
                str((record or {}).get('id_light') or '')),
            fallback_date=entry.transaction_date,
        )
    return {
        'ok': True,
        'expense_id': expense_id,
        'duplicate': duplicate,
        'vendor_remembered': report.get('vendor_remembered'),
        'record': record,
        'image': image_sync,
    }
