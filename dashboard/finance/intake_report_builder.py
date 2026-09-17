"""Synthetic recent-report page for an intake whose document has no
report.html (the normal case for scanner scans -- they store expenses in
MySQL but never generate a report file). Mirrors the Receipt Only page: a
#verified-transactions table of the intake's expenses with the same embedded
category-picker dialog, so recategorize / view-receipt work exactly like on a
real report.

``build_recent_intake_html``'s one job is to gather the intake's data. What
that data *means* belongs to ``finance.intake_report_model``, and how it
looks belongs to ``finance.intake_report_page``. Everything server.py still
owns -- expense lookup, source-path resolution, the picker assets, Mazda's
live progress -- arrives as a ``Collaborators`` bundle built fresh per call,
same reasoning as ``finance.recategorize.Collaborators``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from html import escape as _esc
from typing import Callable

from finance import intake_report_model, intake_report_page, manual_entry, vendor_lookup
from finance.intake_report_model import META_EMPTY
from finance.intake_report_model import document_type_label as _document_type_label
from finance.intake_report_model import format_month_range as _format_month_range
from hardware.scanners import SCANNERS
from intake.statuses import TERMINAL_INTAKE_STATUSES as _TERMINAL_INTAKE_STATUSES
from recent_intake_view import collapse_check_evidence_rows

#: What /report.html points at for the "View Source Document" link on a
#: synthetic intake report. Re-exported from server.py (http_app/get_routes.py
#: reads it as `srv.INTAKE_DOCUMENT_URL_PREFIX`), owned here because nothing
#: else in server.py uses it.
INTAKE_DOCUMENT_URL_PREFIX = '/api/intake-document'


@dataclass(frozen=True)
class Collaborators:
    """What stays behind in server.py, handed over per call."""

    fetch_expenses_by_ids: Callable
    associated_source_paths: Callable
    associated_evidence_paths: Callable
    recent_intake_archive_path: Callable
    statement_archive_path: Callable
    receipt_only_picker_assets: Callable
    receipt_only_cat_css: Callable
    mazda_intake_progress: Callable
    mazda_mode_current: Callable


def build_recent_intake_html(deps: Collaborators, intake):
    label = intake.get('label') or ''
    dispatched_at = intake.get('dispatched_at')
    when = ''
    if dispatched_at:
        when = datetime.fromtimestamp(float(dispatched_at)).strftime('%Y-%m-%d %H:%M')
    reported = intake.get('reported_at')
    intake_status = str(intake.get('status') or 'processing').lower()
    duplicate_ids = {
        int(i) for i in (intake.get('duplicate_expense_ids') or [])
        if str(i).isdigit()
    }

    rows, row_error = [], None
    try:
        rows = deps.fetch_expenses_by_ids(intake.get('expense_ids') or [])
        rows, promoted_duplicate_ids = collapse_check_evidence_rows(
            rows, duplicate_ids)
        duplicate_ids |= promoted_duplicate_ids
    except Exception as exc:
        row_error = str(exc)

    pdf_path, receipt_path = deps.associated_source_paths(rows)
    if intake.get('kind') == 'pdf':
        # Rule 2: the currently-processed document IS the PDF -- it's the
        # source regardless of what (date, amount) matching finds elsewhere.
        pdf_display = '<b>this.</b>'
    else:
        pdf_display = _esc(pdf_path) if pdf_path else META_EMPTY
    scanned_statement_path, moms_ledger_path = deps.associated_evidence_paths(rows)
    # Resolve the durable archive copy once: it is the ONLY scan-image path the
    # report is allowed to print. The intake's own image_path is a temporary
    # staging location, so showing it advertises a path that will not exist
    # tomorrow (and leaks the staging tree) -- the file name still appears as
    # "Most Recent Document", which is the part a reader can act on.
    archive_path = deps.recent_intake_archive_path(
        intake, rows, receipt_path=receipt_path)
    # The scanned statement is its own evidence slot, but for statement intakes
    # it resolves to the same archived copy -- print it only when it adds a path
    # the reader cannot already see.
    if archive_path and (
            scanned_statement_path == archive_path
            or archive_path == deps.statement_archive_path(
                rows, vendor_key=(rows[0].get('vendor_key') if rows else ''))):
        # For a statement these are two names for one page: scanned_statement_url
        # holds the raw scanner filename the DB happened to record, archive_path
        # the canonically-named copy actually filed. Printing both offers the
        # reader a stale path beside the real one.
        scanned_statement_path = ''

    def _path_field(path):
        return _esc(path) if path else META_EMPTY

    meta_fields = [
        ('Document Type', _esc(_document_type_label(
            intake.get('doc_kind'), intake.get('vendor')))),
        ('Month Range', _esc(_format_month_range(rows))),
        ('Associated PDF', pdf_display),
        ('Associated Receipt', _path_field(receipt_path)),
        ('Associated Scanned Statement', _path_field(scanned_statement_path)),
        ('Archived Scan Image', _path_field(archive_path)),
        ('Associated Mom’s Ledger', _path_field(moms_ledger_path)),
    ]

    picker_css, picker_html, click_css = '', '', ''
    try:
        picker_css, picker_html, click_css = deps.receipt_only_picker_assets()
    except Exception:
        pass  # picker unavailable → page still renders, rows just aren't clickable

    scanner_key = next((key for key, cfg in SCANNERS.items()
                        if cfg.get('name') == label), '')
    source_document_url = (
        f'{INTAKE_DOCUMENT_URL_PREFIX}?scanner={scanner_key}'
        if intake.get('kind') == 'scan' and scanner_key else '')
    # Refresh while we're still waiting on Mazda's STEP 8 report-back.
    terminal = intake_status in _TERMINAL_INTAKE_STATUSES
    working = ('' if (reported or terminal)
               else intake_report_page.mazda_working_html(
                   deps.mazda_intake_progress(intake)))
    # Unconditional since 2026-08-19. It used to appear only on a
    # needs_human_review intake -- i.e. only while Mazda was switched off --
    # so turning her back on took the review dialog away with her. The two are
    # separate questions: the switch decides who READS the next document, this
    # form is where a human CHECKS and corrects whatever was read, and that is
    # worth having in either mode. Save All still only inserts, so on a
    # document Mazda already filed it is the way to add an expense she missed;
    # correcting one she got wrong is Edit Expense's job, in the same dialog.
    presentation_rows_list = intake_report_model.presentation_rows(
        rows, duplicate_ids,
        stored=intake.get('stored'), parsed=intake.get('parsed'))
    source_descriptions = {}
    doc_kind = str(intake.get('doc_kind') or '').lower()
    if doc_kind in ('statement', 'bank_statement'):
        source_descriptions = intake_report_model.recover_statement_source_descriptions(
            f"{intake.get('image_path')}.statement.json"
            if intake.get('image_path') else '',
            presentation_rows_list,
        )
    elif doc_kind == 'receipt':
        receipt_token = hashlib.sha256(
            str(intake.get('image_path') or '').encode('utf-8')).hexdigest()[:12]
        source_descriptions = intake_report_model.recover_receipt_source_descriptions(
            f'/tmp/mazda_receipt_{receipt_token}.json'
            if intake.get('image_path') else '',
            presentation_rows_list,
        )
    presentation_rows_list = intake_report_model.apply_source_descriptions(
        presentation_rows_list, source_descriptions)
    presentation_rows_list = intake_report_model.apply_canonical_vendor_keys(
        presentation_rows_list,
        lambda description: manual_entry.resolve_vendor_match(
            description).get('vendor_key'),
    )
    # Mazda's own findings (whatever STEP 8 already stored for this document)
    # seed the review dialog instead of leaving it blank -- an auto-scan used
    # to only ever populate Verified Transactions, so checking/correcting what
    # she read meant running a manual receipt-reading command. resolve_vendor resolves
    # each row's *canonical* vendor_key (manual_entry.resolve_vendor_match)
    # so the dialog's vendor dropdown preselects a known merchant even though
    # the DB's own vendor_key column can hold a one-off, transaction-specific
    # slug rather than the reusable key the dropdown lists.
    stored_items = intake_report_model.stored_findings(
        presentation_rows_list,
        resolve_vendor=lambda description: manual_entry.resolve_vendor_match(
            description).get('vendor_key'),
        guess_vendor=vendor_lookup.guess_vendor_key,
        vendor_is_known=vendor_lookup.vendor_is_known)
    manual_entry_html = intake_report_page.manual_entry_form_html(
        intake.get('image_path'), intake.get('conversation_id'), scanner_key,
        mazda_mode=deps.mazda_mode_current(), stored_items=stored_items)
    # Unconditional, unlike the form above. Save All inserts, so it belongs
    # only to a scan nobody has typed in yet; Edit Expense corrects a row that
    # is already stored, so gating it on the same status made it unreachable
    # at exactly the moment it was needed.
    expense_edit_html = intake_report_page.expense_edit_panel_html()
    return intake_report_page.render_intake_report(
        headline=intake_report_model.display_document_name(
            archive_path, intake.get('document') or 'document'),
        subtitle=(f'{label} — ' if label else '') + f'dispatched {when}',
        meta_fields=meta_fields,
        status_text=intake_report_model.status_sentence(
            intake, rows, row_error=row_error,
            status_detail=intake.get('status_detail')),
        status_tone=intake_report_model.status_tone(
            intake_status, reported, rows),
        table_html=intake_report_page.transactions_table_html(
            presentation_rows_list,
            source_document_url=source_document_url,
            empty_note=intake_report_model.empty_table_note(
                intake_status, reported)),
        working_html=working,
        expense_edit_html=expense_edit_html,
        archive_path=archive_path,
        auto_refresh=not (rows or reported or terminal),
        extra_css=('\n' + deps.receipt_only_cat_css() + '\n' + click_css + '\n'
                   + picker_css + '\n'),
        picker_html=picker_html,
        manual_entry_html=manual_entry_html,
    )
