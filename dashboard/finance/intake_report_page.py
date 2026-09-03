"""The HTML of the synthetic intake report page.

Serves both `/recent_report.html` in intake mode and `/scanner_report.html`
(the Last Window Scan / Last Freezer Scan tabs). It receives everything it
needs as finished values — no database, no filesystem, no intake record — so
the page's layout can be changed and tested without going anywhere near the
scan pipeline.

Presentation rules that live here, because they are presentation:
  * a metadata field with nothing to say is omitted, not printed as '--';
  * the status sentence is a banner toned by outcome, not a bare paragraph;
  * an empty transactions table always carries the note explaining itself.
"""

from __future__ import annotations

import json
from html import escape as _esc
from typing import Sequence

from .intake_report_model import META_EMPTY, StoredFinding

# Static, page-wide rules live in css/finance/intake_report.css (served as a
# real stylesheet — see the server's generic /<path> static-file fallback).
# extra_css stays inline below because it's generated per-call (e.g. category
# colors), not something a static file can hold.
_PAGE_CSS_LINK = '<link rel="stylesheet" href="/css/finance/intake_report.css">'


def document_meta_html(fields):
    """The metadata block, from (label, html_value) pairs.

    Only fields carrying a value are rendered. An intake not yet matched to a
    PDF/receipt/archive copy used to print a column of '--' that buried the
    lines which did say something. Values arrive as HTML (some, like the PDF
    cell, are deliberate markup); labels are plain text.
    """
    rows = [(label, value) for label, value in fields
            if value and value != META_EMPTY]
    if not rows:
        return ''
    return ('  <div class="doc-meta">'
            + ''.join(f'<div class="doc-meta-row">{label}: {value}</div>'
                      for label, value in rows)
            + '</div>\n')


def archive_evidence_html(archive_path):
    """The one metadata line kept on the page: where this document was filed.

    The rest of that block -- Most Recent Document, Document Type, Month Range,
    Associated PDF/Receipt -- was removed from the dialog by request. This line
    came back because it answers the question actually being asked at the
    moment the paper goes into the attic: does a durable archived copy of this
    page exist, and where? Blank when no archive has been resolved, since
    there is then nothing to promise.
    """
    if not archive_path:
        return ''
    return document_meta_html([('Archived Scan Image', _esc(archive_path))])


#: The row actions, in the order they are drawn. Each is a plain <button>
#: carrying only its verb -- everything it needs to act on (the id, the
#: description) already sits on the <tr> as a data-* attribute, so the buttons
#: stay identical from row to row and js/implementation/verified-transaction-
#: rows.js reads the row rather than the button.
ROW_ACTIONS = (
    ('edit', 'Edit'),
    ('delete', 'Delete'),
    ('add-tax', 'Add 6%'),
)

#: "Edit" loads a row into the review dialog's Prev/Next list. With a single
#: transaction on the page that dialog is already showing it -- "Expense 1 of
#: 1" cannot go anywhere -- so the button would be a no-op wearing a verb.
EDIT_NEEDS_SIBLINGS = 2


def row_actions_html(*, show_edit=True):
    """The actions cell: Edit / Delete / Add 6% for one row."""
    buttons = ''.join(
        '<button type="button" class="vt-action" data-vt-action="%s">%s</button>'
        % (action, _esc(label))
        for action, label in ROW_ACTIONS
        if show_edit or action != 'edit')
    # The buttons sit in their own box, not directly in the cell: a <td> set
    # to display:flex stops being a table-cell and its column stops lining up
    # with the header above it.
    return ('<td class="vt-actions">'
            '<div class="vt-action-group">%s</div></td>' % buttons)


def transactions_table_html(rows, *, source_document_url='', empty_note=''):
    """The Verified Transactions table. `rows` are presentation rows (see
    intake_report_model.presentation_rows); an empty list still renders the
    table, carrying `empty_note` so the page says why it is empty.

    Every row carries an actions cell. The buttons are inert markup here --
    Python renders them and stops. Their behaviour (the confirm dialog, the
    review dialog's Prev/Next, the tax call) is browser work and lives in
    js/implementation/verified-transaction-rows.js, matching how the manual
    entry form and the category picker already split.
    """
    show_edit = len(rows) >= EDIT_NEEDS_SIBLINGS
    trs = []
    for row in rows:
        badge = (' <strong class="duplicate-badge">DUPLICATE</strong>'
                 if row['duplicate'] else '')
        trs.append(
            '<tr class="%s%s%s" data-expense-id="%s" '
            'data-source-document="%s" data-is-duplicate="%s" '
            'data-vendor-key="%s" data-id-light="%s" data-description="%s" '
            'data-signed-amount="%s" data-date="%s" onclick="openCategoryPicker(this)" '
            'title="Click row to set category / view receipt">'
            '<td>%s</td><td class="number">%s</td><td class="vt-date">%s</td>'
            '<td class="category-cell" data-category-cell="true">%s</td>%s</tr>' % (
                row['cat_class'], ' duplicate-row' if row['duplicate'] else '',
                ' has-receipt' if source_document_url else '',
                row['id'],
                _esc(source_document_url, quote=True),
                'true' if row['duplicate'] else 'false',
                _esc(row['vendor_key'], quote=True),
                _esc(row.get('id_light') or '', quote=True),
                _esc(row['description'], quote=True),
                _esc(row['amount'], quote=True),
                _esc(row['date'], quote=True),
                _esc(row['description']) + badge,
                _esc(row['amount']), _esc(row['date']),
                _esc(row['reporting_category']),
                row_actions_html(show_edit=show_edit),
            ))
    body_rows = '\n'.join(trs) or (
        '<tr><td colspan="5" class="muted">%s</td></tr>' % _esc(empty_note))
    return ('  <div class="dialog-panel">\n'
            '  <h2>Verified Transactions</h2>\n'
            '  <table id="verified-transactions"><thead><tr>'
            '<th>Description</th><th class="number">Amount</th>'
            '<th class="vt-date">Date</th>'
            '<th>Category</th><th class="vt-actions">Actions</th>'
            '</tr></thead><tbody>\n'
            + body_rows + '\n</tbody></table>\n'
            '  </div>\n'
            '<script type="module" '
            'src="/js/implementation/verified-transaction-rows.js"></script>\n')


def mazda_working_html(progress):
    """The live STEP 0-8 progress panel, shown only while Mazda still owes a
    report-back."""
    steps = ''.join(
        '<li class="mazda-step-%s">%s</li>' % (
            _esc(step.get('status') or 'pending'), _esc(step.get('label') or ''))
        for step in progress.get('steps', []))
    return ('<div class="mazda-working"><h2>Mazda Working</h2>'
            '<div class="mazda-progress-shell">'
            f'<div class="mazda-progress-bar" style="width:{int(progress.get("percent", 0))}%"></div>'
            '</div>'
            f'<p>{int(progress.get("completed", 0))} of '
            f'{int(progress.get("required", 0))} required steps complete</p>'
            f'<ul>{steps}</ul></div>')


def manual_entry_form_html(image_path, conversation_id, scanner_key='',
                           mazda_mode=None,
                           stored_items: Sequence[StoredFinding] = ()):
    """The Save-by-hand / review dialog's mount point, on every report page.

    All rendering and behavior live in js/implementation/manual-entry-form.js
    (backed by js/abstract/manual-entry.interface.js) — this only emits the
    mount point and the data it needs, matching how every other page-level
    widget in this app splits abstract/implementation. Python owns the
    server-rendered shell; the browser owns the form once it mounts.

    scanner_key (blank for a PDF-kind intake, no scanner involved) lets the
    form's post-save archive-verification terminal reuse the exact same
    /api/scanner-archive-path lookup the Scanner tabs already use.

    mazda_mode is the MazdaModeState in force (intake/mazda_mode.py). It is
    stamped here rather than fetched by the browser so the Automatic /
    Semi-Automatic switch renders already showing the truth — a toggle that
    paints itself in one position and corrects itself a moment later is a
    toggle nobody can trust. None means "don't stamp it", and the form falls
    back to the pipeline's own default (GET /api/mazda-mode answers the same
    question for anything rendering its own shell).

    stored_items, when non-empty, is what Mazda's own STEP 8 callback already
    read/stored for this document — see intake_report_model.stored_findings(),
    which turns presentation_rows_list into validated StoredFinding models. It
    seeds the form's item list so an automatic scan's findings are there to
    check/correct on load, the same way a manual receipt read fills them, and
    multi-transaction documents get Prev/Next for free since there is already
    more than one item.
    """
    mode_attrs = ''
    if mazda_mode is not None:
        mode_attrs = (
            f'data-mazda-automatic="{"true" if mazda_mode.automatic else "false"}" '
            f'data-mazda-mode-label="{_esc(mazda_mode.label, quote=True)}" ')
    findings_attr = ''
    if stored_items:
        findings_json = json.dumps(
            [item.model_dump() for item in stored_items])
        findings_attr = (
            f'data-mazda-findings="{_esc(findings_json, quote=True)}" ')
    return (
        '<div id="manual-entry-root" '
        f'data-image-path="{_esc(image_path or "", quote=True)}" '
        f'data-conversation-id="{_esc(conversation_id or "", quote=True)}" '
        f'{mode_attrs}'
        f'{findings_attr}'
        f'data-scanner-key="{_esc(scanner_key or "", quote=True)}"></div>\n'
        '<script type="module" src="/js/implementation/manual-entry-form.js"></script>\n'
    )


def expense_edit_panel_html():
    """The Edit Expense panel's own mount point, rendered on every report page.

    Kept as a separate mount point from the entry form even though that form is
    now unconditional too. It is the fallback: any page that renders this shell
    without the entry form still gets an Edit Expense button, and the two have
    never had the same reason to exist — Save All only ever *inserts*, while
    correcting an already-stored row only becomes useful once a row exists.
    Both endpoints behind it (/api/expense-search, /api/expense-edit) already
    answer on any intake.

    js/implementation/expense-edit-panel.js declines to mount when the entry
    form is also on the page, since that form carries its own copy of this
    dialog — one report page still shows exactly one Edit Expense button.
    """
    return (
        '<div id="expense-edit-root"></div>\n'
        '<script type="module" src="/js/implementation/expense-edit-panel.js"></script>\n'
    )


def render_intake_report(*, headline, subtitle, meta_fields, status_text,
                         status_tone, table_html, working_html='',
                         auto_refresh=False, extra_css='', picker_html='',
                         manual_entry_html='', expense_edit_html='',
                         archive_path=''):
    """Assemble the page. Every argument is already-decided content, so this
    function only ever answers "where does it go on the page?".

    `headline`, `subtitle` and `meta_fields` are accepted but deliberately not
    rendered: the "Most Recent Document" heading and the Document Type / Month
    Range / Associated-document block were removed from the top of the dialog
    by request. Do not "restore" them -- guarded by
    test_recent_intake_html_omits_document_metadata. The single exception is
    the archived-copy path, which comes in as `archive_path` and is filing
    evidence rather than metadata -- see archive_evidence_html.
    """
    refresh = '<meta http-equiv="refresh" content="30">' if auto_refresh else ''
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        + refresh +
        '<title>Recent Report</title>'
        '<link rel="stylesheet" href="/css/vendor/98css/98.css">'
        + _PAGE_CSS_LINK +
        '<style>'
        + extra_css +
        '\n  </style></head><body>\n'
        '<section class="card window">\n'
        '  <div class="title-bar">\n'
        '    <div class="title-bar-text">Recent Report</div>\n'
        '    <div class="title-bar-controls">'
        '<button aria-label="Minimize"></button>'
        '<button aria-label="Maximize"></button>'
        '<button aria-label="Close"></button></div>\n'
        '  </div>\n'
        '  <div class="window-body">\n'
        f'  <p class="status-banner status-{status_tone}">{_esc(status_text)}</p>\n'
        + archive_evidence_html(archive_path)
        + working_html
        + manual_entry_html
        + expense_edit_html
        + table_html
        + '  </div>\n'
        '</section>\n' + picker_html + '\n</body></html>')
