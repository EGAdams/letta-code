"""Recording one document-intake event (POST /api/expense-stored).

``record_stored_expense`` is Mazda's STEP 8 callback landing point: it shapes
the event, asks the Trainer-escalation policy whether this callback needs a
human, appends the event to the shared in-process log, and folds it into the
Recent Report view. ``stored_expense_lock``/``stored_expense_events`` are true
shared mutable state that has to keep living in server.py -- everything else
either has an owning module of its own or is monkeypatched by its `server.`
name in tests, so it all arrives as a ``Collaborators`` bundle built fresh per
call, same reasoning as ``intake.mazda_dispatch.Collaborators``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Collaborators:
    """What stays behind in server.py, handed over per call."""

    invalidate_receipt_index: Callable
    observe_intake_callback: Callable
    merge_recent_intake_event: Callable
    set_recent_report_pointer: Callable
    stored_expense_lock: object
    stored_expense_events: object


def record_stored_expense(deps: Collaborators, data):
    """Append one document-intake event.

    Also drops the receipt-index cache so a receipt stored by this same intake is
    visible to the NEXT /api/receipts-present / Receipt-Only fetch the frontend makes
    when it reloads — no waiting out the 300s TTL, no manual refresh.

    `kind` distinguishes what changed so the frontend can refresh the right views:
      receipt   — a receipt was stored (default; row marker + Receipt-Only tab)
      statement — a bank statement was imported (transaction rows changed)
      reprocess — a document was re-run end to end
    `report_path`, when present, names the specific report.html that changed so the
    frontend can target just that view instead of reloading every open iframe.
    """
    deps.invalidate_receipt_index()
    event = {
        'stored_at': time.time(),
        'kind': (data.get('kind') or 'receipt'),
        'expense_id': data.get('expense_id'),
        'expense_date': data.get('expense_date', ''),
        'amount': data.get('amount', ''),
        'vendor_key': data.get('vendor_key', ''),
        'description': data.get('description', ''),
        'receipt_url': data.get('receipt_url', ''),
        'report_path': data.get('report_path', ''),
        'document_path': data.get('document_path', ''),
        'expense_ids': data.get('expense_ids') or [],
        'duplicate_expense_ids': data.get('duplicate_expense_ids') or [],
        'deposits_stored': data.get('deposits_stored') or 0,
        'parsed': data.get('parsed'),
        'stored': data.get('stored'),
        'doc_kind': data.get('doc_kind') or data.get('doc_type') or '',
        'vendor': data.get('vendor') or data.get('merchant') or '',
        'archive_paths': data.get('archive_paths') or [],
        'archive_years': data.get('archive_years') or [],
        # Preserve exact dispatch identity.  Reusable scanner filenames are
        # insufficient routing keys when an older conversation reports late.
        'conversation_id': data.get('conversation_id', ''),
        'dispatched_at': data.get('dispatched_at'),
    }
    escalation = deps.observe_intake_callback(event)
    if escalation and escalation.summon_required:
        event['trainer_dispatched'] = escalation.summoned
        event['trainer_escalation_reason'] = escalation.reason
        event['status'] = 'processing' if escalation.summoned else 'fail'
        event['status_detail'] = (
            f'Trainer summoned: {escalation.reason}'
            if escalation.summoned
            else f'Trainer launch failed: {escalation.reason}'
        )
    with deps.stored_expense_lock:
        deps.stored_expense_events.append(event)
    # Keep /recent_report.html current. Best-effort: the callback must succeed
    # even if the recent-report bookkeeping can't.
    try:
        # Fold ids/counts into the last intake record so the synthetic recent
        # view can list this run's transactions.
        deps.merge_recent_intake_event(event)
        # Only move the recent-report pointer when the event itself names its
        # source report (a real reprocess of that report's document) — NOT
        # when a report is merely found via date/amount coincidence. A
        # coincidental match (e.g. a scanned receipt whose expense happens to
        # land on the same date/amount as some row in an unrelated bank
        # statement) must never hijack "most recent" away from the actual
        # intake, or /recent_report.html shows that statement's full
        # transaction table instead of the scan's own 1-row view.
        rp = event['report_path']
        if rp:
            deps.set_recent_report_pointer(rp)
    except Exception as exc:
        print(f'[expense-stored] recent-report update failed: {exc}')
    return {'ok': True}
