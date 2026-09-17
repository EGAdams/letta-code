"""Resolving which archived document(s) back a set of transaction rows.

Four evidence slots exist for one intake: the source PDF/xlsx a report row
traces back to, a receipt file, a scanned-statement photo, and a Mom's Ledger
reference. This module answers "given these rows (or this intake), which
files back them" for the Recent Report / scanner-report synthetic views and
for scanner archive verification.

Several of these functions are individually monkeypatched by their `server.`
name in tests to drive the others through their branches without a real
filesystem/DB -- so internal cross-calls route through ``deps`` (the
server.py names) rather than this module's own functions, same reasoning as
``intake.mazda_dispatch.Collaborators``.
"""

from __future__ import annotations

import glob
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

STATEMENT_INTAKE_DOC_KINDS = {'statement', 'bank_statement', 'credit_card_statement'}


@dataclass(frozen=True)
class Collaborators:
    """What stays behind in server.py, handed over per call."""

    find_matching_report_row: Callable
    source_document_path: Callable
    resolve_local_supporting_document: Callable
    resolve_expense_receipt_path: Callable
    report_file_for_url: Callable
    readable_docs_base: str
    associated_source_paths: Callable
    associated_evidence_paths: Callable
    statement_archive_path: Callable
    recent_intake_archive_path: Callable


def rows_are_statement_rows(rows):
    """Do these transactions come off a scanned statement page?

    scanned_statement_url is set for statement rows and for nothing else, so it
    identifies the document even when the intake record forgot to.
    """
    return any((r.get('scanned_statement_url') or '').strip() for r in rows or [])


def associated_source_paths(deps: Collaborators, rows):
    """Resolve the source PDF and receipt file backing a set of transactions
    (the rows shown on the synthetic Recent Report intake view).

    Reuses the same (date, amount) matching primitives the Set Category
    dialog's View Receipt button and recategorize's report-row search already
    use, rather than re-deriving document/transaction linkage from scratch:
      - find_matching_report_row + source_document_path locate the PDF/xlsx
        an existing report.html's row for the same (date, amount) traces back
        to — i.e. this transaction was originally imported from there.
      - resolve_expense_receipt_path locates a receipt file on disk for a
        row that has a non-empty receipt_url.
    Returns (pdf_path or '', receipt_path or ''), stopping at the first row
    that yields each (rows of one intake are assumed to share one source doc).
    """
    pdf_path, receipt_path = '', ''
    for r in rows or []:
        if not pdf_path:
            match = deps.find_matching_report_row(
                r.get('date'), r.get('amount'), r.get('vendor_key'))
            if match:
                pdf_path = deps.source_document_path(match.report_path) or ''
            if not pdf_path:
                # No report.html traces back to this row, but the expense may
                # still carry its own document_url (e.g. a bank-downloaded
                # statement/xlsx attached directly, never via a report row).
                du = (r.get('document_url') or '').strip()
                if du:
                    pdf_path = deps.resolve_local_supporting_document(du, 'source') or ''
        if not receipt_path:
            ru = (r.get('receipt_url') or '').strip()
            if ru:
                receipt_path = deps.resolve_expense_receipt_path(
                    r.get('date'), r.get('amount'), ru) or ''
        if pdf_path and receipt_path:
            break
    return pdf_path, receipt_path


def associated_evidence_paths(deps: Collaborators, rows):
    """Resolve the remaining two supporting-document evidence slots
    (`scanned_statement_url`, `moms_ledger`) backing a set of transactions —
    the counterparts to `associated_source_paths`'s PDF/receipt.

    Scanner intakes routinely populate `scanned_statement_url` (the archived
    photo of the printed statement) without ever touching `document_url` or
    `receipt_url`, so these are surfaced separately rather than folded into
    associated_source_paths's two slots. See the 4-evidence-slot model.
    Returns (scanned_statement_path or '', moms_ledger_path or ''), stopping at
    the first row that yields each.
    """
    scanned_statement_path, moms_ledger_path = '', ''
    for r in rows or []:
        if not scanned_statement_path:
            ref = (r.get('scanned_statement_url') or '').strip()
            if ref:
                scanned_statement_path = (
                    deps.resolve_local_supporting_document(ref, 'scanned_statement')
                    or ref)
        if not moms_ledger_path:
            ref = (r.get('moms_ledger') or '').strip()
            if ref:
                moms_ledger_path = (
                    deps.resolve_local_supporting_document(ref, 'moms_ledger') or ref)
        if scanned_statement_path and moms_ledger_path:
            break
    return scanned_statement_path, moms_ledger_path


def statement_archive_path(deps: Collaborators, rows, vendor_key=''):
    """Locate the canonically-named bank_statements archive copy of a scanned
    statement — readable_documents/bank_statements/<year>/<month>/
    <vendor>_<slug>/<vendor>_<slug>.<ext>, where slug is built from the
    statement's own date range (e.g. 'july_31__august_15').

    Scanner intakes only ever populate scanned_statement_url with the raw
    scan filename (e.g. window_scan_...jpg) — the properly-named copy filed
    under bank_statements/ isn't linked from the DB anywhere, so it has to be
    found by matching this slug against every year/month folder rather than
    looked up directly. Vendor tokens disambiguate when more than one folder
    shares a date range; an unresolved ambiguity returns '' rather than
    guessing (same fail-closed shape as find_matching_report_row).
    """
    dates = sorted({r.get('date') for r in rows or [] if r.get('date')})
    if not dates:
        return ''
    try:
        start = datetime.strptime(dates[0], '%Y-%m-%d')
        end = datetime.strptime(dates[-1], '%Y-%m-%d')
    except ValueError:
        return ''
    slug = (f'{start.strftime("%B").lower()}_{start.day:02d}__'
            f'{end.strftime("%B").lower()}_{end.day:02d}')
    pattern = os.path.join(
        deps.readable_docs_base, 'bank_statements', str(start.year), '*', f'*{slug}')
    folders = sorted(glob.glob(pattern))
    if len(folders) > 1 and vendor_key:
        tokens = [t for t in vendor_key.lower().split('_') if t.isalpha()]
        narrowed = [f for f in folders
                    if any(t in os.path.basename(f).lower() for t in tokens)]
        if narrowed:
            folders = narrowed
    if len(folders) != 1:
        return ''
    folder = folders[0]
    name = os.path.basename(folder)
    for ext in ('.jpg', '.jpeg', '.png', '.pdf', '.xlsx'):
        candidate = os.path.join(folder, name + ext)
        if os.path.isfile(candidate):
            return candidate
    return ''


def recent_intake_archive_path(deps: Collaborators, intake, rows, receipt_path=''):
    """Return this intake's durable filed scan, never its staging name."""
    archive_paths = [
        str(path).strip() for path in (intake.get('archive_paths') or [])
        if str(path).strip()
    ]
    if archive_paths:
        return archive_paths[0]
    # A receipt scan can arrive with doc_kind=unknown because the scanner
    # facade dispatches before Mazda's classifier reports back. The rows' own
    # receipt path is still authoritative and must win before the statement
    # fallback below; otherwise archive verification reports "Archive path not
    # found" even though the receipt file is present on disk.
    if receipt_path and os.path.isfile(receipt_path):
        return str(receipt_path).strip()
    doc_kind = str(intake.get('doc_kind') or '').strip().lower()
    if doc_kind in {'receipt', 'invoice'}:
        return str(receipt_path or '').strip()
    if doc_kind in STATEMENT_INTAKE_DOC_KINDS or rows_are_statement_rows(rows):
        # doc_kind is frequently absent: a scan dispatched with no facade, or
        # one whose only outcome was duplicates, never records one. The rows
        # themselves settle it -- scanned_statement_url is populated for
        # statement transactions and nothing else -- so an unlabelled intake
        # still finds its filed copy instead of showing no archive at all.
        return deps.statement_archive_path(
            rows, vendor_key=(rows[0].get('vendor_key') if rows else ''))
    return ''


def scanner_intake_archive_path(deps: Collaborators, intake, rows):
    """Resolve the durable archive file used by scanner verification.

    Prefer the canonical ``bank_statements`` copy for statements. Older and
    corrected duplicate-only intakes may only have the DB-backed
    ``scanned_statement_url`` copy, so use that existing file as a safe
    fallback instead of reporting that no archive exists.
    """
    doc_kind = str((intake or {}).get('doc_kind') or '').strip().lower()
    archive_file = ''
    if doc_kind in STATEMENT_INTAKE_DOC_KINDS:
        archive_file = deps.statement_archive_path(
            rows, vendor_key=(rows[0].get('vendor_key') if rows else ''))
    if archive_file:
        return archive_file
    if doc_kind in STATEMENT_INTAKE_DOC_KINDS:
        scanned_statement_path, _moms_ledger_path = deps.associated_evidence_paths(rows)
        if scanned_statement_path and os.path.isfile(scanned_statement_path):
            return scanned_statement_path
    _pdf_path, receipt_path = deps.associated_source_paths(rows)
    return deps.recent_intake_archive_path(
        intake or {}, rows, receipt_path=receipt_path)


def scanner_statement_report(deps: Collaborators, scanner_key, intake):
    """Prefer the canonical archived statement report for one scanner intake.

    When a statement scan already has a real archived report.html that contains
    one of this intake's expense ids, serve that report directly instead of the
    synthetic intake page. This keeps the scanner tab aligned with the verified
    canonical artifact and avoids collapsing a statement down to whatever subset
    of ids happened to be forwarded in the intake callback.
    """
    if not isinstance(intake, dict):
        return None
    doc_kind = str(intake.get('doc_kind') or '').strip().lower()
    if doc_kind not in {'statement', 'bank_statement', 'tax_document'}:
        return None
    expense_ids = []
    for source in (intake.get('expense_ids') or [],
                   intake.get('duplicate_expense_ids') or [],
                   intake.get('scanned_statement_attached') or []):
        for value in source:
            try:
                expense_ids.append(int(value))
            except (TypeError, ValueError):
                continue
    if not expense_ids:
        return None
    seen = set()
    for expense_id in expense_ids:
        if expense_id in seen:
            continue
        seen.add(expense_id)
        found = deps.find_matching_report_row('', '', expense_id=expense_id)
        if not found:
            continue
        report_file = deps.report_file_for_url(found.report_path)
        if report_file:
            return {'url': found.report_path, 'file': report_file, 'expense_id': expense_id}
    return None
