#!/usr/bin/env python3
"""Generate HTML report validating id_light values and duplicates."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html import escape
from pathlib import Path
import os
import sys

from dotenv import load_dotenv
import pymysql

ROL_ROOT = Path("/home/adamsl/rol_finances")
ENV_PATH = Path("/home/adamsl/planner/.env")
REPORT_DIR = Path("/home/adamsl/rol_finances/reports")
ORG_ID = 1

sys.path.insert(0, str(ROL_ROOT))
from tools.generate_id_light.GenerateIDLight import GenerateIDLight  # noqa: E402
from tools.create_id_light.CreateIDLite import CreateIDLite  # noqa: E402


@dataclass
class ExpenseRow:
    id: int
    id_light: str | None
    description: str | None
    expense_date: object | None
    amount: object | None


def connect_db():
    load_dotenv(ENV_PATH)
    return pymysql.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        user=os.getenv("NON_PROFIT_USER"),
        password=os.getenv("NON_PROFIT_PASSWORD", ""),
        database=os.getenv("NON_PROFIT_DB_NAME", "nonprofit_finance"),
        port=int(os.getenv("DB_PORT", "3306")),
    )


def fetch_expenses(conn) -> list[ExpenseRow]:
    rows: list[ExpenseRow] = []
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, id_light, description, expense_date, amount FROM expenses WHERE org_id = %s",
            (ORG_ID,),
        )
        for item in cur.fetchall():
            rows.append(
                ExpenseRow(
                    id=item[0],
                    id_light=item[1],
                    description=item[2],
                    expense_date=item[3],
                    amount=item[4],
                )
            )
    return rows


def fetch_duplicates(conn) -> list[tuple[str, int, list[tuple]]]:
    duplicates: list[tuple[str, int, list[tuple]]] = []
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id_light, COUNT(*)
            FROM expenses
            WHERE org_id = %s AND id_light IS NOT NULL AND id_light != ''
            GROUP BY id_light
            HAVING COUNT(*) > 1
            ORDER BY COUNT(*) DESC
            """
        , (ORG_ID,))
        for id_light, count in cur.fetchall():
            cur.execute(
                """
                SELECT id, description, expense_date, amount
                FROM expenses
                WHERE org_id = %s AND id_light = %s
                LIMIT 5
                """,
                (ORG_ID, id_light),
            )
            samples = cur.fetchall()
            duplicates.append((id_light, count, samples))
    return duplicates


def to_amount(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def match_yaml_vendor_key(patterns, description: str) -> str | None:
    for pattern in patterns:
        regex_obj = pattern.get("regex")
        if regex_obj and regex_obj.search(description):
            return pattern.get("base")
    return None


def compute_expected(
    generator: GenerateIDLight,
    id_lite: CreateIDLite,
    patterns,
    row: ExpenseRow,
) -> tuple[str | None, str | None]:
    if not row.description or row.expense_date is None or row.amount is None:
        return None, "missing_fields"
    amount = to_amount(row.amount)
    if amount is None:
        return None, "invalid_amount"
    try:
        vendor_key = match_yaml_vendor_key(patterns, row.description)
        if vendor_key:
            date_val = row.expense_date
            date_string = (
                date_val.strftime("%m/%d/%y") if hasattr(date_val, "strftime") else str(date_val)
            )
            expected = id_lite.create_id_light(
                row.description,
                date_string,
                amount,
                vendor_key_override=vendor_key,
            )
        else:
            expected = generator.create_id_light(row.description, row.expense_date, amount)
    except Exception:
        return None, "generation_error"
    return expected, None


def build_table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return "<p>None</p>"
    head_html = "".join(f"<th>{escape(h)}</th>" for h in headers)
    body_html = "".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows
    )
    return f"<table class=\"data-table\"><thead><tr>{head_html}</tr></thead><tbody>{body_html}</tbody></table>"


def build_html(summary: dict, invalid_rows: list[dict], dup_rows: list[dict]) -> str:
    invalid_table = build_table(
        [
            "id",
            "id_light",
            "expected_id_light",
            "reason",
            "expense_date",
            "amount",
            "description",
        ],
        [
            [
                escape(str(row["id"])),
                escape(row["id_light"] or ""),
                escape(row["expected_id_light"] or ""),
                escape(row["reason"]),
                escape(row["expense_date"] or ""),
                escape(row["amount"] or ""),
                escape(row["description"] or ""),
            ]
            for row in invalid_rows
        ],
    )

    dup_table = build_table(
        ["id_light", "count", "samples"],
        [
            [
                escape(row["id_light"]),
                escape(str(row["count"])),
                row["samples"],
            ]
            for row in dup_rows
        ],
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>id_light Integrity Report</title>
<style>
  body {{ font-family: Arial, sans-serif; margin: 24px; color: #222; }}
  h1 {{ margin-bottom: 8px; }}
  .meta {{ color: #555; margin-bottom: 16px; }}
  table.data-table {{ border-collapse: collapse; width: 100%; }}
  table.data-table th, table.data-table td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
  table.data-table th {{ background: #f5f5f5; position: sticky; top: 0; }}
  table.data-table tr:nth-child(even) {{ background: #fafafa; }}
  .section {{ margin-top: 18px; }}
  .callout {{ background: #f8fbff; border: 1px solid #cfe3ff; padding: 12px 14px; border-radius: 6px; }}
</style>
</head>
<body>
  <h1>id_light Integrity Report</h1>
  <div class="meta">Generated: {escape(summary['generated'])}</div>

  <div class="section callout">
    <strong>Summary</strong>
    <ul>
      <li>Total expenses: {summary['total']}</li>
      <li>Invalid id_light rows: {summary['invalid']}</li>
      <li>Missing id_light rows: {summary['missing']}</li>
      <li>Duplicate id_light groups: {summary['duplicates']}</li>
    </ul>
  </div>

  <div class="section">
    <h2>Invalid id_light Rows</h2>
    {invalid_table}
  </div>

  <div class="section">
    <h2>Duplicate id_light Groups</h2>
    {dup_table}
  </div>
</body>
</html>"""


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    conn = connect_db()
    try:
        expenses = fetch_expenses(conn)
        duplicates = fetch_duplicates(conn)
    finally:
        conn.close()

    generator = GenerateIDLight()
    id_lite = CreateIDLite()
    patterns = id_lite._load_patterns()
    invalid_rows: list[dict] = []
    missing_count = 0
    for row in expenses:
        if not row.id_light:
            missing_count += 1
            expected, error_reason = compute_expected(generator, id_lite, patterns, row)
            if error_reason:
                expected = None
            invalid_rows.append(
                {
                    "id": row.id,
                    "id_light": row.id_light,
                    "expected_id_light": expected,
                    "reason": "missing_id_light",
                    "expense_date": str(row.expense_date) if row.expense_date else None,
                    "amount": str(row.amount) if row.amount is not None else None,
                    "description": row.description,
                }
            )
            continue

        expected, error_reason = compute_expected(generator, id_lite, patterns, row)
        if error_reason:
            invalid_rows.append(
                {
                    "id": row.id,
                    "id_light": row.id_light,
                    "expected_id_light": expected,
                    "reason": error_reason,
                    "expense_date": str(row.expense_date) if row.expense_date else None,
                    "amount": str(row.amount) if row.amount is not None else None,
                    "description": row.description,
                }
            )
            continue
        if expected and expected != row.id_light:
            invalid_rows.append(
                {
                    "id": row.id,
                    "id_light": row.id_light,
                    "expected_id_light": expected,
                    "reason": "mismatch",
                    "expense_date": str(row.expense_date) if row.expense_date else None,
                    "amount": str(row.amount) if row.amount is not None else None,
                    "description": row.description,
                }
            )

    dup_rows: list[dict] = []
    for id_light, count, samples in duplicates:
        sample_lines = []
        for sample in samples:
            sid, desc, exp_date, amount = sample
            sample_lines.append(escape(f"{sid} | {exp_date} | {amount} | {desc}"))
        dup_rows.append(
            {
                "id_light": id_light,
                "count": count,
                "samples": "<br>".join(sample_lines),
            }
        )

    summary = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(expenses),
        "invalid": len(invalid_rows),
        "missing": missing_count,
        "duplicates": len(dup_rows),
    }

    html = build_html(summary, invalid_rows, dup_rows)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = REPORT_DIR / f"id_light_integrity_report_{timestamp}.html"
    out_path.write_text(html, encoding="utf-8")
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
