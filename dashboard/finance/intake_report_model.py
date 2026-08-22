"""What an intake record *means*, in the words the report page shows.

The Recent Report (intake mode) and the per-scanner Last Window/Freezer Scan
pages used to decide all of this inline, halfway through a 230-line function
that also queried the database and emitted HTML. That mixture is why a scan
that stalled rendered a headline of "Archived scan image unavailable" over six
rows of "--": nothing owned the question "what does this page have to say?".

This module owns exactly that question and nothing else. Everything here is a
pure function over plain data — no DB, no HTTP, no HTML — so the wording of a
stalled/duplicate/still-working scan can be tested directly.
"""

from __future__ import annotations

from datetime import datetime
import os

from pydantic import ValidationError

from finance.expense_fields import ExpenseFieldRules

#: A metadata field left at this marker has no value to report, and the page
#: omits its row rather than printing a dash.
META_EMPTY = '--'

#: Statuses meaning the intake reached a terminal outcome without Mazda's
#: STEP 8 report-back — the page must stop waiting for one.
FAILED_STATUSES = frozenset({'fail', 'stalled'})

#: MAZDA_DECISION_MODE=human_only: Mazda's turn never started, so — like
#: FAILED_STATUSES — there is no STEP 8 report-back to wait for. Kept
#: distinct from FAILED_STATUSES because this isn't a failure: the document
#: was deliberately routed to a human instead of Mazda's LLM turn.
HUMAN_REVIEW_STATUSES = frozenset({'needs_human_review'})

_DOC_KIND_LABELS = {
    'statement': 'Bank Statement',
    'bank_statement': 'Bank Statement',
    'receipt': 'Receipt',
    'tax_document': 'Tax Document',
    'invoice': 'Invoice (awaiting payment counterpart)',
    'other': 'Blank or non-financial document',
}


def document_type_label(doc_kind, vendor):
    """Human label for the 'Document Type' field, e.g. 'Chase Bank Statement'.

    doc_kind/vendor come from whichever document classifier ran (the
    deterministic facade's doc_kind/vendor for text-extractable PDFs, or
    Mazda's classify_scan.py vision result — doc_type/merchant — for scanned
    images, folded into the intake record by merge_recent_intake_event)."""
    kind_label = _DOC_KIND_LABELS.get((doc_kind or '').strip().lower())
    vendor = (vendor or '').strip()
    if vendor and vendor.lower() not in ('unknown', 'none'):
        vendor_label = vendor.replace('_', ' ').title()
        return f'{vendor_label} {kind_label}' if kind_label else vendor_label
    # 'Unknown' reads like a document type; this field is really reporting that
    # no classifier has named the document yet (a stalled scan's normal state).
    return kind_label or 'Not yet identified'


def format_month_range(rows):
    """'May 30, 2025 >>---> June 23, 2025' from the earliest/latest expense_date
    among rows, or META_EMPTY when there's nothing to show a range for."""
    dates = sorted({r['date'] for r in (rows or []) if r.get('date')})
    if not dates:
        return META_EMPTY

    def _fmt(value):
        try:
            return datetime.strptime(value, '%Y-%m-%d').strftime('%B %-d, %Y')
        except ValueError:
            return value

    if len(dates) == 1 or dates[0] == dates[-1]:
        return _fmt(dates[0])
    return f'{_fmt(dates[0])} >>---> {_fmt(dates[-1])}'


def display_document_name(archive_path, document):
    """The document this page is about, named by filename.

    Prefers the durable archive copy; otherwise falls back to whatever the
    intake was dispatched with. Always reduced to a basename: the staging
    directory a scan is being processed in is never part of the page, but the
    document's *name* always is — a page that refuses to say which document it
    is showing tells the reader nothing.
    """
    source = str(archive_path or '') or str(document or '')
    return os.path.basename(source) or source


def status_sentence(intake, rows, *, row_error='', status_detail=''):
    """The one sentence explaining where this intake stands."""
    status = str(intake.get('status') or 'processing').lower()
    parsed, stored = intake.get('parsed'), intake.get('stored')
    reported = intake.get('reported_at')
    detail = str(status_detail or '').strip()
    if status in HUMAN_REVIEW_STATUSES:
        return 'HUMAN-ONLY MODE.' + (f' {detail}' if detail else '')
    if status in FAILED_STATUSES:
        label = 'FAILED' if status == 'fail' else 'STALLED'
        return f'Mazda Trainer reported {label}.' + (f' {detail}' if detail else '')
    if rows:
        if stored == 0 and parsed:
            return (f'Mazda parsed {parsed} transaction(s); all were already in the '
                    f'database from an earlier run of this document. The {len(rows)} '
                    'matching rows are shown below — click one to (re)categorize it.')
        return (f'{len(rows)} transaction(s) recorded by this intake. '
                'Click a row to set its category.')
    if row_error:
        return ('Could not load this intake’s transactions from the database: '
                f'{row_error}')
    if reported:
        if str(intake.get('doc_kind') or '').lower() == 'other':
            return ('Mazda confirmed this scan is blank or non-financial. '
                    'No transactions were expected.')
        if parsed and not stored:
            return (f'Mazda parsed {parsed} transaction(s); all were already in the '
                    'database (duplicates of an earlier run of this document) — '
                    'nothing new was stored.')
        return 'Mazda finished this intake without storing new transactions.'
    return 'Dispatched to Mazda — processing… this page refreshes automatically.'


def status_tone(intake_status, reported, rows):
    """Banner tone for the status sentence: bad (failed or stalled), attention
    (routed to a human, not a failure), ok (transactions recorded), info
    (finished with nothing to store), or working (still waiting on Mazda).
    The page styles the banner from this."""
    if intake_status in FAILED_STATUSES:
        return 'bad'
    if intake_status in HUMAN_REVIEW_STATUSES:
        return 'attention'
    if rows:
        return 'ok'
    return 'info' if reported else 'working'


def empty_table_note(intake_status, reported):
    """Why the Verified Transactions table is empty. An empty table with no
    explanation is what made a stalled scan look like a working one."""
    if intake_status in FAILED_STATUSES:
        return ('This scan stopped before any transactions were stored, so '
                'there is nothing to verify for this document. Re-scan it to '
                'try again.')
    if intake_status in HUMAN_REVIEW_STATUSES:
        return ('MAZDA_DECISION_MODE=human_only — this document was not sent '
                'to Mazda. Process it manually from the Scanners/ROL Finance '
                'tabs.')
    if not reported:
        return ('Mazda is still reading this document — verified transactions '
                'appear here as they are stored.')
    return 'There is nothing to verify for this document.'


def presentation_rows(rows, duplicate_ids, *, stored=None, parsed=None):
    """DB rows -> the fields the table renders, with duplicates already marked.

    Whether a row is a duplicate is a judgement about the intake (a run that
    stored nothing but parsed something re-saw every row), not a rendering
    detail, so it is settled here rather than inside the HTML loop.
    """
    everything_was_a_duplicate = stored == 0 and bool(parsed)
    prepared = []
    for row in rows or []:
        row_id = row.get('id')
        prepared.append({
            'id': row_id or '',
            'cat_class': row.get('cat_class') or '',
            'vendor_key': row.get('vendor_key') or '',
            'description': row.get('description') or '',
            'amount': row.get('amount') or '',
            'date': row.get('date') or '',
            'reporting_category': row.get('reporting_category') or '',
            'duplicate': row_id in duplicate_ids or everything_was_a_duplicate,
        })
    return prepared


class StoredFinding(ExpenseFieldRules):
    """One of Mazda's own findings, already stored for this document.

    Feeds the review dialog's data-mazda-findings attribute (see
    finance/intake_report_page.py's manual_entry_form_html) so an automatic
    scan seeds the dialog with what she read instead of leaving it blank.
    Reusing ExpenseFieldRules -- the same merchant/date/amount rules
    manual_entry.ManualReceiptEntry and expense_edit_model.ExpenseEdit already
    enforce -- means a row that could not have been stored in the first place
    can never reach the browser as a "finding" either; stored_findings() below
    drops it instead.
    """

    category_name: str = ''


def stored_findings(rows):
    """`presentation_rows` output -> validated `StoredFinding`s for the dialog.

    Duplicate rows are excluded: a duplicate was already rejected as a repeat,
    not something to check/correct/re-save. A row that fails ExpenseFieldRules
    (e.g. a blank description slipped through, or an unparsable amount) is
    dropped rather than raised -- the review dialog degrades to asking the
    operator to fill it in by hand, same as it always has for a row Mazda
    never touched, instead of failing the whole page.
    """
    findings = []
    for row in rows:
        if row['duplicate']:
            continue
        try:
            # Stored rows carry a signed amount (negative = expense, see the
            # table's data-signed-amount); ExpenseFieldRules' total_amount is
            # the same always-positive magnitude every manual/Mazda-Fill entry
            # already uses, so the sign is normalised here, once.
            amount = abs(float(row['amount']))
        except (TypeError, ValueError):
            continue
        try:
            findings.append(StoredFinding(
                merchant_name=row['description'],
                transaction_date=row['date'],
                total_amount=amount,
                category_name=row['reporting_category'],
            ))
        except ValidationError:
            continue
    return findings
