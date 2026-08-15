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

_PAGE_CSS = """
    body { font-family: Arial, sans-serif; margin:0; padding:20px; background:#f1f5f9; color:#0f172a; }
    section.card { background:#fff; border-radius:12px; padding:18px 20px; margin:0 auto; max-width:1100px; box-shadow:0 1px 3px rgba(0,0,0,.08); }
    h1 { font-size:1.4rem; margin:0 0 4px; } h2 { font-size:1.1rem; margin:18px 0 8px; }
    table { width:100%; border-collapse:collapse; overflow:hidden; border-radius:12px; font-size:0.95rem; }
    th, td { padding:8px 10px; border-bottom:1px solid #e5e7eb; text-align:left; }
    th { background:#0f172a; color:#fff; }
    th.number, td.number { text-align:right; }
    .muted { color:#6b7280; }
    .duplicate-row td { box-shadow:inset 0 2px #b91c1c,inset 0 -2px #b91c1c; }
    .duplicate-badge { display:inline-block; margin-left:8px; padding:2px 7px; border-radius:999px; background:#b91c1c; color:#fff; font-size:.72rem; letter-spacing:.04em; }
    .mazda-working { margin:16px 0; padding:12px; border:1px solid #3b4654; border-radius:10px; background:#000; color:#ffe761; }
    .mazda-working h2 { color:#fff; }
    .mazda-progress-shell { height:10px; overflow:hidden; border-radius:999px; background:rgba(10,16,24,.8); }
    .mazda-progress-bar { height:100%; background:#f4b400; }
    .mazda-working ul { margin:8px 0 0; padding-left:20px; }
    .mazda-step-done { color:#4ade80; } .mazda-step-active { color:#ffe761; font-weight:700; }
    .mazda-step-skipped, .mazda-step-pending { color:#9aa5b1; }
    .doc-meta { margin:12px 0; display:grid; gap:2px; font-size:0.92rem; }
    .doc-meta-row { overflow-wrap:anywhere; }
    .status-banner { margin:14px 0 0; padding:10px 12px; border-radius:10px; border-left:4px solid #94a3b8; background:#f8fafc; }
    .status-bad { border-left-color:#b91c1c; background:#fef2f2; color:#7f1d1d; font-weight:600; }
    .status-ok { border-left-color:#15803d; background:#f0fdf4; }
    .status-working { border-left-color:#f4b400; background:#fffbeb; }
"""


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


def render_intake_report(*, headline, subtitle, meta_fields, status_text,
                         status_tone, table_html, working_html='',
                         auto_refresh=False, extra_css='', picker_html=''):
    """Assemble the page. Every argument is already-decided content, so this
    function only ever answers "where does it go on the page?"."""
    refresh = '<meta http-equiv="refresh" content="30">' if auto_refresh else ''
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        + refresh +
        '<title>Recent Report</title><style>'
        + _PAGE_CSS + extra_css +
        '\n  </style></head><body>\n'
        '<section class="card">\n'
        f'  <h1>Most Recent Document: {_esc(headline)}</h1>\n'
        f'  <p class="muted">{_esc(subtitle)}</p>\n'
        + document_meta_html(meta_fields)
        + f'  <p class="status-banner status-{status_tone}">{_esc(status_text)}</p>\n'
        + working_html
        + table_html
        + '</section>\n' + picker_html + '\n</body></html>')
