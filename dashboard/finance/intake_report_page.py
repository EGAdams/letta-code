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

from html import escape as _esc

from .intake_report_model import META_EMPTY

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


def transactions_table_html(rows, *, source_document_url='', empty_note=''):
    """The Verified Transactions table. `rows` are presentation rows (see
    intake_report_model.presentation_rows); an empty list still renders the
    table, carrying `empty_note` so the page says why it is empty."""
    trs = []
    for row in rows:
        badge = (' <strong class="duplicate-badge">DUPLICATE</strong>'
                 if row['duplicate'] else '')
        trs.append(
            '<tr class="%s%s%s" data-expense-id="%s" '
            'data-source-document="%s" data-is-duplicate="%s" '
            'data-vendor-key="%s" data-description="%s" '
            'data-signed-amount="%s" data-date="%s" onclick="openCategoryPicker(this)" '
            'title="Click row to set category / view receipt">'
            '<td>%s</td><td class="number">%s</td><td>%s</td>'
            '<td class="category-cell" data-category-cell="true">%s</td></tr>' % (
                row['cat_class'], ' duplicate-row' if row['duplicate'] else '',
                ' has-receipt' if source_document_url else '',
                row['id'],
                _esc(source_document_url, quote=True),
                'true' if row['duplicate'] else 'false',
                _esc(row['vendor_key'], quote=True),
                _esc(row['description'], quote=True),
                _esc(row['amount'], quote=True),
                _esc(row['date'], quote=True),
                _esc(row['description']) + badge,
                _esc(row['amount']), _esc(row['date']),
                _esc(row['reporting_category']),
            ))
    body_rows = '\n'.join(trs) or (
        '<tr><td colspan="4" class="muted">%s</td></tr>' % _esc(empty_note))
    return ('  <h2>Verified Transactions</h2>\n'
            '  <table id="verified-transactions"><thead><tr>'
            '<th>Description</th><th class="number">Amount</th><th>Date</th>'
            '<th>Category</th></tr></thead><tbody>\n'
            + body_rows + '\n</tbody></table>\n')


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


def manual_entry_form_html(image_path, conversation_id, scanner_key=''):
    """The needs_human_review Save-by-hand form's mount point.

    All rendering and behavior live in js/implementation/manual-entry-form.js
    (backed by js/abstract/manual-entry.interface.js) — this only emits the
    mount point and the data it needs, matching how every other page-level
    widget in this app splits abstract/implementation. Python owns the
    server-rendered shell; the browser owns the form once it mounts.

    scanner_key (blank for a PDF-kind intake, no scanner involved) lets the
    form's post-save archive-verification terminal reuse the exact same
    /api/scanner-archive-path lookup the Scanner tabs already use.
    """
    return (
        '<div id="manual-entry-root" '
        f'data-image-path="{_esc(image_path or "", quote=True)}" '
        f'data-conversation-id="{_esc(conversation_id or "", quote=True)}" '
        f'data-scanner-key="{_esc(scanner_key or "", quote=True)}"></div>\n'
        '<script type="module" src="/js/implementation/manual-entry-form.js"></script>\n'
    )


def render_intake_report(*, headline, subtitle, meta_fields, status_text,
                         status_tone, table_html, working_html='',
                         auto_refresh=False, extra_css='', picker_html='',
                         manual_entry_html=''):
    """Assemble the page. Every argument is already-decided content, so this
    function only ever answers "where does it go on the page?"."""
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
        f'  <h1>Most Recent Document: {_esc(headline)}</h1>\n'
        f'  <p class="muted">{_esc(subtitle)}</p>\n'
        + document_meta_html(meta_fields)
        + f'  <p class="status-banner status-{status_tone}">{_esc(status_text)}</p>\n'
        + working_html
        + manual_entry_html
        + table_html
        + '  </div>\n'
        '</section>\n' + picker_html + '\n</body></html>')
