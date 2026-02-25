#!/usr/bin/env python3
"""Report database health for nonprofit_finance."""
import os
import pymysql

DB_HOST = os.getenv('DB_HOST', '127.0.0.1')
DB_PORT = int(os.getenv('DB_PORT', '3306'))
DB_USER = os.getenv('NON_PROFIT_USER')
DB_PASS = os.getenv('NON_PROFIT_PASSWORD')
DB_NAME = os.getenv('NON_PROFIT_DB_NAME', 'nonprofit_finance')

if not DB_USER or not DB_PASS:
    raise SystemExit('Missing NON_PROFIT_USER or NON_PROFIT_PASSWORD env vars.')

conn = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME, port=DB_PORT, charset='utf8mb4')
cur = conn.cursor()

# duplicates on id_light (non-null)
cur.execute("SELECT id_light, COUNT(*) AS cnt FROM expenses WHERE id_light IS NOT NULL GROUP BY id_light HAVING cnt > 1 ORDER BY cnt DESC")
dups = cur.fetchall()
print('Duplicate id_light groups (non-null):', len(dups))
for r in dups[:20]:
    print(f"  {r[0]}\t{r[1]}")
if len(dups) > 20:
    print(f"  ... and {len(dups)-20} more")

# missing receipt_url
cur.execute("SELECT COUNT(*) FROM expenses WHERE receipt_url IS NULL OR receipt_url IN ('', 'null', 'nil', 'NULL')")
missing = cur.fetchone()[0]
print('Missing receipt_url rows:', missing)

conn.close()
