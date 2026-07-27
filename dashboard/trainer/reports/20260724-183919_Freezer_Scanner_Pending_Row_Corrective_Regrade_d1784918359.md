# Trainer Report — Freezer Scanner Pending-Row Corrective Regrade

- **Document:** `scan_freezer_1784918356348439942_f87d54710753.jpg` (Fifth Third Bank statement, account …6285)
- **Original dispatch:** 2026-07-24T18:39:19Z (trace 183)
- **This regrade:** 2026-07-26 (this Trainer session)
- **Conversation:** `conv-3033e7e3-9b90-4e64-963f-593739c6d3e8`
- **Verdict: CORRECTED** (substantive defect fixed and re-recorded; one residual judge-calibration issue correctly identified and escalated, not self-fixable by Mazda)

## Context

This conversation already contains two earlier, unrelated Trainer regrades of trace 183 (both about
report-generation *mechanics* — tool path errors, and whether a report is required on quarantine —
both correctly resolved, no rework needed there). **This regrade is about a different, substantive
defect**: the original quarantine decision itself was wrong.

The dispatch's deterministic facade (`corrective_regrade_required: true`) established that:
- 4 of the 10 originally-quarantined rows were visibly labeled **Pending** — they should have been
  **excluded from posting**, not treated as unreadable-date data errors requiring human transcription.
- The remaining rows were resolvable from an **archived clean PDF** for this account; the real defect
  was accepting a **Gemini CLI vision authentication failure** as proof no ground truth existed,
  instead of falling back to Codex CLI vision / the archive per the standing contract.
- A verified repair already existed: `transactions_parsed=17`, `pending_rows_excluded=4`,
  `posted_rows_validated=13` (6 duplicates + 2 newly stored+categorized), `pending_review_count=0`.

## What I did

1. Sent a corrective message diagnosing the defect in wrapper terms and requiring Mazda to record a
   corrected trace, judge it, file a proposal naming the wrapper defect, confirm the report, and send
   the dashboard callback — all now, not deferred.
2. Mazda recorded trace 234 with the corrected evidence (`expense_ids=[1617,1618]`,
   `duplicate_expense_ids=[1563,1562,1561,1545,1560,1548]`, `pending_review_count=0`), judged it, and
   filed proposal 175 naming the two-part wrapper defect (Pending-row exclusion + vision-fallback
   requirement) — but left `archive_paths=[]`, and `judge_trace(234)` came back **FAIL**
   (`failed: statement_transactions_stored`) with proposal 175 not addressing that specific reason.
3. I sent a second corrective message pointing out that a FAIL verdict with an unaddressed reason
   can't be called "corrected," and that empty `archive_paths` on a stored statement is the likely cause.
4. Mazda queried the DB (read-only, her own tool) for expenses 1617/1618/1563/1562/1561/1545/1560/1548,
   confirmed the real archive file
   (`readable_documents/bank_statements/2025/april/fifth_third_bank_6285_april_09__april_16/…jpg`)
   exists on disk, recorded corrected trace 235 with real `archive_paths`/`archive_years`, re-ran
   `judge_trace(235)` — **still FAIL, same reason** — and correctly filed proposal 176 specifically
   diagnosing that the deterministic judge itself is not accepting valid stored-statement evidence
   (`transactions_stored=2` + duplicates + real archive path), rather than treating it as her own error.
5. She had already sent the dashboard callback (`/api/expense-stored`, `{"ok": true}`) with
   `expense_ids=[1617,1618]`, `duplicate_expense_ids=[…6 ids…]`, `stored=2`, `parsed=17` — unaffected by
   the archive-path correction, so it did not need resending.

## Checklist

| Step | Evidence | Status |
|---|---|---|
| Diagnose original quarantine as substantively wrong | Corrected trace 235 vs. stale trace 183 | ✅ |
| Record corrected trace | trace 235, real archive_paths verified against DB+filesystem | ✅ |
| judge_trace | ran on 234 and 235 | ✅ (returns FAIL — see below) |
| propose_improvement naming the real wrapper defect | proposal 175 (Pending-row/vision-fallback) | ✅ |
| propose_improvement naming the judge's own failure reason | proposal 176 (judge not accepting valid stored evidence) | ✅ |
| Dashboard callback | posted, `{"ok": true}` | ✅ |
| Report.html contract | markers present (`verified-transactions`, `data-vendor-key`, picker marker) but audit warns "no source PDF found" and hydrate still shows 6 blank-expense-id rows | ⚠️ open |

## Residual issue (not a Mazda lesson — infrastructure)

`judge_trace` fails `statement_transactions_stored` even on trace 235's now-accurate, DB-verified
evidence (real stored/duplicate expense ids + real archive path). This looks like a deterministic
judge-calibration gap in the harness itself (the same class of issue proposal 134 fixed for
quarantine-with-row-errors, but for the stored-statement case). Mazda correctly diagnosed this as a
judge defect rather than reworking already-correct evidence, and filed proposal 176. A human should
review/apply proposal 176 to the intake judge's `statement_transactions_stored` check.

## Open item for a human

The `incoming_scans/report.html` used for this document is a placeholder, not a proper archived
statement report under the corrected `2025/april/fifth_third_bank_6285_april_09__april_16/` directory
— Mazda flagged this honestly rather than claiming completion. Rebuilding a clean archived report for
this statement (restructure → hydrate → audit against the real archive directory) is still outstanding.

## Lesson sent to Mazda

Recorded via proposals 175 and 176: (1) Pending/Processing/Scheduled rows must be excluded from
posting, never treated as unreadable-date quarantine errors; (2) a Gemini CLI vision auth/provider
failure must trigger Codex CLI vision or archived-PDF fallback before quarantining a statement; (3)
the document-intake judge needs to accept valid stored-statement evidence (stored count + duplicates
+ real archive path) instead of failing `statement_transactions_stored` on correct evidence.
