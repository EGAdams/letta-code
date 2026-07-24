# Mazda Trainer Report

- Scanner: `Bank 6285 PDF 1 source-safe category correction v3`
- Document: `/home/adamsl/rol_finances/readable_documents/bank_statements/march/non_profit_rol_Statement_december_january_6285/february_march_fifth_third_6285_2025.pdf`
- Dispatch timestamp: `1784847263` (`2026-07-23T22:54:23Z`)
- Verdict: `FAIL`

## Checklist

- `load_wrapper_revision(agent_name="Mazda")`: observed in transcript.
- Statement branch taken: observed `executor_run` activity, `record_trace`, `judge_trace`, and statement report handling.
- Report generation and restructuring: observed `restructure_verified_transactions.py` and `audit_statement_reports.py` succeeding on `report.html`.
- Hydration: observed `hydrate_report_categories_from_db.py /home/adamsl/rol_finances/readable_documents/bank_statements/march/non_profit_rol_Statement_december_january_6285/report.html` returning `ok: true`, `blank_expense_id_rows: 0`, `missing_expense_ids: []`.
- Trace/judge/callback: observed `record_trace` with `task_name="document-intake"` and later `judge_trace` returning `PASS` on trace `176`, plus a dashboard callback that included `report_path`.
- Final report content check: failed. The live `report.html` still contains March-April rows such as `2025-03-24`, `2025-03-17`, `2025-04-03`, `2025-04-10`, and does not contain the three required source rows from this PDF:
  - `2025-03-07 REF 01102666169 expense 1156 Personal`
  - `2025-03-13 AT&T XXXXX6008 expense 1157 Utilities`
  - `2025-03-14 REF 01104943983 expense 1158 Personal`

## Wrapper Defect

The statement-report wrapper still permits report contamination from the wrong parsed rows. Mazda rebuilt the report, but the live HTML did not preserve the required source rows for this PDF, so the report is not a valid reconstruction of the dispatched statement.

## Lesson Sent

I sent Mazda this corrective message:

> The current `report.html` is still wrong for this PDF: it passes audit/hydration structure, but it does not preserve the three required source rows from the statement. Rebuild the report from the unique parse JSON for this exact PDF, not from the contaminated shared parse output, and make sure the verified-transactions table contains these three source rows exactly: `2025-03-07 REF 01102666169 expense 1156 Personal`; `2025-03-13 AT&T XXXXX6008 expense 1157 Utilities`; `2025-03-14 REF 01104943983 expense 1158 Personal`. Then rerun restructure, hydrate, audit, record_trace with the hydrator result and the `report_path`, judge again, and resend the dashboard callback with `report_path`. Do not mark this complete until the live report actually contains those source rows.

## Human Review Notes

- Mazda’s own transcript claims the hydrator and audit passed, but the file on disk still does not contain the required source-row evidence.
- The final status is therefore `FAIL`, not `PASS`, despite the internal judge result.
