# Bank Statement Intake — current state (started 2026-07-21, updated 2026-07-22)

**Status: SHIPPED AND DEPLOYED.** Archiving, the fail-closed halt rules, the account
last-4 lookup, and the Scanner-screen review dialog are all live on DESKTOP-2OBSQMC.

> **This file used to open with "Nothing about bank statements has been implemented yet."**
> That was true the evening of 2026-07-21 and wrong by the next morning — a concurrent
> `letta.js --yolo` agent implemented the archiver while the design was still being
> discussed, and the stale warning cost a session's worth of wrong conclusions before
> anyone checked `git log`. **Verify any doc in this directory against the code and git
> history before trusting it.** Two live agents write to `rol_finances` and `letta-code`
> continuously.

## Why this exists

A scanned statement must end up in a permanent, human-browsable location so the physical
paper can be archived ("put it in the attic for the feds") rather than remaining the real
record. Receipts already did this via `save_receipt_non_interactive` →
`move_receipt_to_month_day_dir`; statements only wrote MySQL rows and never persisted the
image. That gap is now closed.

**Do not rebuild the content-hash archive.** An earlier dashboard-side approach hashed scan
bytes to detect re-scans; EG killed it because a scanner produces different bytes on every
pass of the same paper, so hashing only catches byte-identical software double-dispatch —
which `_claim_scan_dispatch` already handles. Retraction:
`~/.claude/projects/-home-adamsl-letta-code/memory/dashboard_permanent_scan_archive_2026_07_21.md`.

Also dropped: the separate "loose statement" classification. **Everything scanned as a
statement — official or not — goes into `bank_statements/`.** The orphaned
`readable_documents/loose_statements/` folder is not built toward.

## Where the code lives

| Concern | File |
|---|---|
| Vision extraction of rows | `rol_finances/tools/receipt_scanning_tools/parse_statement_scan.py` |
| Validation, archive planning, quarantine, amount suggestion | `…/statement_archive.py` |
| Account last-4 lookup | `…/known_accounts.py` |
| Dedupe + store + archive driver | `…/store_statement_transactions.py` |
| Back-fill of pre-existing loose files | `…/migrate_bank_statements_to_year_folders.py` |
| Vision classification (`doc_type: bank_statement`) | `rol_finances/tools/classify_scan.py` |
| Tests | `…/test_statement_archive.py`, `test_known_accounts.py`, `test_store_statement_rejects.py` |

Dashboard side (`letta-code/dashboard/`): `statement_review.py`,
`js/abstract/statement-review.interface.js`, `js/implementation/statement-review-dialog.js`,
`tests/test_statement_review.py`, `js/tests/statement-review.test.js`.

## Archive layout

```
readable_documents/bank_statements/{year}/{month}/{bank}_{last4}_{range}/{bank}_{last4}_{range}.jpg
                              e.g.  2025/march/american_express_4007_march_06__march_20/
```

- `{month}` = lowercase month name of the earliest transaction **in that year's copy**
  (matches the receipts convention).
- `{range}` = `{firstmonth}_{firstday}__{lastmonth}_{lastday}` from the earliest and latest
  transaction dates **in the whole document**, not just the part in one year.
- **The folder repeats the full file stem**, not just the range (revised 2026-07-22). Two
  accounts routinely share one statement period — Fifth Third 6285 and 5938 both had a
  `december_..__january_21` range in 2025/january — and a range-only folder collides.
  Existing folders were migrated.
- **Cross-year statements are copied into BOTH years.** The full range appears in both
  folder names; each copy's DB import is filtered to only that year's rows so nothing is
  double-counted. A more complex "which report year is active" rule was explicitly
  rejected — if you find yourself building that, stop.
- The archiver **copies, never moves**, and preserves an existing canonical copy rather
  than overwriting it with fresh scanner bytes. **A file still sitting in `incoming_scans/`
  is not evidence it failed to archive.**

## The rules EG confirmed (2026-07-22)

1. **Every row readable, or the whole statement is quarantined.** One unreadable date,
   description, or amount rejects the *entire* statement into
   `bank_statements/_needs_review/` with a JSON sidecar. No partial import, no guessing.
   *Why:* importing the readable rows and dropping the rest makes an expense vanish with
   nothing to notice it by, while the paper gets filed as "done" and discarded.
2. **An unresolved vendor is a different thing entirely.** That row is still stored, with
   `category_id = NULL` and `expense_status = NEEDS_VENDOR_KEY`, reported under
   `uncategorized` / `uncategorized_expense_ids` — **never counted in `failed`**. Same rule
   as receipts; it lands in the dashboard's New Records queue. (Before 2026-07-22 it raised
   and the transaction was never persisted at all.)
3. **Account last-4 is looked up, never invented.** Precedence: `--account-last4` → the
   number read off the statement → the known-cards workbook. If none resolve, the rejection
   carries `needs_workbook_entry: true`.
4. **Ambiguity halts.** Several cards at one bank (Amex ×2, Fifth Third ×3) means the
   printed bank name cannot identify the card; the lookup returns
   `workbook_ambiguous_last4` and stops rather than picking one.

## The known-cards workbook

`readable_documents/Known_Credit_Cards_and_Banks.xlsx`, sheet 1, **columns B/C/D only**.
Row 1 is a header; a historical duplicate E/F block must be ignored or every card
double-counts and looks ambiguous.

| B — Partial File Name | C — Last 4 | D — Printed on Statement |
|---|---|---|
| `american_express_1006` | `1006` | American Express |
| `barclays_bank_delaware_3965` | `3965` | Barclays Bank Delaware |
| `chase_5783` | `5783` | Chase |

**Column D is load-bearing**: a scan yields the bank's printed name ("Barclays Bank
Delaware"), not EG's shorthand. The lookup scores D and B and takes the best match. As of
2026-07-22 every column-B value equals what the archiver generates from column D, so B
genuinely describes the resulting filename.

Parsed with stdlib `zipfile` + `ElementTree` — **openpyxl is not installed in any venv on
any box**, and this isn't worth a runtime dependency.

### Excel traps (every one of these was hit for real)

- **Leading zeros are silently dropped** on unformatted numeric cells: `0062` stores as
  `62`. Column C is now formatted as **text** so stored == displayed.
  `workbook_last4(cell, partial_file_name)` still restores zeros from column B when the two
  agree numerically, and fails closed on a genuine mismatch.
- **Never truncate the other way.** Two Amex rows once held FIVE digits (`61006`); taking
  the trailing four would have invented account "1006". A non-4-digit cell is unusable.
- **Writing the file while EG has it open in Excel loses the write.** Excel saves its stale
  in-memory copy over yours; it does not merge. Ask EG to close it, back up first, verify
  after.
- **Edit it with zip/XML surgery, not openpyxl** — the workbook carries cell comments and a
  `legacyDrawing` that a library rewrite would drop. Copy every zip entry through
  byte-for-byte and patch only `xl/worksheets/sheet1.xml` (+ `styles.xml` for formats).

## The bug that made the halt rule unreachable

`parse_statement_scan.py` used to `continue` past any row whose amount wouldn't `float()`
or whose date/description was blank — **deleting real transactions before the store step
ever saw them**. The "one bad row quarantines the statement" rule therefore could never
fire from a real scan, because the bad rows were already gone.

Fixed 2026-07-22: every row is emitted, with `None` in the unreadable field plus
`unreadable: true`, and the vision prompt instructs the model to do the same and never
guess. The parser also now returns `statement_total` (the printed total of new charges).

**Generalize this:** if a fail-closed rule appears never to trigger, check whether an
upstream layer already discarded the bad input.

## The review dialog (Scanner screen)

The quarantine sidecar is a **self-contained retry packet** — all rows, the statement
total, per-row suggestions, workbook state, archive root, env path — so a quarantined
statement is re-runnable without re-scanning or re-parsing. This is deliberately
*retry-after-the-fact* rather than pausing Mazda mid-run and holding state.

| Endpoint | Purpose |
|---|---|
| `GET /api/statement-reviews` | Pending quarantined statements, newest first |
| `POST /api/statement-review-resolve` `{id, amounts?}` | Re-run the store with human-supplied values |

- **Missing card** → "add a row for this card, then press OK". OK re-runs (the workbook is
  re-read on every lookup). A still-missing row **leaves the item queued so the dialog
  reappears** — EG's explicit requirement.
- **Unreadable amount** → one input per bad row, prefilled from
  `suggest_missing_amount()`, which reconstructs exactly ONE missing amount as
  `printed_total − sum(readable)`. Two unknowns, or no printed total, yields **no
  suggestion** rather than a wrong one.
- A blank entry is an error, never a silent skip — skipping would resubmit the same hole
  and re-quarantine the statement.

## Running the tests

On **DESKTOP-SHDBATI** no venv has the full stack, and the repo-root `conftest.py` loads
`tools/receipt_scanning_tools/app/db/__init__.py`, which imports `pymysql` — collection
aborts with an INTERNALERROR before any test runs. Bypass it with `--confcutdir`:

```bash
cd /home/adamsl/rol_finances
PYTHONPATH=/home/adamsl/rol_finances browser_tools/.venv/bin/pytest \
  tools/receipt_scanning_tools/test_known_accounts.py \
  tools/receipt_scanning_tools/test_statement_archive.py \
  tools/receipt_scanning_tools/test_store_statement_rejects.py \
  -q -p no:cacheprovider --confcutdir=tools/receipt_scanning_tools
```

On the live box use `/home/adamsl/rol_finances/.venv/bin/python3 -m pytest` with the same
flags (33 pass there). Dashboard: `.venv/bin/python -m pytest tests/` and
`bun test js/tests`.

`test_store_statement_rejects.py` stubs the DB modules via `sys.modules`, so the reject
path runs with no database. Tests importing `parse_statement_scan` fail on SHDBATI for
missing `google.generativeai` — pre-existing, not a regression.

## Deploying

**Editing on SHDBATI changes nothing** — it runs only `dashboard-proxy.service`, a TCP
forwarder. The live code is on DESKTOP-2OBSQMC (`Ubuntu-26.04`). Push, then pull there:

```bash
ssh NewUser@100.118.122.75 'wsl.exe -d Ubuntu-26.04 -e bash -lc "git -C /home/adamsl/rol_finances pull --ff-only origin main"'
```

Use the base64-piped script pattern from `dashboard/CLAUDE.md` for anything non-trivial.
Two files are perpetually dirty there and are safe to `git checkout --` before pulling:
`rol_finances.egg-info/SOURCES.txt` and `dashboard/claude_toolcalls.json`. Restart
`dashboard-server.service` **only** when `server.py` changed — the statement scripts and
the Trainer instructions are read fresh on every run.

## Mazda's memory

Her `system/statement_intake_procedure` block carries these rules (steps 6, 6a, 6b).
**`git push` to `state.git` alone is inert** — verified 2026-07-22, the block was unchanged
until `letta-code/scripts/project_memfs_to_blocks.py --agent <id>` ran. Before pushing,
confirm every attached block label has a top-level `system/<label>.md` file, or the
re-derivation can detach it; `statement_intake_procedure` was found existing *only* as a
block with no file, and pushing blind would have wiped it.

## Pre-existing loose files at the `bank_statements/` root (audited 2026-07-21)

There are **15** loose PDFs at the `bank_statements/` root, not the 13 an older note
claimed (verified 2026-07-22: `ls *.pdf` = 15, plus a stray
`choice Credit Card Year End052826.csv` and `finance_directory_listing.php` that are not
scanned statements). Nine of the 15 now have byte-identical canonical year/range copies —
some loose names were duplicate aliases: `3686285_december_january.pdf`,
`3686285_january_february.pdf`, `7735938_december_january.pdf`,
`7735938_december_january_check_images.pdf`, `7735938_january_february.pdf`,
`diners_december_january.pdf`, `first_rol_bank_statement.pdf`,
`jet_blue_february_march.pdf`, `jet_blue_january_february.pdf`.

Six were deliberately left untouched because no trustworthy full transaction range was
available (provider timeout, no report evidence): `7735938_june_july.pdf`,
`7735938_may_june_check_images.pdf`, `JET BLUE AnnualSummary2025-3965.pdf`,
`fnbo_year-end-summary-2025.pdf`, `june_statement.pdf`, `may_statement.pdf`.
**Do not infer their ranges from filenames** — rerun the bounded audit or supply verified
metadata. Originals were not removed, so existing links stay valid.

The curated monthly statement reports (the ones with real `report.html` files, see
`dashboard/CLAUDE.md` → "ROL Finance Reports") are a **separate, established system** from
raw scanner intake. Don't restructure them without asking.

## Not built / open

- No UI for browsing `_needs_review/` history; the dialog surfaces only pending items.
- `united_0062`, `fnbo_4851`, `choice_7580` were filled into the workbook on 2026-07-22 and
  have not been exercised by a real scan.
- The Trainer verifies the contract but has not yet observed a live quarantine run.
