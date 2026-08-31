# Runbook: repointing a lost/retired Amex card's transactions to its replacement statement

When to use: a physical Amex card is reported lost, a new card number is issued, and
American Express re-issues (or re-numbers) the SAME account's transaction history under
the new card ending. The old card's transactions are already in the database — they
don't need to be recategorized, only re-labeled to point at the new statement file.

Worked example 2026-08-27: card ending -24007 (retired, tab was mislabeled "Platinum
Year") and card ending -4007 (also retired) were both replaced by card ending -26002
("6002"). Source file: `readable_documents/american_express_2025_6002_full_year.xlsx`.

## Steps

1. **Do NOT run the normal intake pipeline blind.** It will try to recategorize and may
   flag things wrong. First figure out how much of the new file already exists in the DB.

2. **Parse the new statement's "Transaction Details" sheet.** Real header row is NOT row 1
   — check for a banner/title row first (this file: header at row 7, data from row 8, not
   the row-6/row-7 assumed earlier in the session — always verify per file, Amex's export
   format has shifted before).

3. **Find existing `expenses` rows sourced from the OLD card's statement(s).** Search
   `source_file` / `document_url` / `scanned_statement_url` for the old filename patterns
   (spreadsheet AND scanned-image `.jpg` statements — a lost card's older months are often
   only present as scanned images, not xlsx). Match against the new file by
   `(expense_date, amount)` — this project's established match convention.

4. **Separately check whether the new file was ALREADY loaded once before**, independent
   of the old-card question. In this case 168 of 176 rows were already in the DB from a
   2026-02-16 load, with `source_file` left NULL. **Always check for this before assuming
   "new file = all new rows."** A raw `(date, amount)` scan across the whole `expenses`
   table (not just rows matching the old-card filenames) is the only reliable way to find
   this — the pipeline's own duplicate check historically had a bug in `--dry-run` mode
   that skipped it entirely (see gotcha below), so don't trust a dry-run preview count
   without cross-checking.

5. **Only 3 buckets of rows should exist after step 3+4:**
   - Old-card rows matching the new file → `UPDATE expenses SET source_file = '<new file
     path>' WHERE id IN (...)`. Do not touch `category_id`, `amount`, `expense_date`,
     `description`.
   - Rows already in the DB from a prior real load of the new file → leave alone entirely.
   - Rows with no match anywhere → run through the real (non-dry-run) pipeline so they get
     categorized and inserted normally.

6. **No new dashboard tab needed.** The tab (`dashboard/finance/report_registry.py`) keeps
   its existing `key`/`dir` — it's the same logical account, just a new card number. Only
   the underlying data changes; if the tab's `report.html` was generated from the OLD
   card's file, it needs to be regenerated from the corrected DB data covering both old
   and new card numbers.

## Gotcha found 2026-08-27 (fixed, see commit in `e_two_e_processing/process.py`)

`process.py`'s duplicate-existence check was wrapped in `if not dry_run:` — meaning
`--dry-run --batch` NEVER actually queried the database for existing rows, so its preview
counts (e.g. "147 would insert") were meaningless. It also lumped income-received lines
(e.g. "ELECTRONIC PAYMENT RECEIVED-THANK") into the same skipped-count as real duplicates,
mislabeling the summary. Both fixed: the existence check (read-only) now runs in preview
mode too; income skips get their own counter. If a future dry-run's "would insert" count
looks implausibly high relative to a manual `(date, amount)` spot-check against the DB,
suspect this class of bug again — dry-run modes that skip real lookups "for safety" instead
of skipping only the write are a recurring trap in this pipeline.

See also: [[mazda_statement_pipeline_manual_takeover]] (memory),
`rol_finances_receipt_parsing_divergent_copies_2026_07_21` (memory, on divergent copies of
`parse_and_categorize.py` — the same root-vs-real-module trap applies to `process.py`: the
root-level `process.py` in `rol_finances/` is a stale copy, the real one is
`e_two_e_processing/process.py`).
