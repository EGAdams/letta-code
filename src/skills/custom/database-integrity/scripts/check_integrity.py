from __future__ import annotations

from pathlib import Path
import json
import os
from datetime import date

from dotenv import load_dotenv
import pymysql

LAST_RUN = Path("/home/adamsl/rol_finances/events/logs/last_process_run.json")
ENV_PATH = Path("/home/adamsl/planner/.env")


def load_last_run():
    if not LAST_RUN.exists():
        raise SystemExit(f"Missing {LAST_RUN}")
    return json.loads(LAST_RUN.read_text())


def connect_db():
    load_dotenv(ENV_PATH)
    return pymysql.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        user=os.getenv("NON_PROFIT_USER"),
        password=os.getenv("NON_PROFIT_PASSWORD", ""),
        database=os.getenv("NON_PROFIT_DB_NAME", "nonprofit_finance"),
        port=int(os.getenv("DB_PORT", "3306")),
    )


def parse_id_light(id_light: str):
    tokens = (id_light or "").split("_")
    if len(tokens) < 6:
        return None
    tail = tokens[-5:]
    if not all(t.isdigit() for t in tail):
        return None
    vendor_key = "_".join(tokens[:-5])
    mm, dd, yy, dollars, cents = tail
    year = int(yy)
    if year < 100:
        year += 2000
    try:
        expense_date = date(year, int(mm), int(dd))
    except Exception:
        expense_date = None
    amount = f"{int(dollars)}.{int(cents):02d}"
    return vendor_key, expense_date, amount


def fetch_similar(cur, vendor_key: str | None, expense_date, amount: str | None):
    by_vendor = []
    by_date_amount = []
    if vendor_key:
        cur.execute(
            "SELECT id_light, expense_date, amount, description FROM expenses WHERE id_light LIKE %s LIMIT 10",
            (f"{vendor_key}%",),
        )
        by_vendor = cur.fetchall()
    if expense_date and amount:
        cur.execute(
            "SELECT id_light, expense_date, amount, description FROM expenses WHERE expense_date = %s AND amount = %s LIMIT 10",
            (expense_date, amount),
        )
        by_date_amount = cur.fetchall()
    return by_vendor, by_date_amount


def main() -> None:
    payload = load_last_run()
    skipped = payload.get("skipped_dup_id_lights", [])
    inserted = payload.get("inserted_id_lights", [])

    skipped_ids = [item["id_light"] if isinstance(item, dict) else item for item in skipped]
    inserted_ids = [item["id_light"] if isinstance(item, dict) else item for item in inserted]
    ids = list(dict.fromkeys(skipped_ids + inserted_ids))

    conn = connect_db()
    missing = []
    duplicates = []
    details = {}
    with conn.cursor() as cur:
        for id_light in ids:
            cur.execute("SELECT COUNT(*) FROM expenses WHERE id_light = %s", (id_light,))
            count = cur.fetchone()[0]
            if count == 0:
                missing.append(id_light)
                parsed = parse_id_light(id_light)
                if parsed:
                    vendor_key, expense_date, amount = parsed
                else:
                    vendor_key, expense_date, amount = None, None, None
                by_vendor, by_date_amount = fetch_similar(cur, vendor_key, expense_date, amount)
                details[id_light] = {
                    "vendor_key": vendor_key,
                    "expense_date": str(expense_date) if expense_date else None,
                    "amount": amount,
                    "similar_by_vendor": by_vendor,
                    "similar_by_date_amount": by_date_amount,
                }
            elif count > 1:
                duplicates.append(id_light)
    conn.close()

    print("checked", len(ids))
    print("missing", len(missing))
    print("duplicates", len(duplicates))
    if missing:
        print("missing_ids:")
        for item in missing:
            print(f"  {item}")
        print("\n-- similar rows for missing ids --")
        for item in missing:
            info = details.get(item) or {}
            print(f"\n{item}")
            print("  vendor_key:", info.get("vendor_key"))
            print("  expense_date:", info.get("expense_date"))
            print("  amount:", info.get("amount"))
            if info.get("similar_by_vendor"):
                print("  similar_by_vendor:")
                for row in info["similar_by_vendor"]:
                    print("   ", row)
            if info.get("similar_by_date_amount"):
                print("  similar_by_date_amount:")
                for row in info["similar_by_date_amount"]:
                    print("   ", row)
    if duplicates:
        print("duplicate_ids:")
        for item in duplicates:
            print(f"  {item}")


if __name__ == "__main__":
    main()
