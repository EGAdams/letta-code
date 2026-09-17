"""Rendering the standalone Receipt Only report page.

Mirrors the restructured Verified Transactions table (Description | Amount |
Date, clickable rows with data-* attrs) and embeds the identical category
picker, so the existing /api/receipts-present marker, /api/recategorize-expense
and /api/receipt-lookup all drive it without change.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape as _esc
from typing import Callable


@dataclass(frozen=True)
class Collaborators:
    """What stays behind in server.py, handed over per call."""

    receipt_only_picker_assets: Callable
    fetch_receipt_only_rows: Callable
    receipt_only_cat_css: Callable


def build_receipt_only_report_html(deps: Collaborators, month_key=None):
    picker_css, picker_html, click_css = deps.receipt_only_picker_assets()
    rows = deps.fetch_receipt_only_rows(month_key)
    trs = []
    for r in rows:
        trs.append(
            '<tr class="%s%s" data-expense-id="%s" data-human-verified="%s" data-vendor-key="%s" data-description="%s" '
            'data-signed-amount="%s" data-date="%s" onclick="openCategoryPicker(this)" '
            'title="Click row to set category / view receipt">'
            '<td>%s</td><td class="number">%s</td><td>%s</td></tr>' % (
                r['cat_class'], ' human-verified' if r.get('human_verified') else '',
                _esc(str(r['id']), quote=True),
                'true' if r.get('human_verified') else 'false',
                _esc(str(r['vendor_key']), quote=True),
                _esc(str(r['description']), quote=True),
                _esc(str(r['amount']), quote=True),
                _esc(str(r['date']), quote=True),
                _esc(str(r['description'])), _esc(str(r['amount'])), _esc(str(r['date'])),
            ))
    body_rows = '\n'.join(trs) if trs else (
        '<tr><td colspan="3" class="muted">No receipt-only records.</td></tr>')
    head = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>Receipt Only</title><style>\n'
        '    body { font-family: Arial, sans-serif; margin:0; padding:20px; '
        'background:#f1f5f9; color:#0f172a; }\n'
        '    section.card { background:#fff; border-radius:12px; padding:18px 20px; '
        'margin:0 auto; max-width:1100px; box-shadow:0 1px 3px rgba(0,0,0,.08); }\n'
        '    h1 { font-size:1.4rem; margin:0 0 4px; } h2 { font-size:1.1rem; margin:18px 0 8px; }\n'
        '    table { width:100%; border-collapse:collapse; overflow:hidden; '
        'border-radius:12px; font-size:0.95rem; }\n'
        '    th, td { padding:8px 10px; border-bottom:1px solid #e5e7eb; text-align:left; }\n'
        '    th { background:#0f172a; color:#fff; }\n'
        '    th.number, td.number { text-align:right; }\n'
        '    .muted { color:#6b7280; }\n'
        + deps.receipt_only_cat_css() + '\n'
        + click_css + '\n'
        + picker_css + '\n'
        + '  </style></head><body>\n'
        '<section class="card">\n'
        '  <h1>Receipt Only</h1>\n'
        '  <p class="muted">Receipts not associated with any bank-statement '
        'transaction. Click a row to set its category or view the receipt.</p>\n'
        '  <h2>Verified Transactions</h2>\n'
        '  <table id="verified-transactions"><thead><tr>'
        '<th>Description</th><th class="number">Amount</th><th>Date</th>'
        '</tr></thead><tbody>\n'
    )
    return head + body_rows + '\n</tbody></table>\n</section>\n' + picker_html + '\n</body></html>'
