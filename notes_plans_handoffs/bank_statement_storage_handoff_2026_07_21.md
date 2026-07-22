# Bank Statement Year-Folder Storage — Handoff (2026-07-21)

## ⚠️ Read first — what's actually done vs. what's just agreed

**Nothing about bank statements has been implemented yet.** This entire shift was spent on
two adjacent things that ARE done (receipts year-folders, removing a bad hash-archive idea)
plus a long back-and-forth with EG designing the bank-statement rules below. The design is
solid and EG confirmed every piece of it — but zero code exists for it. Today's Chase-style
scan would still be handled exactly as before: parsed into MySQL rows, no file saved anywhere.

Start here. Everything below "The design (confirmed by EG)" is spec, not code.

## Why this exists

EG's underlying goal (same motivation as the receipts year-folders): a scanned document
should end up in a permanent, human-browsable location so the physical paper can be
discarded/archived ("put it in the attic for the feds") instead of kept as the real record.
Receipts already do this via `save_receipt_non_interactive` → `move_receipt_to_month_day_dir`.
**Statements currently do NOT** — `store_statement_transactions.py` only writes rows to MySQL;
the scanned image is never persisted anywhere durable. That gap is what this feature closes.

We tried one other approach first (a dashboard-side content-hash archive, independent of
document type) and EG explicitly killed it: a scanner produces different bytes on every pass
of the same physical paper, so hash matching can't detect a real re-scan — only a
byte-identical software double-dispatch, which `_claim_scan_dispatch` already handles. See
`~/.claude/projects/-home-adamsl-letta-code/memory/dashboard_permanent_scan_archive_2026_07_21.md`
for the full retraction if this comes up again — don't rebuild it.

## The design (confirmed by EG, via a real example — a Chase statement scanned 2026-07-20)

### 1. No more separate "loose statement" concept
Originally scoped as a distinct classification (official bank statement vs. informal/partial
statement) with its own `loose_statements/` folder. EG killed this after one round of
questions: **everything scanned as a statement — official or not — goes into
`bank_statements/`.** The `loose_statements/` folder EG manually created at
`~/rol_finances/readable_documents/loose_statements/` is now orphaned — delete it or repurpose
it, but don't build toward it.

### 2. Folder path: `bank_statements/{year}/{month}/{range}/`
- `{year}` = the reporting year (see rule 4 below for cross-year statements).
- `{month}` = the month name (lowercase, matches receipts convention: `january`, `december`, …) of
  the **earliest transaction in that year's copy**.
- `{range}` = `{firstmonth}_{firstday}__{lastmonth}_{lastday}`, built from the **earliest** and
  **latest transaction dates found in the document** — the full range, not just the days
  relevant to one reporting year.

Real example (the Chase statement processed this shift, transactions Jan 4–Jan 22 2025):
```
bank_statements/2025/january/january_04__january_22/
```

### 3. Image filename
```
{bank}_{last4}_{range}.jpg          # once the account number is known
{bank}_{range}.jpg                  # before it's known
```
Example: `chase_january_04__january_22.jpg` → later renamed/refiled to
`chase_1234_january_04__january_22.jpg` once the account's last 4 digits are confirmed. EG
did not specify exactly when/how "known" gets determined — see open question #1 below.

### 4. Cross-year statements: **copy into BOTH years**
This was the trickiest part of the design and went through two iterations before landing.
**Final rule, confirmed simplest by EG: if a statement's transactions span two calendar years,
save a full copy of the image into EACH year's folder tree**, not just one:

```
Dec 28, 2024 → Jan 5, 2025 statement produces BOTH:
  bank_statements/2024/december/december_28__january_05/   (imports only the Dec 2024 rows)
  bank_statements/2025/january/december_28__january_05/    (imports only the Jan 2025 rows)
```

- The **full range** (`december_28__january_05`) appears in BOTH folder names — don't truncate
  it per-year.
- Each copy's transaction import is filtered to **only that year's transactions** — never
  double-count a transaction across both reporting years.
- (We initially discussed a more complex "which report is currently being processed" input
  rule before landing on "just copy to both" — the simpler rule. If you find yourself building
  logic to determine "the active report year," stop — that complexity was explicitly rejected.)

### 5. Minimum required data (mentioned by EG, not yet re-confirmed after simplification)
Before the loose/official distinction was dropped, EG specified a general minimum-data halt
rule that should likely still apply, but wasn't re-confirmed in the final simplified design —
**ask EG before implementing** rather than assuming it still applies as originally stated:
- Receipts: require `{vendor_key, date, amount}` or halt for human review, no guessing.
- Statements: doesn't map 1:1 (many transactions, not one) — EG's original wording implied
  something like `{bank_vendor_key, earliest_date, latest_date}` at the document level, with
  each row still needing its own `{vendor_key, date, amount}` to store. Confirm this framing
  is still wanted before building it.

## Open questions to raise with EG before/while implementing

1. **How does the system know the account number to add `{last4}` to the filename?** Is this
   OCR'd from the statement image, does Mazda ask, is it looked up from a known-accounts table
   (rol_finances has `Known_Credit_Cards_and_Banks.xlsx` at the readable_documents root —
   maybe cross-reference that), or is it a manual rename EG does later? Not yet asked.
2. **Confidence threshold for "can't classify confidently" → human review**, for statements
   specifically. The general principle (never guess, halt instead) is well-established
   elsewhere in this codebase (see the receipts `_needs_review/` migration this shift as a
   worked example of the same philosophy) but the specific statement-classification confidence
   cutoff hasn't been discussed.
3. Does this apply retroactively to the 13 existing statement files already sitting flat in
   `readable_documents/bank_statements/` (see `dashboard/CLAUDE.md`'s "ROL Finance Reports"
   section — these already have real `report.html` files and are a different, established
   system)? Almost certainly **NOT** — those are the curated monthly bank-statement reports,
   a separate concern from raw scanner intake. Don't touch them without asking.

## Suggested implementation approach (not yet started, just a starting point)

Mirror what worked for receipts this shift — tests first, dry-run before any live move:

1. **New pure path-generator function**, analogous to `move_receipt_to_month_day_dir` in
   `rol_finances/tools/receipt_scanning_tools/receipt_parsing_tools/parse_and_categorize.py`
   (and its duplicate at repo-root `receipt_parsing_tools/` — remember both copies exist and
   diverge; see that file's new top-of-function comment for why). Something like
   `build_statement_archive_paths(transactions, bank_name, account_last4=None) -> list[(year_path, filtered_transactions)]`
   — returns one or two `(path, transactions)` pairs depending on whether the range crosses a
   year boundary. Write this as a standalone, side-effect-free function first; test it against
   the Chase example and a synthetic cross-year example before touching any file I/O.
2. **Wire into `store_statement_transactions.py`** (currently DB-only) to also copy the image
   into the computed path(s) and pass only the filtered per-year transactions to whatever does
   the DB insert.
3. **GoF separation** (EG's standing architecture rule, [[feedback_gof_ports_even_for_logging]]
   in memory): keep classification, date-range extraction, path generation, and file-copy as
   separably-testable pieces — don't fuse them into one function. The receipts migration this
   shift (`migrate_receipts_to_year_folders.py`) is a reasonable model: a pure `plan_*()`
   function returns a decision + reason, a separate runner executes it.
4. Mazda's actual instructions (memfs) need updating so she does this — see
   `mazda_memfs_update_procedure_2026_06_26` memory for the procedure (this is NOT a
   `git commit` to a normal file; it's a separate memfs push). **Nothing in her wrapper
   currently knows about any of this.**
5. Update `dashboard/trainer/mazda_trainer_instructions.md`'s contract checklist so the Trainer
   verifies the new archive step happened, same pattern as the receipt-store verification
   already in that file.

## What's already done this shift (context, not part of this handoff's scope)

- Receipts reorganized into `receipts/{year}/{month}/{day}/` (was `{month}/{day}`, year token
  from the filename was previously discarded). Migration script + tests committed:
  `rol_finances` commit `e64587c`. 74 uncertain files parked in `receipts/_needs_review/` with
  a manifest rather than guessed.
- Dashboard-side content-hash scan archive was built, then explicitly removed same day per EG
  — see the memory note above. Don't resurrect it. `letta-code` commit `782ee94`.
- Both repos pushed clean, nothing from concurrent live agents' WIP bundled in.

## Where things live

- Statement scan/store code: `rol_finances/tools/receipt_scanning_tools/parse_statement_scan.py`,
  `store_statement_transactions.py`.
- Vision classification: `rol_finances/tools/classify_scan.py` (`doc_type: bank_statement` — no
  official/loose distinction exists here; per rule 1 above, it doesn't need one anymore).
- Existing receipts precedent to copy the pattern from:
  `receipt_parsing_tools/parse_and_categorize.py` → `move_receipt_to_month_day_dir` +
  `_parse_receipt_date_from_stem` (both the root and `tools/receipt_scanning_tools/` copies —
  keep them in sync, see the sync-note comments added to both this shift).
- `~/rol_finances/readable_documents/Known_Credit_Cards_and_Banks.xlsx` — possibly relevant to
  open question #1 (account number lookup).
