# Mazda Trainer Report

- Scanner: `Bank 6285 PDF 1 complete 19-row category correction v4`
- Dispatch time: `2026-07-23T22:54:23Z`
- Document: `/home/adamsl/rol_finances/readable_documents/bank_statements/march/non_profit_rol_Statement_december_january_6285/february_march_fifth_third_6285_2025.pdf`
- Verdict: `PASS` after correction

## Checklist

- `load_wrapper_revision(agent_name="Mazda")` was missing in the initial run, so I coached Mazda to restart from the top.
- Mazda then logged `load_wrapper_revision` at `2026-07-24T00:13:27+00:00` with active wrapper `wrap-v039`.
- Mazda rebuilt `/home/adamsl/rol_finances/readable_documents/bank_statements/march/non_profit_rol_Statement_december_january_6285/report.html` from `/tmp/mazda_unique_pdf_rows.json` and restored the full statement table.
- `restructure_verified_transactions.py` succeeded, followed by `hydrate_report_categories_from_db.py` with:
  - `ok: true`
  - `blank_expense_id_rows: 0`
  - `missing_expense_ids: []`
  - `categorized_rows: 18`
- On disk, `report.html` now has:
  - `19` verified expense rows
  - `0` blank `data-expense-id` rows
  - `1` `rol-category-picker:start` marker
- `audit_statement_reports.py` returned `PASS`.
- `record_trace` saved trace `178` with `task_name="document-intake"`.
- `judge_trace(178)` returned `PASS`.
- The dashboard callback `/api/expense-stored` returned `{"ok": true}` for the corrected run.

## Defect Diagnosed

- The initial report was incomplete and only carried a 3-row Verified Transactions table.
- The initial transcript also lacked the required wrapper-load evidence.
- Root cause: Mazda stopped at a partial report rebuild instead of restarting from the statement-spec source rows and rerunning the full verification tail.

## Lesson Sent

> You did not satisfy the dispatch yet. First, log the wrapper with `load_wrapper_revision(agent_name="Mazda")`. Then rebuild `/home/adamsl/rol_finances/readable_documents/bank_statements/march/non_profit_rol_Statement_december_january_6285/report.html` from `/tmp/mazda_unique_pdf_rows.json` so Verified Transactions contains all 19 expense/debit rows paired to the required duplicate IDs `[1147,1144,1145,1140,1141,1148,1142,1143,1146,1582,1150,1151,1152,1153,1154,1155,1156,1157,1158]` in source debit order. Then rerun `restructure_verified_transactions.py`, `hydrate_report_categories_from_db.py` on that exact `report.html`, `audit_statement_reports.py`, `record_trace` with `report_path`/`report_generated`/`report_audit_status`/`hydrator_result`, `judge_trace`, and resend the dashboard callback with `report_path`. Do not leave the report in a 3-row state; that is incomplete for this dispatch. Record this lesson in memory.

## Human Notes

- The corrected report is now complete and passes audit/hydration/trace/judge/callback checks.
- The initial partial state should be treated as a wrapper/process defect, not a model failure.
