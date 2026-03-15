from __future__ import annotations

from pathlib import Path
import json
import os
from typing import Dict, List, Tuple

from dotenv import load_dotenv
import pymysql

LAST_RUN_PATH = Path("/home/adamsl/rol_finances/events/logs/last_process_run.json")
ENV_PATH = Path("/home/adamsl/planner/.env")


def load_last_run() -> Dict:
    if not LAST_RUN_PATH.exists():
        raise SystemExit(f"Missing {LAST_RUN_PATH}. Run process.py first.")
    return json.loads(LAST_RUN_PATH.read_text())


def connect_db():
    load_dotenv(ENV_PATH)
    return pymysql.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        user=os.getenv("NON_PROFIT_USER"),
        password=os.getenv("NON_PROFIT_PASSWORD"),
        database=os.getenv("NON_PROFIT_DB_NAME", "nonprofit_finance"),
        port=int(os.getenv("DB_PORT", "3306")),
    )


def check_id_lights(conn, id_lights: List[str]) -> Tuple[List[str], List[str]]:
    missing = []
    duplicates = []
    if not id_lights:
        return missing, duplicates
    with conn.cursor() as cur:
        for id_light in id_lights:
            cur.execute(
                "SELECT COUNT(*) FROM expenses WHERE id_light = %s",
                (id_light,),
            )
            count = cur.fetchone()[0]
            if count == 0:
                missing.append(id_light)
            elif count > 1:
                duplicates.append(id_light)
    return missing, duplicates


def main() -> None:
    last_run = load_last_run()
    inserted_ids = last_run.get("inserted_id_lights", [])
    skipped_dup_ids = last_run.get("skipped_dup_id_lights", [])

    conn = connect_db()
    try:
        missing, duplicates = check_id_lights(conn, inserted_ids)
    finally:
        conn.close()

    print("--- Last Process Run ---")
    print(f"file: {last_run.get("filename")}")
    print(f"processed: {last_run.get("processed")}")
    print(f"inserted: {last_run.get("inserted")}")
    print(f"skipped_duplicate: {last_run.get("skipped_duplicate")}")
    print(f"uncategorized: {last_run.get("uncategorized")}")
    print(f"dry_run: {last_run.get("dry_run")}")
    print("--- Insert Verification ---")
    print(f"inserted_id_lights: {len(inserted_ids)}")
    print(f"missing: {len(missing)}")
    print(f"duplicates: {len(duplicates)}")
    if missing:
        print("missing_ids:")
        for item in missing:
            print(f"  {item}")
    if duplicates:
        print("duplicate_ids:")
        for item in duplicates:
            print(f"  {item}")

    if skipped_dup_ids:
        print("--- Skipped Duplicates (by process) ---")
        for item in skipped_dup_ids:
            print(f"  {item}")


if __name__ == "__main__":
    main()
