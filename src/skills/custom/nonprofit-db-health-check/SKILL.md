---
name: nonprofit-db-health-check
description: Runs database health checks for nonprofit_finance (duplicate expenses.id_light, missing receipt_url, receipt matching) and can apply fixes with explicit approval. Use when asked to audit or fix database consistency for the nonprofit_finance project.
---

# Nonprofit DB Health Check

Use this skill to audit the `nonprofit_finance` MySQL database for data quality issues and (optionally) fix them. **Default is report-only** and **ask before applying changes if counts > 0**.

## Quick start (report-only)
1. Ensure DB env vars are set (see below).
2. Run:
   - `python3 scripts/report.py`

## Backup (recommended before fixes)
- Create a timestamped dump:
  - `python3 scripts/backup_db.py`
- Optional: `--output /path/to/backup.sql` or set `BACKUP_DIR`.

## Fixes (only after user approval)
- Dedupe non-null `expenses.id_light` (keep highest id):
  - `python3 scripts/dedupe_id_light.py`
- Enforce uniqueness for non-null `id_light`:
  - `python3 scripts/add_unique_index.py`
- Match receipts to missing `receipt_url` (ReceiptFinder):
  - `python3 scripts/receipt_match.py --dry-run`
  - then: `python3 scripts/receipt_match.py --log-path /tmp/receipt_match_log.tsv` (live)
  - review the log file for updated rows.

## Environment variables
These are read by all scripts:
- `DB_HOST` (default `127.0.0.1`)
- `DB_PORT` (default `3306`)
- `NON_PROFIT_USER`
- `NON_PROFIT_PASSWORD`
- `NON_PROFIT_DB_NAME` (default `nonprofit_finance`)
- `BACKUP_DIR` (default `/home/adamsl/rol_finances/backups`)

## Receipt matching inputs
- ReceiptFinder script: `/home/adamsl/rol_finances/tools/categorizer/ReceiptFinder.py`
- Receipts directory: `/home/adamsl/rol_finances/readable_documents/receipts`

## Policy
- **Report-only by default**.
- **Prompt before changes** if any duplicates or missing receipts are found.
- **Back up the DB** before any destructive changes.
