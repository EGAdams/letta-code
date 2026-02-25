#!/usr/bin/env python3
"""Deduplicate expenses.id_light (non-null), keeping highest id."""
import os
import argparse
import pymysql

parser = argparse.ArgumentParser()
parser.add_argument('--dry-run', action='store_true', help='Report only, do not delete')
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

cur.execute("SELECT id_light, COUNT(*) FROM expenses WHERE id_light IS NOT NULL GROUP BY id_light HAVING COUNT(*)>1")
dups = cur.fetchall()
print('Duplicate groups (non-null):', len(dups))
for d in dups:
    print('  ', d[0], d[1])

if not dups:
    conn.close()
    raise SystemExit(0)

if args.dry_run:
    conn.close()
    print('Dry-run: no deletions performed.')
    raise SystemExit(0)

cur.execute("DELETE e FROM expenses e JOIN (SELECT id_light, MAX(id) keep_id FROM expenses WHERE id_light IS NOT NULL GROUP BY id_light HAVING COUNT(*)>1) keep ON e.id_light=keep.id_light AND e.id!=keep.keep_id")
print('Deleted rows:', cur.rowcount)
conn.commit()

cur.execute("SELECT COUNT(*) FROM expenses WHERE id_light IS NOT NULL GROUP BY id_light HAVING COUNT(*)>1")
rem = cur.fetchall()
print('Remaining duplicate groups:', len(rem))
conn.close()
