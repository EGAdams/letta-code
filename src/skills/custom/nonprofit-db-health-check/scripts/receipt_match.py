#!/usr/bin/env python3
"""Match receipts to expenses with missing receipt_url."""
import os
import argparse
import importlib.util
from pathlib import Path
import pymysql

parser = argparse.ArgumentParser()
parser.add_argument('--dry-run', action='store_true', help='Report only, do not update DB')
parser.add_argument('--limit', type=int, default=0, help='Limit number of rows to process (0 = no limit)')
parser.add_argument('--fuzzy', action='store_true', help='Allow fuzzy fallback using ReceiptFinder token search')
parser.add_argument('--log-path', help='Write updated rows to TSV log')
args = parser.parse_args()

DB_HOST = os.getenv('DB_HOST', '127.0.0.1')
DB_PORT = int(os.getenv('DB_PORT', '3306'))
DB_USER = os.getenv('NON_PROFIT_USER')
DB_PASS = os.getenv('NON_PROFIT_PASSWORD')
DB_NAME = os.getenv('NON_PROFIT_DB_NAME', 'nonprofit_finance')

if not DB_USER or not DB_PASS:
    raise SystemExit('Missing NON_PROFIT_USER or NON_PROFIT_PASSWORD env vars.')

RECEIPT_ROOT = Path(os.getenv('RECEIPT_ROOT', '/home/adamsl/rol_finances/readable_documents/receipts'))
RECEIPT_FINDER_PATH = os.getenv('RECEIPT_FINDER', '/home/adamsl/rol_finances/tools/categorizer/ReceiptFinder.py')

# Load ReceiptFinder
spec = importlib.util.spec_from_file_location('receiptfinder', RECEIPT_FINDER_PATH)
rf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rf)
ReceiptFinder = rf.ReceiptFinder
finder = ReceiptFinder(receipts_root=RECEIPT_ROOT)

# Build stem map for exact matching
stem_map = {}
for dirpath, _, filenames in os.walk(RECEIPT_ROOT):
    for fn in filenames:
        ln = fn.lower()
        if ln.endswith(('.png', '.jpg', '.jpeg')):
            stem = os.path.splitext(fn)[0].lower()
            stem_map.setdefault(stem, []).append(Path(dirpath) / fn)

conn = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME, port=DB_PORT, charset='utf8mb4')
cur = conn.cursor()
cur.execute("SELECT id, id_light FROM expenses WHERE receipt_url IS NULL OR receipt_url IN ('', 'null', 'nil', 'NULL')")
rows = cur.fetchall()
if args.limit and args.limit > 0:
    rows = rows[:args.limit]

print('Missing rows:', len(rows))
updated = 0
log_fh = None
if args.log_path:
    log_fh = open(args.log_path, 'w', encoding='utf-8')
    log_fh.write('id\tid_light\treceipt_name\n')

for id_, id_light in rows:
    if not id_light:
        continue
    key = str(id_light).lower()
    matched = None

    # exact stem match
    if key in stem_map:
        matched = stem_map[key][0]
    elif args.fuzzy:
        # fallback: use ReceiptFinder token search and require exact stem match in candidates
        candidates = finder.find_receipts(key, limit=10)
        for p in candidates:
            if p.is_file() and p.stem.lower() == key:
                matched = p
                break
        if not matched:
            token = key.split('__')[0].split('_')[0]
            if token:
                candidates = finder.find_receipts(token, limit=10)
                for p in candidates:
                    if p.is_file() and p.stem.lower() == key:
                        matched = p
                        break

    if matched:
        receipt_name = matched.name
        if args.dry_run:
            print(f'DRY-RUN: {id_} {id_light} -> {receipt_name}')
        else:
            cur.execute("UPDATE expenses SET receipt_url = %s WHERE id = %s", (receipt_name, id_))
            if cur.rowcount > 0:
                updated += cur.rowcount
                print(f'UPDATED: {id_} {id_light} -> {receipt_name}')
                if log_fh:
                    log_fh.write(f"{id_}\t{id_light}\t{receipt_name}\n")

if not args.dry_run:
    conn.commit()

print('Updated:', updated)
if log_fh:
    log_fh.close()
conn.close()
