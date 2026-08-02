# Trainer Report — Freezer Scanner (Expense 1680 / $18.00 — Final Red Box Regrade)

- **Scanner:** Freezer Scanner
- **Document:** `scan_freezer_1785330063408672399_e4e29af60f85.jpg` (handwritten "love offering" labor invoice, Jacob Menninga)
- **Dispatch:** 2026-07-29T13:01:10.608Z
- **Conversation:** `conv-d6423b25-796b-4359-a5c7-18130a2cee89`
**Verdict: FAIL (overall) — Mazda intake PASS; dashboard red-box gate FAIL**

## Focus of this regrade

This run's earlier grading already covered the intake pipeline (classify → parse → invest­igate →
categorize → store → itemize → trace → judge → callback) and it is unchanged/still correct — see
checklist below. This regrade's specific task was to verify the **red-box annotation** for the
itemized child **expense 1680 ($18.00)**, per the Trainer contract's "the red box is part of the
contract too" clause.

## Step-by-step checklist (intake)

| Step | Evidence | Result |
|---|---|---|
| `load_wrapper_revision` | returned `wrap-v062`, instructions applied | OK |
| STEP 0 classify | `classify_scan.py` → `doc_type=receipt, confidence=0.99`, reason: paid ("love offering" note, date 4-8-25, circled total $67.25) | OK |
| STEP 0 parse | `parse_and_categorize.py --json` → merchant `Jacob Menninga`, date `2025-03-31`, total `67.25`, 5 line items | OK |
| STEP 2a `check_vendor_key` | `vendor_key=jacob_menninga`, recognized=true | OK |
| STEP 2b `check_duplicates` | `is_exact_duplicate=false`, `in_database=false` | OK |
| STEP 3 categorize | `categorizer_main.py --provider=auto` → `category_id=197` (Gemini) | OK |
| STEP 4 store | `parse_and_categorize.py --save --category-id=197` → `expense_id=1678` (parent) | OK — minor non-blocking warning: "Could not update source_file" (receipt file was subsequently moved into the year-folder archive; recorded truthfully in `problems`) |
| STEP 4B itemize | `itemize_existing_expense` → `itemized=true`, reconciled exactly (5 lines sum to $67.25), parent `1678`, children `1679,1680,1681,1682,1683` | OK |
| STEP 5 `record_trace` | `task_name="document-intake"`, full evidence JSON incl. itemization fields | OK |
| STEP 6 `judge_trace` | trace `279` → **PASS**, `failure_type=none` | OK |
| STEP 8 dashboard callback | `POST /api/expense-stored` with `expense_id=1678`, `expense_ids=[1678]`, `stored=1` | OK (`{"ok": true}`) |

Mazda's agentic work for this document is complete and correct. No coaching was sent.

## Red-box verification (all graded rows: parent + 5 children)

Fetched `/supporting-document/<id>/receipt` for every id in the itemization set and compared served
bytes against the raw source file
(`readable_documents/receipts/2025/march/march_31/jacob_menninga_03_31_25_67_25.jpg`, md5
`1fcf21e5aaff6c96ac1cef7e2360c0c8`):

| Expense | Line item (line_total) | Served bytes | Boxed? |
|---|---|---|---|
| 1678 (parent) | full receipt ($67.25) | identical to raw | **NO — unboxed** |
| 1679 | "…2/15 sermon on a changed life…" ($19.50) | differs from raw | boxed |
| **1680** | **"…students and Rosemary's messages on Love Not the World…" ($18.00)** | **identical to raw** | **NO — unboxed** |
| 1681 | "…sermon on the golden rule" ($9.75) | differs from raw | boxed |
| 1682 | "…Joshua's 3/8 sermon…" ($4.50) | differs from raw | boxed |
| 1683 | "…3/5 sermon on speaking the truth in love." ($15.50) | differs from raw | boxed |

Dashboard server log confirms the annotator's own verdict for the unboxed rows:
```
[supporting-document] opened without highlight expense_id=1680 type=receipt reason=No high-confidence expense row was found in the image.
[supporting-document] opened without highlight expense_id=1678 type=receipt reason=No high-confidence expense row was found in the image.
```

**This is confirmed a dashboard defect, not a Mazda failure.** Per the Trainer instructions, a
missing box is `document_annotation.py`'s job to draw, and Mazda's parse/store evidence (STEP 0
artifact, itemization payload) is accurate and unchanged from prior grading. Item 1680's line
description ("Edited and uploaded the students and Rosemary's messages on Love Not the World and
Loving the Family of God") is long, narrative, and near-duplicates the wording pattern of items
1679/1683 (also "Edited and uploaded Rosemary's … sermon on …") — a plausible reason the OCR/line
scorer fails to isolate a single high-confidence matching row on this handwritten, prose-style
invoice. No action was taken to "fix" this by re-storing or editing the expense, per instructions.

## What a human should look at

`dashboard/document_annotation.py`'s receipt-image line matcher fails to box the row for expense
**1678 (parent/full-receipt)** and **1680 ($18.00 item)** on this document, while succeeding for the
other four sibling rows on the same image. Worth investigating whether the matcher's identity
scoring needs a similar-wording tiebreak (per CLAUDE.md's existing note about repeated/near-duplicate
OCR text) for narrative, non-tabular invoices like this one, distinct from the already-documented
"pen crosses the amount column" statement case.

## Summary

Mazda's intake of this Jacob Menninga love-offering invoice (parent expense 1678, itemized into
children 1679–1683) is complete and correct — PASS, no coaching needed. This regrade's specific
target, expense 1680 ($18.00), together with parent 1678, are confirmed **not boxed** when viewed
via **View Receipt**, while the other three siblings are boxed correctly; this is a dashboard
annotation-matcher defect on this narrative-style handwritten invoice, filed here for a human to
investigate, not something Mazda can or should fix.

## Deterministic red-box gate — FAIL

Mazda intake contract: **PASS**. Dashboard annotation verification: **FAIL**.

- expense `1678`, receipt: No high-confidence expense row was found in the image.
- expense `1680`, receipt: No high-confidence expense row was found in the image.

Do not coach Mazda, re-store the expense, or edit finance data for this failure. The red box is produced by `dashboard/document_annotation.py`; this is a dashboard defect.
