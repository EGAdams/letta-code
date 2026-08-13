# Trainer Report — Window Scanner (Right to Life Category Correction)

**Document:** Right to Life of Michigan Educational Fund — 2025 year-end giving statement, 10 contributions, $247.70
**Scanner:** Window
**Dispatch time:** 2026-07-29T13:02:35Z (this is a retrospective category-correction run over an already-completed, already-once-corrected intake)
**Mazda conversation:** conv-4c7381e7-68d4-4462-b3a0-7a67c20be2d3
**Verdict: PASS (CORRECTED)**

## Context

This intake had already gone through two prior corrective passes (traces 280→281→282, all judged PASS) handling a duplicate-child-itemization defect, graded by an earlier Trainer report for the same dispatch (`20260729-130235_Window_Scanner_d1785330155.md`). That earlier report incorrectly marked `check_vendor_key` and the resulting category assignment (357/Licensing) as PASS. This run's task was specifically to fix that missed defect: EG reviewed the stored expenses and rejected the category.

## Root cause (confirmed directly from the transcript)

- `classify_scan.py` correctly identified the merchant: "Right to Life of Michigan Educational Fund", confidence 0.95.
- `check_vendor_key` was called with `vendor_key="right_to_life_of_michigan_educational_fund"` and returned a **fuzzy-match normalization to `michigan_corporations_division`** — an unrelated State-of-Michigan corporate-filing vendor — with no plausibility check against the merchant name.
- `categorizer_main.py` faithfully mapped that wrong vendor_key to `category_id=357` (Licensing → Information Technology & Software).
- Every downstream row inherited the wrong category: parent 1684 (correctly NULL as an itemization anchor), all 10 itemized children 1685–1694, and pre-existing standalone expense 1660.

## Corrective action verified

Sent one coaching message identifying the root cause and requiring: per-expense `update_expense_category.py --category-id=218` calls, a DB readback to prove persistence, a fresh trace/judge, a `propose_improvement`, and a re-sent dashboard callback.

Mazda executed all of it, with successful tool returns for every step (verified in the transcript, not just her prose):

| expense_id | before | after | evidence |
|---|---|---|---|
| 1660 | 357 (Licensing) | **218 (Right to Life)** | `update_expense_category.py` success return + DB readback |
| 1685–1694 (10 line items) | 357 | **218** | same, each individually |
| 1684 (itemization parent) | NULL | NULL (untouched, correct) | DB readback |
| 477 (pre-existing, already correct bucket) | 190 (Gifts & Love Offerings) | 190 (untouched, per instruction — sharpening was optional) | DB readback |

A `pymysql` readback she ran herself (13:29:39) independently confirms the post-state of all 13 rows — this is database evidence, not narrative.

Follow-through:
- `record_trace` → `trace_id=283` (task_name=`document-intake`)
- `judge_trace(283)` → **PASS**
- `propose_improvement` → `proposal_id=197`, `failure_type=wrong_category`, correctly describing the vendor_key-plausibility gap (recommends rejecting/flagging a normalized vendor_key whose plain meaning has no relation to the classifier's merchant text, rather than silently accepting it into categorization)
- Dashboard `/api/expense-stored` callback re-sent, HTTP-level success (`{"ok": true}`)

One minor cosmetic note, not a defect: Mazda pointed out the callback payload's `vendor_key` field still literally reads `michigan_corporations_division` (the callback schema carries no per-expense category field to update) — correct observation, no action needed since the category fix lives in the DB, not the callback.

## Still open (carried over, not this run's scope)

Per the dispatch's `also_still_open_from_the_previous_trainer_report`: children **1692 ($24.00)** and **1694 ($25.00)** are still live LINE_ITEM rows duplicating pre-existing standalone expenses 1660 and 477, overstating totals by **$49.00**. This is a known finance-tooling gap (no safe merge/void path for an already-itemized child) that Mazda flagged and proposed for twice already (proposals 195/196) — it needs a developer-built reconciliation tool, not another agent coaching pass. Restating here so it isn't lost.

## Human follow-up needed

- Build a safe tool/repository path to void or merge a duplicate itemized LINE_ITEM child without breaking parent/child integrity, so the $49.00 overstatement above can be resolved.
- Consider whether `check_vendor_key`'s fuzzy-matcher should itself refuse a normalization whose result has zero token overlap with the input, rather than relying on downstream agent judgment.
