"""Folding one STEP 8 /api/expense-stored event into an intake record.

``fold_event_into_intake`` is the merge rule behind
``server.merge_recent_intake_event``: given one callback event, it decides
which expense ids the Recent Report table should show, whether a duplicate
callback's ids are trustworthy, and whether the intake's status may advance.
``duplicate_callback_integrity_error`` (the validation) and
``resolve_duplicate_expense_ids`` (the last-resort id recovery) exist only to
serve this one function and travel with it -- nothing else in the codebase
calls them.

``get_connection`` stays behind in server.py (the live MySQL connection
factory, shared and reused far beyond this module). ``duplicate_event_rows``
and ``resolve_duplicate_expense_ids`` also route back through server.py --
even though their real implementation lives here -- because
``tests/test_server.py`` and ``tests/test_recent_intake_event_routing.py``
monkeypatch them by their `server.` name to fake a duplicate row without a
database; routing internal calls through the deps bundle rather than calling
this module's own functions directly is what keeps that patch reachable. Same
reasoning as ``intake.mazda_dispatch.Collaborators``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Collaborators:
    """What stays behind in server.py, handed over per call."""

    get_connection: Callable
    duplicate_event_rows: Callable
    resolve_duplicate_expense_ids: Callable


def duplicate_event_rows(deps: Collaborators, ids):
    """Raw date/amount identity for duplicate callback validation.

    This is the real implementation server.py's `_duplicate_event_rows`
    thin wrapper delegates to. `duplicate_callback_integrity_error` below
    calls `deps.duplicate_event_rows` -- the server.py name -- rather than
    this function directly, so a test's `monkeypatch.setattr(server,
    '_duplicate_event_rows', ...)` is still honoured.
    """
    clean = []
    for value in ids or []:
        try:
            value = int(value)
        except (TypeError, ValueError):
            continue
        if value not in clean:
            clean.append(value)
    if not clean:
        return []
    placeholders = ','.join(['%s'] * len(clean))
    with deps.get_connection() as cnx:
        with cnx.cursor() as cur:
            cur.execute(
                "SELECT id, expense_date, amount FROM expenses "
                f"WHERE id IN ({placeholders})",
                tuple(clean),
            )
            return list(cur.fetchall())


def duplicate_callback_integrity_error(deps: Collaborators, event):
    """Reject a duplicate ID whose stored date/amount is not this receipt."""
    duplicate_ids = event.get('duplicate_expense_ids') or []
    try:
        duplicate_only = int(event.get('stored')) == 0 and bool(duplicate_ids)
    except (TypeError, ValueError):
        duplicate_only = False
    date_s = str(event.get('expense_date') or '').strip()
    amount_s = str(event.get('amount') or '').strip()
    if not duplicate_only or not date_s or not amount_s:
        return ''
    try:
        expected_amount = abs(float(
            amount_s.replace(',', '').replace('$', '')))
        clean_ids = [int(value) for value in duplicate_ids]
        rows = deps.duplicate_event_rows(clean_ids)
    except Exception as exc:
        print(f'[expense-stored] duplicate callback validation skipped: {exc}')
        return ''
    by_id = {int(row['id']): row for row in rows}
    for expense_id in clean_ids:
        row = by_id.get(expense_id)
        if row is None:
            return f'Duplicate callback named missing expense {expense_id}.'
        try:
            stored_amount = abs(float(row.get('amount')))
        except (TypeError, ValueError):
            return f'Duplicate expense {expense_id} has an unreadable amount.'
        stored_date = str(row.get('expense_date') or '').strip()
        if stored_date != date_s or abs(stored_amount - expected_amount) >= 0.005:
            return (
                f'Duplicate callback mismatch: current parse is {date_s} '
                f'${expected_amount:.2f}, but expense {expense_id} is '
                f'{stored_date or "unknown date"} ${stored_amount:.2f}.'
            )
    return ''


def resolve_duplicate_expense_ids(deps: Collaborators, expense_date, amount, limit=3):
    """Ids of already-stored expenses matching (expense_date, |amount|).

    Used only as the last-resort recovery in fold_event_into_intake when a
    duplicate-only callback named no ids at all. Deliberately narrow:

    - (date, amount) is the same join this codebase already trusts for
      receipt<->row linkage (see server._resolve_expense_receipt_path), and it
      is the only identifying pair a duplicate callback reliably carries --
      vendor_key is NOT usable here, because check_duplicates reports the
      stored row's id_light (e.g. consumers_energy_01_23_25_222_65) while
      STEP 8 reports the normalized vendor key (consumers_7996); requiring
      them to agree would reject every real match.
    - More than `limit` hits means the pair is ambiguous (a common round amount
      on a busy day), so return nothing rather than showing rows that may
      belong to an unrelated document. Guessing wrong here is worse than the
      empty table this is trying to fix.

    Best-effort: any DB problem yields [] and the caller renders as before.
    """
    date_s = str(expense_date or '').strip()
    amount_s = str(amount or '').strip()
    if not date_s or not amount_s:
        return []
    try:
        amount_f = abs(float(amount_s.replace(',', '').replace('$', '')))
    except ValueError:
        return []
    try:
        with deps.get_connection() as cnx:
            with cnx.cursor() as cur:
                cur.execute(
                    'SELECT id FROM expenses '
                    'WHERE expense_date = %s AND ABS(ABS(amount) - %s) < 0.005 '
                    'ORDER BY id LIMIT %s',
                    (date_s, amount_f, limit + 1),
                )
                rows = cur.fetchall()
    except Exception as exc:
        print(f'[expense-stored] duplicate id recovery failed: {exc}')
        return []
    ids = [int(r['id']) for r in rows]
    return [] if len(ids) > limit else ids


def fold_event_into_intake(deps: Collaborators, intake, event):
    """Fold one STEP 8 event's fields (expense ids + parsed/stored counts +
    doc_kind/vendor) into one intake record, in place."""
    integrity_error = duplicate_callback_integrity_error(deps, event)
    if integrity_error:
        # Never let a coincidental/old DB row become this scan's displayed
        # receipt. Preserve the current source document and surface the failed
        # correlation for the Trainer instead.
        event = dict(event)
        event['expense_id'] = None
        event['expense_ids'] = []
        event['duplicate_expense_ids'] = []
        intake['expense_ids'] = []
        intake['duplicate_expense_ids'] = []
        intake['integrity_error'] = integrity_error
        intake['status'] = 'fail'
        intake['status_detail'] = integrity_error
    ids = list(intake.get('expense_ids') or [])
    duplicate_ids = list(intake.get('duplicate_expense_ids') or [])
    # A corrected duplicate-only callback supersedes any earlier bad store
    # from the same isolated run. Keep only the canonical existing rows named
    # by the final callback instead of permanently unioning a deleted/bad ID
    # into the scanner view.
    try:
        duplicate_only = (int(event.get('stored')) == 0 and
                          bool(event.get('duplicate_expense_ids')))
    except (TypeError, ValueError):
        duplicate_only = False
    if duplicate_only:
        ids = []
        duplicate_ids = []
    # Duplicates matter as much as newly-stored rows here: a re-scan that
    # stores nothing still shows its transactions so they can be
    # recategorized before the next scan.
    for eid in (list(event.get('expense_ids') or [])
                + list(event.get('duplicate_expense_ids') or [])
                + list(event.get('scanned_statement_attached') or [])
                + [event.get('expense_id')]):
        try:
            eid = int(eid)
        except (TypeError, ValueError):
            continue
        if eid not in ids:
            ids.append(eid)
    intake['expense_ids'] = ids
    for eid in event.get('duplicate_expense_ids') or []:
        try:
            eid = int(eid)
        except (TypeError, ValueError):
            continue
        if eid not in duplicate_ids:
            duplicate_ids.append(eid)
    intake['duplicate_expense_ids'] = duplicate_ids
    for k in ('parsed', 'stored', 'rolled_back_row_count'):
        if event.get(k) is not None:
            try:
                intake[k] = int(event[k])
            except (TypeError, ValueError):
                pass
    # Safety net for a duplicate run that named no ids. The receipt/invoice
    # branch of Mazda's STEP 8 has more than once posted
    # duplicate_expense_ids:[] even though check_duplicates knew the existing
    # row's id, which left the Recent Report page with nothing to render — the
    # user sees "already in the database" and no Verified Transactions table at
    # all. The event still carries the date/amount it matched on, so resolve
    # the pre-existing row here rather than depending on the agent's payload.
    if (not ids and not duplicate_ids
            and intake.get('stored') == 0 and (intake.get('parsed') or 0) > 0):
        recovered = deps.resolve_duplicate_expense_ids(
            event.get('expense_date'), event.get('amount'))
        if recovered:
            intake['expense_ids'] = list(recovered)
            intake['duplicate_expense_ids'] = list(recovered)
    # doc_kind/vendor: Mazda's own classification (STEP 8 payload) beats the
    # facade's dispatch-time guess (often 'unknown' for scanned images) --
    # accept either her doc_kind (statement/receipt/unknown, matching the
    # facade's vocabulary) or classify_scan.py's doc_type/merchant naming.
    doc_kind = event.get('doc_kind') or event.get('doc_type')
    if doc_kind and doc_kind != 'unknown':
        intake['doc_kind'] = doc_kind
    vendor = event.get('vendor') or event.get('merchant')
    if vendor and vendor != 'unknown':
        intake['vendor'] = vendor
    if event.get('archive_paths') is not None:
        intake['archive_paths'] = [
            str(path).strip() for path in (event.get('archive_paths') or [])
            if str(path).strip()
        ]
    if event.get('archive_years') is not None:
        cleaned_years = []
        for year in event.get('archive_years') or []:
            try:
                cleaned_years.append(int(year))
            except (TypeError, ValueError):
                continue
        intake['archive_years'] = cleaned_years
    intake['reported_at'] = time.time()
    event_status = str(event.get('status') or '').strip().lower()
    # STEP 8 and Trainer updates can race. A late expense-stored callback has
    # no status of its own and must not downgrade an already-terminal Trainer
    # PASS/FAIL back to "complete", which would re-lock the scanner after a
    # service restart.
    if event_status:
        intake['status'] = event_status
    elif intake.get('status_source') == 'transport':
        # A synchronous Letta POST can time out after the isolated
        # conversation accepted the message. Its later STEP 8 callback is
        # authoritative proof of delivery; clear only that provisional
        # transport failure, never a Trainer verdict.
        intake['status'] = 'complete'
        intake['status_detail'] = ''
        intake['status_source'] = 'callback'
    elif str(intake.get('status') or '').lower() not in {
            'pass', 'corrected', 'fail', 'stalled'}:
        intake['status'] = 'complete'
    if event.get('status_detail'):
        intake['status_detail'] = str(event['status_detail'])
    if event.get('trainer_dispatched') is not None:
        intake['trainer_dispatched'] = bool(event['trainer_dispatched'])
    if event.get('trainer_escalation_reason'):
        intake['trainer_escalation_reason'] = str(
            event['trainer_escalation_reason'])
