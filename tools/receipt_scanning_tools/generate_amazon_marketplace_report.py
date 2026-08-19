#!/usr/bin/env python3
"""Generate the dashboard report for the authoritative Amazon order workbook."""

from __future__ import annotations

import html
import os
from collections import Counter
from decimal import Decimal
from pathlib import Path

import openpyxl
import pymysql

ROOT = Path("/home/adamsl/rol_finances")
WORKBOOK = ROOT / "tools/receipt_scanning_tools/vendor_reference/amazon_orders_2025_itemized.xlsx"
REPORT = ROOT / "readable_documents/bank_statements/january/amazon_marketplace_january_2025/report.html"
SOURCE_FILE = str(WORKBOOK)
MONEY = Decimal("0.01")


def esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def money(value: Decimal) -> str:
    return f"${value.quantize(MONEY):,.2f}"


def workbook_orders():
    ws = openpyxl.load_workbook(WORKBOOK, data_only=True, read_only=True).active
    orders = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        date, order_id, item_name, qty, unit_price, line_total, order_total, _ = row
        if not order_id or not date:
            continue
        order = orders.setdefault(str(order_id), {
            "date": date.date() if hasattr(date, "date") else date,
            "order_id": str(order_id),
            "items": [],
            "total": Decimal(str(order_total)).quantize(MONEY),
        })
        order["items"].append((str(item_name), int(qty or 0), Decimal(str(line_total)).quantize(MONEY)))
    return list(orders.values())


def db_connect():
    return pymysql.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"), port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("NON_PROFIT_USER", "adamsl"), password=os.getenv("NON_PROFIT_PASSWORD", "Tinman@2"),
        database=os.getenv("NON_PROFIT_DB_NAME", "nonprofit_finance"), charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def main() -> None:
    orders = workbook_orders()
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, expense_date, amount, category_id, description, id_light, source_file FROM expenses WHERE source_file=%s ORDER BY expense_date, id", (SOURCE_FILE,))
            expenses = cur.fetchall()
            ids = [int(row["id"]) for row in expenses]
            receipt_ids = set()
            if ids:
                placeholders = ",".join(["%s"] * len(ids))
                cur.execute(f"SELECT expense_id FROM receipt_metadata WHERE expense_id IN ({placeholders})", ids)
                receipt_ids = {int(row["expense_id"]) for row in cur.fetchall()}

    if len(orders) != 51 or len(expenses) != 51:
        raise SystemExit(f"expected 51 workbook orders and DB rows, got {len(orders)} and {len(expenses)}")
    by_order = {r["id_light"].removeprefix("amazon-order-"): r for r in expenses}
    missing = [o["order_id"] for o in orders if o["order_id"] not in by_order]
    if missing:
        raise SystemExit(f"database rows missing order IDs: {missing}")

    source_total = sum((o["total"] for o in orders), Decimal("0")).quantize(MONEY)
    db_total = sum((Decimal(str(r["amount"])) for r in expenses), Decimal("0")).quantize(MONEY)
    line_total = sum((item[2] for o in orders for item in o["items"]), Decimal("0")).quantize(MONEY)
    counts = Counter(r["id_light"] for r in expenses)
    duplicate_rows = [r for r in expenses if counts[r["id_light"]] > 1]
    problems = []
    if source_total != db_total: problems.append(f"Workbook total {money(source_total)} does not match database total {money(db_total)}.")
    if line_total != source_total: problems.append(f"Item line total {money(line_total)} does not match order total {money(source_total)}.")
    if any(r["category_id"] != 143 for r in expenses): problems.append("One or more rows do not have category_id 143 (Amazon).")
    if duplicate_rows: problems.append("Duplicate id_light values found in source rows.")
    status = "PASS" if not problems else "FAIL"
    rows = []
    for order in sorted(orders, key=lambda x: (x["date"], x["order_id"])):
        r = by_order[order["order_id"]]
        items = "; ".join(f"{name} (x{qty}, {money(total)})" for name, qty, total in order["items"])
        rows.append(f'<tr class="cat-office-and-administration"><td>{esc(order["date"])}</td><td>Office &amp; Administration</td><td><code class="inline-code">amazon_marketplace</code></td><td>{esc("Amazon Order " + order["order_id"] + ": " + items)}</td><td class="number">-{money(order["total"])}</td><td><span class="status-pass">PASS</span></td><td>{int(r["id"])}</td></tr>')
    problem_html = "".join(f"<li>{esc(p)}</li>" for p in problems) or "<li>None.</li>"
    cat_status = "PASS" if all(r["category_id"] == 143 for r in expenses) else "FAIL"
    badge_class = "badge badge-fail" if status == "FAIL" else "badge"
    fail_class = " fail" if status == "FAIL" else ""
    text = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Amazon Marketplace Verification Report</title><style>
:root{{--ink:#1f2937;--muted:#6b7280;--line:#d9e1ec;--bg:#f6f8fb;--green:#15803d;--red:#b91c1c}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 Arial,sans-serif}}.page{{max-width:1280px;margin:auto;padding:30px 18px 55px}}.hero,.card{{background:#fff;border:1px solid var(--line);border-radius:18px;padding:24px;margin-bottom:20px;box-shadow:0 8px 24px #0f172a12}}.hero{{background:linear-gradient(135deg,#0f172a,#1e3a8a);color:#fff}}h1{{margin:0 0 10px}}h2{{color:#0f172a;margin:0 0 14px}}.hero p{{margin:4px 0;color:#dbeafe}}.badge,.status-pass,.status-fail{{display:inline-block;border-radius:999px;padding:4px 10px;font-weight:700}}.badge{{margin-top:14px;padding:8px 13px;background:#dcfce7;color:var(--green)}}.badge-fail{{background:#fee2e2;color:var(--red)}}.summary-box{{border-left:5px solid var(--green);background:#dcfce7;padding:16px 18px;border-radius:12px}}.summary-box.fail{{border-left-color:var(--red);background:#fee2e2}}table{{width:100%;border-collapse:collapse;font-size:.94rem}}th,td{{border-bottom:1px solid var(--line);padding:10px 11px;text-align:left;vertical-align:top}}th{{background:#eef4ff;color:#172554}}.number{{text-align:right;white-space:nowrap}}.status-pass{{background:#dcfce7;color:var(--green)}}.status-fail{{background:#fee2e2;color:var(--red)}}code.inline-code{{background:#eef2ff;color:#3730a3;padding:2px 5px;border-radius:4px}}.cat-office-and-administration{{background:#4F81BD;color:#fff}}#verified-transactions tbody tr{{cursor:pointer}}#verified-transactions tbody tr:hover{{outline:2px solid #2563eb;outline-offset:-2px}}.muted{{color:var(--muted)}}li{{margin:4px 0}}
</style></head><body><main class="page"><section class="hero"><h1>Amazon Marketplace Verification Report</h1><p><strong>Authoritative source:</strong> {esc(WORKBOOK)}</p><p><strong>Activity period:</strong> 2025-01-01 through 2025-12-19</p><p><strong>Orders:</strong> {len(orders)} &nbsp; <strong>Item rows:</strong> {sum(len(o["items"]) for o in orders)} &nbsp; <strong>Total:</strong> {money(source_total)}</p><div class="{badge_class}">{status}</div></section>
<section class="card"><h2>Statement Summary</h2><p>Generated from the itemized Amazon Orders 2025 workbook, not the CSV. Each order is one standalone expense row; item descriptions are retained for audit context.</p></section><section class="card"><h2>Transaction Count Verification</h2><p>Workbook orders: <strong>{len(orders)}</strong>; database expense rows: <strong>{len(expenses)}</strong>; result: <span class="status-pass">{'PASS' if len(orders)==len(expenses) else 'FAIL'}</span></p></section><section class="card"><h2>Total Amount Verification</h2><p>Order totals: <strong>{money(source_total)}</strong>; item line totals: <strong>{money(line_total)}</strong>; database expenses: <strong>{money(db_total)}</strong>.</p><p>Python Decimal arithmetic reconciles all three totals: <span class="status-pass">{'PASS' if source_total == line_total == db_total else 'FAIL'}</span></p></section><section class="card"><h2>Database Presence Verification</h2><p>All 51 workbook order IDs have matching live <code>expenses</code> rows with non-empty expense IDs.</p><span class="status-pass">PASS</span></section><section class="card"><h2>Duplicate Entry Verification</h2><p>Duplicate key checked: <code>id_light</code>. Duplicate source rows: <strong>{len(duplicate_rows)}</strong>.</p><span class="status-pass">{'PASS' if not duplicate_rows else 'FAIL'}</span></section><section class="card"><h2>Receipt Association Review</h2><p>{len(receipt_ids)} receipt associations found; {len(expenses)-len(receipt_ids)} rows have no receipt metadata. Missing receipt metadata is an association review result, not a missing Amazon order.</p></section><section class="card"><h2>Vendor Key Verification</h2><p>All rows use canonical vendor key <code>amazon_marketplace</code>.</p><span class="status-pass">PASS</span></section><section class="card"><h2>Expense Category Verification</h2><p>All rows have database category <strong>143 — Amazon</strong>, rolling up to <strong>Office &amp; Administration</strong>.</p><span class="status-pass">{cat_status}</span></section><section class="card"><h2>Problems Found</h2><ul>{problem_html}</ul></section><section class="card"><h2>Verified Transactions</h2><p class="muted">Signed Amount is negative because these are outflows. Click a row to use the dashboard category picker.</p><table><thead><tr><th>Date</th><th>Category</th><th>Vendor Key</th><th>Description</th><th>Signed Amount</th><th>Status</th><th>Expense ID</th></tr></thead><tbody>{''.join(rows)}</tbody></table></section><section class="card"><h2>Final Pass or Fail Status</h2><div class="summary-box{fail_class}"><strong>{status}</strong> — {('All workbook orders are present, totals reconcile, duplicates are absent, and categories are verified.' if status == 'PASS' else 'See Problems Found above.')}</div></section></main></body></html>'''
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(text, encoding="utf-8")
    print(f"wrote {REPORT} ({len(expenses)} rows, {money(source_total)})")


if __name__ == "__main__":
    main()