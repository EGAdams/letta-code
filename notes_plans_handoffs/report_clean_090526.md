# Handoff — Report Accuracy + JetBlue Rebuild (2026-09-05)

## Read this first

```bash
git -C /home/adamsl/letta-code log -1
git -C /home/adamsl/rol_finances log -1
```

Two repos changed. Both are committed and pushed to `origin/main`:

- `letta-code` `3480d74e` — dashboard tab colour now comes from the auditor.
- `rol_finances` `45289dc` — source-anchored audit checks + the JetBlue rebuild.

## What was wrong

A report's green badge is written by the report **about itself**. Four reports
carried a different statement's numbers and stayed green for months. Two of them
(the JetBlue pair) were never generated at all — a finished Fifth Third report
was copied, the title changed, and every balance left behind.

## What changed

### Dashboard — the tab colour is now a second opinion

`dashboard/finance/report_verdict.py` defines `IReportVerdictSource`.
`AuditorReportVerdictSource` runs `rol_finances`'
`audit_statement_reports.py` against a report and its source PDF and caches the
verdict against the fingerprint of `report.html` plus every sibling `*.pdf`, so
a report is re-audited exactly when one of its inputs changes.
`NullReportVerdictSource` is the no-opinion implementation the tests wire in
(autouse fixture in `dashboard/tests/conftest.py`).

`_classify_report_status` takes the **worse** of the badge and the verdict. The
auditor can turn a self-declared PASS red; it can never promote a report its own
author flagged.

**Auditor WARN maps to no opinion, not to yellow.** WARN means "could not
confirm". Mapping it to `review` turned 13 good tabs amber in one pass and would
have buried the six carrying real defects. Do not "fix" this.

A one-shot startup task warms all report verdicts (~5s, ~49 reports) so the
first page load is not the slow one. It runs once and exits — not a poll loop.

### rol_finances — three checks anchor a report to its own PDF

- `report_source_consistency.py` — account number, balances and daily balances a
  report claims must appear in the PDF beside it. Runs for **every** report
  shape, not just the ones with a parser.
- `audit_statement_reports.py` — Fifth Third prints the same header block on
  check-image packets as on statements, so the ledger audit now gates on the
  **Account Summary table**. That cleared a false FAIL on
  `january/check_images/fifth_third_personal_images`.
- `transaction_visibility.py` — `StatementDepositVisibilityPolicy` drops deposit
  rows from Verified Transactions by **(date, amount)** taken from the
  statement's own extracted deposits, never by wording: "DEPOSIT" is obvious,
  "EARLY PAY: SSA TREAS 310 XXSOC SEC" is not. A row whose date or amount cannot
  be read is **kept** — dropping an unidentifiable row would hide a real expense.
  Running `restructure_verified_transactions.py` over a report is the fix for a
  stray deposit row; no regeneration needed.

### The JetBlue rebuild

`tools/python_tasks/verification_lib/jetblue_statement_report.py`:

```bash
cd /home/adamsl/rol_finances
PYTHONPATH=. .venv/bin/python tools/python_tasks/verification_lib/jetblue_statement_report.py \
  --pdf <dir>/<statement>.pdf --title "Barclays 3965 (JetBlue Business Mastercard) — Statement Closing <Month D, YYYY>"
```

It refuses to write a report when the balance summary does not reconcile
(previous − payments − credits + purchases + cash advances + other charges +
finance charges = current balance), when a printed table's rows disagree with
the total the summary claims, or when a transaction matches zero or several live
expense records. 13 tests in `test_jetblue_statement_report.py`.

Card-statement rules that are easy to get wrong again:

- **No checks, no deposits, no daily balance table.** The auditor FAILs a
  JetBlue report carrying `<h2>Checks</h2>`, `Deposits / Credits`,
  `MyAdvance Summary` or `Real Life Rewards Summary`. Payments get their own
  `Payment Summary` section — the auditor looks for that exact phrase.
- **A refund is a credit, not a negative expense.** Refunds print inside
  PURCHASES/OTHER DEBITS with a minus sign. They belong in `Credits and Refunds`
  as positive credits, and `-0.54` / `-0.45` must not appear anywhere in the
  HTML **including the JSON block**.
- Transaction dates print `MM-DD` with no year; the year comes from the
  Statement Closing Date (a month later than the closing month is the previous
  year).
- Finance charges are billed as a lump on the closing date, not as a transaction
  row, so the builder synthesises one expense row for them.
- Vendor keys are recovered from `expenses.id_light` by stripping the row's own
  `_MM_DD_YY_dollars_cents` suffix — that keeps reports on the vendor keys the
  database already uses instead of inventing parallel slugs.
- Titles say **Barclays**, not JetBlue. Mazda's own notes set that convention
  for this card.

### EG's duplicate-expense decision (2026-09-05)

Deleted the older hand-written rows **#484, #534, #561, #580**; kept the newer
machine re-imports **#2300, #2286, #1519, #1159**.

`fk_receipt_metadata_expense` is `ON DELETE CASCADE`, so before deleting,
receipt_metadata id 39 (the Valvoline itemization) was re-pointed from #534 to
#2286 — otherwise the delete would have destroyed a real scanned receipt.
Receipt 66 on #561 was a second scan of the same Mr Burger slip already attached
to survivor #1519, so it was allowed to cascade.

Backups: `rol_finances/backups/jetblue_duplicate_expenses_20260905.json` and
`..._receipt_metadata_20260905.json`.

**Category side effect, already reported to EG:** the survivors carry their own
categories, so 2025-02-11 Valvoline moved 166 → 160 (Travel & Transportation)
and 2025-01-21 gas moved 160 → 375 (BP Gas). EG has not asked to change them.

### Mazda and the Trainer

Both blocks swapped via create + detach/attach (`mazda_block_edit_method` — the
memfs projection is broken on this box):

- `system/report_html_contract` → `block-be84e3ac-ed9f-4b94-821f-ad01cd5567d9`
- `system/barclay_3965_annual_summary_parsing_notes` → `block-3d4bb6b7-5fee-457d-b5cc-f764b82d6922`

Verify a block edit with **GET** `/v1/agents/<id>/context` and grep the compiled
context. `POST /v1/agents/<id>/context` returns Method Not Allowed and looks
like a failed recompile.

Mazda was messaged the correction and answered correctly in her own words.
Trainer prompt assembles at 102,518 chars.

## State at end of shift

- Auditor sweep: **19 PASS**, 2 FAIL.
- Dashboard: 3,233 pass, 2 skipped, **1 failed** —
  `tests/test_model_stats_assignments.py` `TypeError` at
  `model_stats/assignments.py:119`. **Pre-existing, not from this work.**
- rol_finances verification lib: 60 pass
  (`--ignore=.../test_transfer_pay_reconciler.py`, whose collection error is
  also pre-existing).
- Live dashboard restarted; no red tabs.

## Follow-up — reusable receipt matching (2026-09-05)

`rol_finances` commits `db222bf` and `a853932` added and applied
`tools/python_tasks/verification_lib/audit_report_receipt_matches.py`. It checks every
Verified Transactions row in any supplied `report.html` using exact absolute amount
and an inclusive five-day receipt-filename date window. The default is read-only;
`--apply` writes only confident matches to both `expenses.receipt_url` and the exact
report row's `has-receipt` / `data-receipt-url`. Ambiguous matches remain `review`.

Applied to `january/fnbo_4851_year_2025/report.html`: 153 rows checked, 7 matched,
0 review, 146 unmatched. All seven were same-day matches. The report now has seven red
receipt tags and seven working View Receipt actions; the dashboard supporting-document
endpoint and a direct receipt URL both verified successfully. Focused tests: 15 passed.

Mazda's live `system/report_html_contract` and the Trainer instructions now require this
guarded receipt-reconciliation step after restructuring/category hydration. The new live
block is `block-be84e3ac-ed9f-4b94-821f-ad01cd5567d9`; the first recompile was stale, and
the required second recompile plus `GET /context` both showed the new command.

Reusable command:

```bash
cd /home/adamsl/rol_finances
.venv/bin/python3 tools/python_tasks/verification_lib/audit_report_receipt_matches.py \
  <path-to-report.html> --days 5 --apply
```

## Open — EG's call, do not guess

1. **`february/` directory names for this card are shifted by one statement.**
   `february/jet_blue__december_january_12_26_25_to_01_23_25/` holds
   `jet_blue_january_february.pdf` (closing **February 26, 2025** — the *same*
   statement as the january/ report just rebuilt), and
   `february/jet_blue_january_february_01_27_to_02_25_25/` holds
   `jet_blue_february_march.pdf` (closing **March 26, 2025**). One statement is
   covered twice under contradictory names. Renaming affects tabs. Asked, not
   answered.
2. **Neither rebuilt report is a dashboard tab.** `finance/report_registry.py`
   carries only `barclay-3965-year`. The two monthlies were pulled 2026-08-27
   while contaminated and never restored. Asked, not answered.
3. **Two remaining auditor FAILs** — `2026/prime_chase_card_january_2026`
   (`<title>Report</title>`) and root-level `fifth_third_non_profit_3119`
   (`<title>PDF description</title>`, body "This is just an automatic transfer
   amount"). Both look like one-line note pages the auditor reads as unfinished
   reports; neither is wired to a tab. Their `january/` and `february/`
   siblings both PASS. Left alone deliberately.
4. Unrelated leftovers: 28 reports still have no JSON block; 17 of 34 rows in
   the rebuilt January 6285 report are still Uncategorized.

## Do not

- Do not branch. Everything lands on `origin/main`.
- Do not `git stash` in `rol_finances` or this tree — live agents write here.
  Run `git status` before assuming the tree is clean, and stage only your own
  files (other agents' work was interleaved during this shift).
- Do not write agent memory through raw `POST`/`PATCH /v1/blocks` as a general
  habit; the create + detach/attach path above is the approved exception on this
  box.
