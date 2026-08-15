# Trainer Report — Window Scanner (Menninga Full Invoice Correction)

**Document:** `window_scan_1785371446360842781_63f9da45e563.jpg` (Jacob Menninga invoice INJTM2502, 2025-02-28)
**Dispatch:** 2026-07-30T00:30:50Z (retrospective correction of trace 288 / expense 1696)
**Conversation:** conv-a3921f6e-0fee-4828-9880-22703e4441a9
**Verdict: FAIL (overall) — Mazda intake CORRECTED; dashboard red-box gate FAIL**

## Timeline

### Round 1 — initial run (00:30:50–00:32:43): FAIL
Mazda ran `load_wrapper_revision` → `classify_scan.py` (receipt, 0.95) → `parse_and_categorize.py --json` →
`check_vendor_key` → `check_duplicates` → `categorizer_main.py` (category 197) →
`parse_and_categorize.py --save` → `itemize_existing_expense` → `record_trace`(288) →
`judge_trace`(288)=**PASS** → dashboard callback.

**Defect:** the dispatch was an explicit retrospective correction stating the ground truth
(`expense_scope=full_receipt`, total $51.25, calculator-tape arithmetic 17.75+14.50+19.00=51.25).
Mazda instead re-ran the vision parser, which again returned `expense_scope="marked_items"` with
**no** `handwritten_arithmetic_total` field — the 2026-07-29 parser fix the dispatch cited did not
manifest in this call's output. Mazda trusted that stale field over the dispatch's ground truth and
her own parse JSON (which already showed `totals.subtotal=51.25` and `totals.total_amount=51.25`,
exactly matching the sum of the three line items). She re-stored expense 1696 at $19.00 (unchanged),
and `itemize_existing_expense` correctly refused (`"line items total 51.25, charge is 19.00"`) — but
per the Trainer contract that refusal is a symptom of the wrong scope, not a valid fail-closed
outcome, on a document whose own arithmetic reconciles to the full total. `judge_trace` PASSed a run
that left the invoice mis-scoped exactly as it was before this dispatch.

### Round 2 — coaching message 1 (00:33): parent/child correction
Sent a corrective message requiring Mazda to: recognize her own parse output's totals as authoritative
evidence overriding the stale `marked_items` field; correct expense 1696 **in place** to the $51.25
parent; itemize into three children with their own line dates (2025-02-12/17.75, 2025-02-20/14.50,
2025-02-26/19.00); re-trace/judge/callback; and file a `propose_improvement`.

**Result (trace 289, judged PASS at 00:50:35):** Mazda hand-updated expense 1696's amount to 51.25 via
a raw `ExpenseRepository.update()` call (not a sanctioned tool — no such tool exists for this field),
then successfully called `itemize_existing_expense`, which correctly reconciled and created children
1697/1698/1699 with category_id=197 each and set the **parent's category_id to NULL** (verified by her
own SELECT). She then patched the children's inherited parent-date bug with another raw
`ExpenseRepository.update()` (acceptable — no tool covers per-line-item dates) — but also ran a third
raw update that **reset the parent's category_id back to 197**, directly violating the contract that
parent/anchor rows must stay `category_id=NULL` and never count in category totals. She filed
`propose_improvement` (proposal 203) for the scope-detection defect and a memory-note proposal (202,
recorded but not live-applied — no memory applier wired).

### Round 3 — coaching message 2 (00:52): parent category_id defect
Sent a second corrective message identifying the category_id=197 regression on parent 1696, requiring
it be reverted to NULL, and cautioning against raw ORM writes as a default correction method
(pointing her to the existing `update_expense_category.py` CLI she had already found via grep but
didn't use for round 2).

**Result (trace 291, judged PASS at 00:54:46):** Mazda checked `update_expense_category.py` and found
it only supports setting a positive category id, not clearing to NULL — she disclosed this and used a
minimal direct `UPDATE expenses SET category_id = NULL WHERE id = 1696`, then verified with a
read-only SELECT:
- `1696.category_id = NULL` ✓ (parent)
- `1697.category_id = 197`, `1698.category_id = 197`, `1699.category_id = 197` ✓ (children)

Re-ran `record_trace`(291) → `judge_trace`(291) = **PASS** → re-sent
`POST /api/expense-stored` with `expense_ids=[1696,1697,1698,1699]`, `duplicate_expense_ids=[]`.

## Final state (verified)
| id | role | amount | date | category | description |
|---|---|---|---|---|---|
| 1696 | PARENT | 51.25 | 2025-02-28 | NULL | Jacob Menninga (anchor) |
| 1697 | LINE_ITEM | 17.75 | 2025-02-12 | 197 | Cliff's sermon on Who We Are in Christ |
| 1698 | LINE_ITEM | 14.50 | 2025-02-20 | 197 | Rosemary's 1/18 sermon on gossip |
| 1699 | LINE_ITEM | 19.00 | 2025-02-26 | 197 | Karen Cook's sermon on turning to the Lord |

`itemization_reconciled=true`, `itemization_parent_id=1696`, `itemization_child_ids=[1697,1698,1699]`.
Trace 291 / judge PASS is the authoritative final record; traces 288 and 289 are superseded.

## Wrapper defects to fix (for the improvement loop / rol_finances maintainers)
1. **Parser/vision scope detection is not reliable.** The 2026-07-29 fix (commits 226452a, df25bdd)
   did not cause this exact image to return `expense_scope=full_receipt` or populate
   `handwritten_arithmetic_total` on re-parse — it still returned `marked_items`/19.00. Mazda's own
   proposal 203 targets this; recommend also directly re-testing this specific image against the fixed
   parser to confirm whether the fix regressed or never covered this arithmetic layout (a
   calculator-tape sum rather than an inline handwritten total).
2. **No sanctioned tool exists to clear an expense's `category_id` to NULL** (needed for parent/anchor
   rows) or to set a per-line-item `expense_date` on itemization. Both gaps forced Mazda into raw
   `ExpenseRepository`/direct-SQL writes this run. These are legitimate tool gaps, not misconduct, but
   should get real tools (`update_expense_category.py --clear`, and an `item_dates` param on
   `itemize_existing_expense`) so future corrections don't need raw DB access at all.
3. Mazda's first attempt to fix the parent amount also used a raw ORM write where none was strictly
   needed only because no "update stored expense amount" tool exists either — same gap as above.

## Lessons sent to Mazda (recorded in this conversation; memory-note proposal 202 pending a live applier)
- Verify a retrospective-correction dispatch's ground truth against her own tool output (parsed
  line-total/printed-total arithmetic) rather than trusting a stale `expense_scope` field.
- Reserve raw ORM/SQL writes for fields no sanctioned tool covers; do not use them to override a
  correct value a sanctioned tool (here, `itemize_existing_expense`) already produced.
- Parent/anchor expense rows must keep `category_id=NULL` — never restore a category onto them.

## Human follow-up
- Confirm the parser fix cited in the dispatch is actually deployed/effective for calculator-tape-style
  arithmetic layouts (round 1 evidence suggests it is not, for this image).
- Consider adding the two missing tools noted above so corrections don't require direct DB writes.
- Memory-note proposal 202 needs a live applier wired before durable lessons persist across runs.

## Deterministic red-box gate — FAIL

Mazda intake contract: **CORRECTED**. Dashboard annotation verification: **FAIL**.

- expense `1696`, receipt: No high-confidence expense row was found in the image.

Do not coach Mazda, re-store the expense, or edit finance data for this failure. The red box is produced by `dashboard/document_annotation.py`; this is a dashboard defect.
