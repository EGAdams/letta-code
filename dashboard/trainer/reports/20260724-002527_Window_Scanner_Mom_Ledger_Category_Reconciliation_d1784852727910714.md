# Mazda Trainer Report

- Scanner: `Window Scanner Mom Ledger Category Reconciliation`
- Dispatch time: `2026-07-24T00:25:27.910Z`
- Scanned image: `/home/adamsl/rol_finances/tools/receipt_scanning_tools/incoming_scans/scan_1784852724195055737_b51a676a6b70.jpg`
- Verdict: `FAIL`

## Checklist

- `load_wrapper_revision(agent_name="Mazda")` succeeded at `00:25:31Z`, returning `wrap-v039`.
- `classify_scan.py` via `executor_run` succeeded at `00:25:44Z`, returning `doc_type="other"` with `confidence=0.9`.
- `record_trace` succeeded at `00:25:52Z` with `task_name="document-intake"` and explicit unsupported-document evidence:
  - `stored=false`
  - `expense_id=null`
  - `duplicate_checked=false`
  - `problems` included `unsupported_document`
- `judge_trace(trace_id=180)` succeeded at `00:25:55Z` but returned `FAIL` with `failure_type="unsupported_document"`.
- `propose_improvement(trace_id=180, failure_type="unsupported_document")` succeeded at `00:26:01Z`.
- `apply_proposal(proposal_id=130)` succeeded at `00:26:05Z`, activating `wrap-v040`.
- Dashboard callback via `curl POST /api/expense-stored` succeeded at `00:26:12Z` with `{"ok":true}`.
- `propose_memory_note(...)` succeeded at `00:26:54Z`.

## Diagnosis

Mazda correctly stopped the intake after classification for an explicit `doc_type=other` document and recorded an unsupported-document trace. The remaining defect is in the wrapper/judge path: the run was still judged as `FAIL` for missing receipt/invoice stages, so the unsupported-document branch is not yet fully reflected in the verdict logic.

## Lesson Sent

`For explicit classify_scan.py doc_type=other unsupported scans, keep the intake trace explicit with stored=false, expense_id=null, and problems naming unsupported_document; always send the /api/expense-stored dashboard callback with the no-store outcome; if judge_trace returns FAIL, file propose_improvement using that exact trace_id and do not run receipt/category/store steps.`

## Human Follow-Up

- Verify the updated judge logic after `wrap-v040` on the next unsupported-document run.
- The transcript shows the run completed its coaching loop, but the verdict remained `FAIL`, so this report is not a PASS.
