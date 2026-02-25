#!/usr/bin/env python3
"""Add unique index on expenses.id_light if missing."""
import os
import argparse
import pymysql

parser = argparse.ArgumentParser()
parser.add_argument('--dry-run', action='store_true', help='Report only, do not alter table')
args = parser.parse_args()

DB_HOST = os.getenv('DB_HOST', '127.0.0.1')
DB_PORT = int(os.getenv('DB_PORT', '3306'))
DB_USER = os.getenv('NON_PROFIT_USER')
DB_PASS = os.getenv('NON_PROFIT_PASSWORD')
DB_NAME = os.getenv('NON_PROFIT_DB_NAME', 'nonprofit_finance')

if not DB_USER or not DB_PASS:
    raise SystemExit('Missing NON_PROFIT_USER or NON_PROFIT_PASSWORD env vars.')

conn = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME, port=DB_PORT, charset='utf8mb4')
cur = conn.cursor()

cur.execute("SELECT INDEX_NAME, NON_UNIQUE FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=%s AND TABLE_NAME='expenses' AND COLUMN_NAME='id_light'", (DB_NAME,))
rows = cur.fetchall()
if rows:
    print('Existing indexes on id_light:')
    for name, non_unique in rows:
        print(f"  {name} (non_unique={non_unique})")
else:
    print('No existing index on id_light.')

unique_exists = any(non_unique == 0 for _, non_unique in rows)
if unique_exists:
    print('Unique index already exists; nothing to do.')
    conn.close()
    raise SystemExit(0)

if args.dry_run:
    print('Dry-run: would add unique index ux_expenses_id_light.')
    conn.close()
    raise SystemExit(0)

cur.execute('ALTER TABLE expenses ADD UNIQUE INDEX ux_expenses_id_light (id_light)')
conn.commit()
print('Added unique index ux_expenses_id_light.')
conn.close()
