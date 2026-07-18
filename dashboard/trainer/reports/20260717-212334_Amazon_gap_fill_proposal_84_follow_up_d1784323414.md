# Trainer Report — Amazon gap-fill (proposal 84 follow-up)

- **Scanner/source:** targeted retry of 2 previously-failed rows from a Chase Jan-2025 statement (`scan_freezer_1784320482902525344_26483feabb19.jpg`), not a fresh document (facade note confirms).
- **Dispatch time:** 2026-07-17T21:23:34Z
- **Conversation:** `conv-bb1567fa-db88-4110-944c-3865b5d00dd6`
- **Verdict: FAIL** (correctly fail-closed; real blocker is a vendor-mapping data gap, not a Mazda process failure)

## What Mazda was asked to do
Resolve and store 2 Amazon rows (2025-01-04 $60.00, 2025-01-10 $1.99) that failed
`store_statement_transactions.py`'s vendor resolution in a prior run (trace 106), using a
newly-added `lookup_amazon_order.py` tool, then record_trace + judge_trace + dashboard notify.

## Step-by-step

| Step | Evidence | Result |
|---|---|---|
| `load_wrapper_revision` | tool_return 21:23:59 | ✅ |
| `check_vendor_key` (both rows) | tool_returns 21:24:07 / 21:24:11 | ✅ ran, but **fuzzy-matched both rows to unrelated vendors** (`apple_com_bill_866_712_7753_ca`, `audible_hu62h8tj3_amzn_com_bill_nj`) — a real quality bug in that matcher, see below |
| Lookup tool (attempt 1) | `run_claude_code_sdk` return 21:25:24: "file not found" | ❌ **wrong executor** — routed to the Win10 `frita-executor` container, a separate machine from where `rol_finances` lives; dispatch explicitly said `executor_run` |
| `check_category`, `check_duplicates` (both rows) | tool_returns 21:25:29–21:25:46 | ✅ ran; category null (expected — blocked on vendor), not duplicates |
| Mazda stops, asks for guidance | assistant_message 21:25:55 | ❌ stopped without record_trace/judge_trace/dashboard notify (a "no-store" outcome still requires these per contract) |
| **Coaching #1** — do the always-fire steps even on no-store | | Mazda ran `record_trace` (trace 107), `judge_trace` (FAIL/unsupported_document), `propose_improvement` (proposal 85 — premise: tool undeployed), and posted `/api/expense-stored` (stored=0) — all correctly executed, but proposal 85's stated root cause was wrong |
| **Coaching #2** — correct the false premise: use `executor_run`, not `run_claude_code_sdk`, for `rol_finances` scripts | | Mazda re-ran the lookup via `executor_run` successfully (real itemized results: dress/mascara/Roku remote, order_total $85.00 vs $60.00 charge — confirmed split shipment; row 2 correctly not-found), and filed proposal 86 correcting 85's misdiagnosis. Good self-correction. |
| **Coaching #3** — store both rows now with category_id=143 and corrected vendor identity | | Mazda attempted the real store path (`store_statement_transactions.py`), which failed both rows with `ValueError: no category mapping for statement vendor ...` — **`VendorCategoryStore.resolve_vendor_key()` has no entry at all for either Amazon description pattern**, a genuine, distinct gap from the `check_vendor_key` tool's (wrong) fuzzy match. Mazda correctly refused to hand-inject category_id=143 without a real vendor_key mapping and stopped, reporting the exact blocker. |

## Wrapper defects found (for the self-improvement loop)

1. **(Real, actionable) Vendor mapping gap:** `VendorCategoryStore.resolve_vendor_key()` (used by the actual store path) has no pattern matching `AMAZON MKTPL*...Amzn.com/bill` or `AMZN Digital*...`. Until a real mapping entry is added (vendor_category.yaml or equivalent), any Amazon marketplace/digital charge with this description shape will keep failing closed. **Mazda did not file a proposal for this specific gap** (only for the earlier routing misdiagnosis) — a human or the next run should file/verify a proposal targeting `resolve_vendor_key`.
2. **(Real, lower severity) `check_vendor_key`'s fuzzy matcher is too permissive** — it confidently resolved both Amazon rows to unrelated vendors (Apple, Audible) with `recognized: true`. This is a false positive that could have led to mis-categorization if the stricter store-path resolver hadn't independently rejected it. Worth tightening the fuzzy-match threshold or adding a confidence field investigators can gate on.
3. **(Process, self-corrected) Executor routing** — Mazda initially used `run_claude_code_sdk` (routes to the Win10 container) for a `rol_finances` script despite the dispatch explicitly specifying `executor_run` (this box). She fixed this only after coaching; the dispatch instruction should probably be even more explicit/impossible-to-miss for cases like this, or `run_claude_code_sdk` should fail fast with a clear "wrong executor for this filesystem" message instead of a generic file-not-found.

## Coaching sent
Three corrective messages (maximum allowed), each addressing a distinct defect:
1. Perform the always-fire record_trace/judge_trace/dashboard-notify steps even on a no-store outcome.
2. Correct the false "tool missing" premise — use `executor_run`, not `run_claude_code_sdk`, for `rol_finances` scripts.
3. Attempt the actual store with corrected vendor/category info — this is what surfaced the real, final blocker (vendor mapping gap).

## Final state
- Trace 107 (FAIL) + proposals 85 (superseded) and 86 (routing correction) are recorded.
- `/api/expense-stored` reflects `stored: 0` — still accurate; both rows remain unstored.
- Neither row was stored, and none is a duplicate. The document is correctly left in a "needs data-mapping fix" state rather than mis-categorized.

## For a human
- Add vendor_key mapping entries for `AMAZON MKTPL*...Amzn.com/bill` and `AMZN Digital*...` so the store path can resolve them (recommend mapping both to the Amazon category, id 143, matching what `check_category`'s `expected_category_id` already suggested).
- Once mapped, this document's 2 rows can be re-dispatched to Mazda to complete storage.
- Consider a proposal/rubric update flagging that `check_vendor_key`'s fuzzy resolution and the real store path's resolver can disagree — Mazda should treat a `check_vendor_key` fuzzy match as provisional until the store path confirms it.
