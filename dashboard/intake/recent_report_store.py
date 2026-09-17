"""The /recent_report.html pointer-file store.

The Reports tab lands on "Recent Report" — a live view of the Verified
Transactions from the most recently processed document. "Most recent" is the
newer of: an explicit pointer written when Mazda's STEP 8 /api/expense-stored
callback (or a Reprocess Document run) names/matches a report, and the newest
report.html mtime (Mazda rewriting a report on disk bumps it even when no
callback fires) — or, when nothing has a report.html yet (the typical case for
a scanned document), the last intake dispatch itself.

``pointer_file`` is rebound by an autouse conftest fixture on every test (so a
live recent_report.json is never touched) and by several tests directly, so it
arrives fresh per call via ``Collaborators`` rather than being read once at
import time. ``lock`` is the one real ``threading.Lock`` guarding the file,
shared with ``server._synchronize_recent_report_image`` -- it stays a single
object handed over by reference, never rebuilt, since a lock only works
against exactly one contended resource. ``merge_recent_intake_event`` routes
back through the server.py name (not this module's own function) so that
``merge_statement_review_result`` still honours
``monkeypatch.setattr(server, 'merge_recent_intake_event', ...)``.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Callable

from intake.recent_intake_contracts import RecentIntakeEventIdentity
from intake.statuses import TERMINAL_INTAKE_STATUSES


@dataclass(frozen=True)
class Collaborators:
    """What stays behind in server.py, handed over per call."""

    pointer_file: str
    lock: object
    report_file_for_url: Callable
    rol_finance_recent_reports: Callable
    current_execution_mode: Callable
    fold_event_into_intake: Callable
    recent_intake_event_router: object
    merge_recent_intake_event: Callable


def read_recent_pointer_file(deps: Collaborators):
    """Raw pointer-file contents ({} when missing/corrupt). The file holds BOTH
    the report pointer ({report_path, updated_at}) and the last intake dispatch
    ({intake: {...}}) — scanned documents usually have no report.html, so the
    intake record is what lets /recent_report.html reflect them at all."""
    try:
        with open(deps.pointer_file, encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def write_recent_pointer_file(deps: Collaborators, data):
    try:
        with open(deps.pointer_file, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        return True
    except OSError:
        return False


def set_recent_report_pointer(deps: Collaborators, report_path):
    """Persist <url path> of the report.html for the most recently processed
    document. No-op (False) when the path doesn't resolve to a real report."""
    if not deps.report_file_for_url(report_path):
        return False
    with deps.lock:
        data = read_recent_pointer_file(deps)
        data['report_path'] = report_path
        data['updated_at'] = time.time()
        return write_recent_pointer_file(deps, data)


def intake_state_token(deps: Collaborators):
    """Cheap change-token for the Recent Report dialog's poll loop: the
    pointer file's mtime, which record_recent_intake/merge_recent_intake_event
    bump on every write (dispatch, and later Mazda's STEP 8 report-back).
    A missing file (nothing scanned yet) gets a stable '0' token."""
    try:
        return str(os.path.getmtime(deps.pointer_file))
    except OSError:
        return '0'


def record_recent_intake(deps: Collaborators, image_path, label, kind='scan',
                         facade=None, conversation_id=None, dispatched_at=None,
                         content_sha256=None, status='processing',
                         status_detail=''):
    """Record an intake dispatch (scan or PDF) the moment Mazda is notified,
    so /recent_report.html can show the document even before — or without —
    any report.html existing for it. Called from process_scanned_document /
    process_pdf_document.

    `facade` is the deterministic classify+parse result (run_intake_facade),
    already computed at dispatch time for every doc — seeds doc_kind/vendor
    for the 'Document Type' field. It's frequently 'unknown' for scanned
    images (no extractable text), in which case merge_recent_intake_event
    overwrites it once Mazda reports her own vision classification back."""
    facade = facade or {}
    with deps.lock:
        data = read_recent_pointer_file(deps)
        intake = {
            'document': os.path.basename(image_path or ''),
            'image_path': image_path or '',
            'label': label or '',
            'kind': kind,
            'dispatched_at': float(dispatched_at or time.time()),
            'expense_ids': [],
            'duplicate_expense_ids': [],
            'parsed': None,
            'stored': None,
            'doc_kind': facade.get('doc_kind'),
            'vendor': facade.get('vendor'),
            'conversation_id': conversation_id,
            'content_sha256': content_sha256 or '',
            'archive_paths': [],
            'archive_years': [],
            # Usually 'processing' -- a dispatch that Mazda will report back
            # on. A capture rejected before dispatch (blank page, empty scanner
            # output) records its own terminal 'fail' here instead, so the
            # scanner's tab shows the failure rather than going on displaying
            # the previous document.
            'status': status,
            'status_detail': status_detail,
            'execution_mode': deps.current_execution_mode(),
        }
        data['intake'] = intake
        # Scans are ALSO recorded per-scanner (keyed by the scanner's human
        # name), so the Window Scanner / Freezer Scanner tabs keep showing each
        # scanner's own last document while both scanners run concurrently —
        # the shared 'intake' slot above only ever shows whichever dispatch
        # happened last.
        if kind == 'scan' and label:
            scanner_intakes = data.get('scanner_intakes')
            if not isinstance(scanner_intakes, dict):
                scanner_intakes = {}
            scanner_intakes[label] = dict(intake)
            data['scanner_intakes'] = scanner_intakes
        return write_recent_pointer_file(deps, data)


def merge_recent_intake_event(deps: Collaborators, event):
    """Fold a STEP 8 /api/expense-stored event into every intake record it
    belongs to — the shared 'last processed document' record and/or the
    per-scanner records — so the Recent Report and per-scanner views can list
    the actual transactions once Mazda reports them.

    Routing is fail-closed: a callback must carry a conversation id, dispatch
    timestamp, or document path. The injected router then selects only records
    proven to belong to that callback. An uncorrelated event remains available
    on the event bus but cannot mutate the latest scanner report."""
    with deps.lock:
        data = read_recent_pointer_file(deps)
        main = data.get('intake') if isinstance(data.get('intake'), dict) else None
        scanner_intakes = data.get('scanner_intakes')
        scanners = ([i for i in scanner_intakes.values() if isinstance(i, dict)]
                    if isinstance(scanner_intakes, dict) else [])
        candidates = ([main] if main else []) + scanners
        identity = RecentIntakeEventIdentity.from_mapping(event)
        if identity is None:
            return False
        targets = deps.recent_intake_event_router.select_targets(identity, candidates)
        if not targets:
            return False
        for intake in targets:
            deps.fold_event_into_intake(intake, event)
        return write_recent_pointer_file(deps, data)


def merge_statement_review_result(deps: Collaborators, payload):
    """Publish a successful review retry through the normal report event path.

    Calls ``deps.merge_recent_intake_event`` -- the server.py name -- rather
    than this module's own function, so a test's
    ``monkeypatch.setattr(server, 'merge_recent_intake_event', ...)`` is still
    honoured.
    """
    report = (payload or {}).get('report') or {}
    if not report.get('ok') or not report.get('source_file'):
        return False
    return deps.merge_recent_intake_event({
        'document_path': report.get('source_file'),
        'doc_kind': 'statement',
        'vendor': report.get('bank_name'),
        'parsed': report.get('transactions_parsed'),
        'stored': report.get('stored'),
        'expense_ids': report.get('expense_ids') or [],
        'duplicate_expense_ids': report.get('duplicate_expense_ids') or [],
        'status': 'complete',
    })


def merge_recent_intake_status(deps: Collaborators, update):
    """Apply a Trainer terminal status to the exact dispatched intake.

    Conversation id is the primary correlation key; document path plus dispatch
    timestamp is the compatibility fallback. Never update the merely-latest
    intake when no exact match exists, because Window and Freezer can overlap.
    """
    status = str(update.get('status') or '').strip().lower()
    if status not in TERMINAL_INTAKE_STATUSES:
        return False
    identity = RecentIntakeEventIdentity.from_mapping(update)
    if identity is None:
        return False
    conversation_id = identity.conversation_id
    document_path = identity.document_path
    dispatched_at = identity.dispatched_at or 0.0
    with deps.lock:
        data = read_recent_pointer_file(deps)
        main = data.get('intake') if isinstance(data.get('intake'), dict) else None
        scanner_intakes = data.get('scanner_intakes')
        scanners = ([i for i in scanner_intakes.values() if isinstance(i, dict)]
                    if isinstance(scanner_intakes, dict) else [])
        candidates = ([main] if main else []) + scanners
        targets = []
        for intake in candidates:
            if conversation_id and intake.get('conversation_id') == conversation_id:
                targets.append(intake)
                continue
            same_path = document_path and intake.get('image_path') == document_path
            try:
                same_dispatch = (dispatched_at and
                                 abs(float(intake.get('dispatched_at') or 0) -
                                     dispatched_at) < 2.0)
            except (TypeError, ValueError):
                same_dispatch = False
            if same_path and same_dispatch:
                targets.append(intake)
        if not targets:
            return False
        for intake in targets:
            integrity_error = str(
                intake.get('integrity_error') or '').strip()
            if status in {'pass', 'corrected'} and integrity_error:
                intake['status'] = 'fail'
                intake['status_detail'] = integrity_error
            else:
                intake['status'] = status
                intake['status_detail'] = str(
                    update.get('detail') or '').strip()
            intake['status_source'] = str(
                update.get('status_source') or 'trainer').strip()
            intake['trainer_report'] = str(update.get('report_path') or '').strip()
            intake['reported_at'] = time.time()
        return write_recent_pointer_file(deps, data)


def record_intake_status(deps: Collaborators, data):
    """Dashboard endpoint used by the Trainer runner after writing its report."""
    merged = merge_recent_intake_status(deps, data or {})
    return {'ok': merged, 'status': (data or {}).get('status', '')}


def load_recent_report_pointer(deps: Collaborators):
    data = read_recent_pointer_file(deps)
    rp = data.get('report_path')
    if not rp or not deps.report_file_for_url(rp):
        return None
    try:
        updated_at = float(data.get('updated_at') or 0)
    except (TypeError, ValueError):
        updated_at = 0.0
    return {'report_path': rp, 'updated_at': updated_at}


def resolve_recent_report(deps: Collaborators):
    """The most recently processed document, as one of:
      {'mode': 'report', 'url', 'file'}   — a report.html to mirror, or
      {'mode': 'intake', 'intake': {...}} — a dispatch with no report.html
                                            (typical for scanned documents).
    Picks the newest among the explicit report pointer, the newest report.html
    mtime, and the last intake dispatch. Returns None when nothing exists."""
    candidates = []
    pointer = load_recent_report_pointer(deps)
    if pointer:
        candidates.append((pointer['updated_at'], 'report', pointer['report_path']))
    latest = deps.rol_finance_recent_reports(limit=1).get('latest')
    if latest:
        candidates.append((latest['mtime'], 'report', latest['url']))
    intake = read_recent_pointer_file(deps).get('intake')
    if isinstance(intake, dict) and intake.get('dispatched_at'):
        candidates.append((float(intake['dispatched_at']), 'intake', intake))
    for _ts, mode, payload in sorted(candidates, key=lambda c: c[0], reverse=True):
        if mode == 'intake':
            return {'mode': 'intake', 'intake': payload}
        fp = deps.report_file_for_url(payload)
        if fp:
            return {'mode': 'report', 'url': payload, 'file': fp}
    return None
