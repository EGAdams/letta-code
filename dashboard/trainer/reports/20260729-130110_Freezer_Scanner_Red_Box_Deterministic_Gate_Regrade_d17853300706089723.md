# Trainer Report — Freezer Scanner (Red Box Deterministic Gate Regrade)

**Document:** `scan_freezer_1785330063408672399_e4e29af60f85.jpg`
**Dispatch:** 2026-07-29T13:01:10.608Z (unix 1785330070.6089723)
**Conversation:** `conv-d6423b25-796b-4359-a5c7-18130a2cee89`
**Verdict: FAIL (intake) / FAIL (red-box gate — dashboard defect, not Mazda's)**

## Document identity

Classified `receipt`, confidence 0.99. Handwritten "love offering" note from Jacob Menninga,
$67.25 total, itemized into 5 video-editing service line items (audio/video editing for
Rosemary/Joshua's sermons), reconciling exactly to the charge.

## Step-by-step checklist (evidence from transcript, all timestamps > dispatch)

1. `load_wrapper_revision` → wrap-v062. ✅
2. `classify_scan.py` → `doc_type=receipt`, confidence 0.99 (paid-invoice detection routed to
   receipt). ✅
3. STEP 0 parse: `parse_and_categorize.py --json` → merchant, date 2025-03-31, amount 67.25,
   5 items, `expense_scope=full_receipt` (no marked-item selection applicable — full document is
   one continuous handwritten note, not a printed table with circled items). ✅
4. `check_vendor_key` → `jacob_menninga`, recognized. ✅
5. `check_duplicates` → not a duplicate. ✅ **(see anomaly below — malformed argument)**
6. Categorization → `categorizer_main.py` via `executor_run` → `category_id=197`. ✅
7. Store → `parse_and_categorize.py --save --category-id=197` → `success:true, expense_id=1678,
   parse_artifact_verified:true`. ✅
8. Itemization → `itemize_existing_expense` → 5 line items reconcile exactly (`difference:0.00`),
   parent 1678, children 1679–1683, all category 197. ✅
9. `record_trace` (task_name=`document-intake`, matches contract fields) → trace_id 279. ✅
10. `judge_trace(279)` → **PASS**, "all deterministic intake checks passed". ✅
11. Dashboard callback `POST /api/expense-stored` with expense_id/expense_ids/vendor_key/etc. ✅

Every contractual step present with a successful tool return. Category, vendor key, and
itemization all correct and reconciled. **Mazda's intake work for this document is correct —
PASS stands.**

## Anomaly observed (not judged as a failure, flagged for visibility)

The `check_duplicates` tool call's `description` argument contained garbled/injected-looking
text appended after the real description ("Jacob Menninga'}【...multi-language garbage including
apparent leaked planning tokens/gambling-spam strings and a stray `to=functions.executor_run`
fragment】"). The tool still executed correctly and returned a valid duplicate-check result, so
this did not affect intake correctness this run, but it looks like raw model
reasoning/tool-routing tokens leaking into a structured tool argument on the cheap mini model.
Worth watching for recurrence; not actionable as a wrapper fix from a single occurrence.

## THE RED BOX GATE — this run's actual purpose, and it is FAILING

Per the contract, I fetched `/supporting-document/<id>/receipt` for the parent and all 5
itemized children, repeated across several points in time (13:21, 13:25, 14:33, 15:51, 16:18,
16:45–16:47) to test determinism, and diffed served bytes against the original file on disk:

| Expense | Role | Result (consistent across all checks) |
|---|---|---|
| 1678 | parent | **NEVER boxed** — every attempt (5+, spanning 13:21→16:47) served the raw unannotated original. Annotator reason: `No high-confidence expense row was found in the image.` |
| 1680 | child ($4.50, Joshua's 3/8 sermon) | **NEVER boxed** — every attempt (13:25, 14:33, 16:46) failed identically. Same reason. |
| 1679, 1681, 1682, 1683 | children | **Nondeterministic** — at 13:21–14:33 all four consistently failed to box (`opened without highlight`, same reason). By 16:18–16:47, repeated fetches of the *same* expense IDs returned genuinely different (annotated) bytes. Cache directory shows two different cache-key files generated for 1681 and for 1683 at different timestamps, confirming the annotator was re-run and produced a different result for an unchanged source image and unchanged expense record. |

This is a real dashboard/annotator defect, not a Mazda failure — per the contract I am not to
coach her to "fix" it or suggest re-storing/editing the expense. Filing as a defect:

- **The gate is not deterministic.** The same `(expense_id, source image)` pair produces
  different highlight outcomes on repeated opens. This contradicts the expectation that the
  annotated copy is a stable, cached artifact.
- **The parent expense (1678) and one child (1680) can never be boxed at all** on this
  document — this is a genuinely hard case: the source is a *handwritten, continuous
  itemized note* (not a printed receipt table with discrete rows), so the row-matching
  heuristic in `dashboard/document_annotation.py`'s image/OCR strategy has nothing structured
  to latch onto for the parent's full-document view or for item 1680's short line
  ("Attempt to edit Joshua's 3/8 sermon...", $4.50 — likely too little distinguishing text
  matched with high confidence).
- Every unboxed row, for the record: 1678 ($67.25, 2025-03-31, full receipt); 1680 ($4.50,
  2025-03-31, "Attempt to edit Joshua's 3/8 sermon, but I only had the edited audio...").

## Coaching sent to Mazda

None. All required intake work was completed correctly and evidenced; the red-box gap is
outside her contract (dashboard-side annotation), and the instructions explicitly forbid
coaching her to work around it.

## For a human to look at

The nondeterminism in `document_annotation.py`'s annotation result for the same expense/image
pair (1679, 1681, 1682, 1683 flipped between unboxed and boxed across repeated opens with no
change to the underlying data) is worth investigating — possibly a non-seeded vision/LLM call
in the row-matching path, or a race in the annotation cache. Separately, the parent view and
item 1680 may simply be an inherent limit of OCR/row-matching against continuous handwriting
with no tabular structure — expected to need a different (e.g. full-page) fallback for such
documents rather than a fix to Mazda's wrapper.

## Deterministic red-box gate — FAIL

Mazda intake contract: **PASS**. Dashboard annotation verification: **FAIL**.

- expense `1678`, receipt: No high-confidence expense row was found in the image.
- expense `1680`, receipt: No high-confidence expense row was found in the image.

Do not coach Mazda, re-store the expense, or edit finance data for this failure. The red box is produced by `dashboard/document_annotation.py`; this is a dashboard defect.
