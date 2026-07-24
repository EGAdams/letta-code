# Mazda Trainer Report

- Scanner: PDF intake (MARCH 2025 — Bank 6285 PDF 1 — Codex vision retry)
- Document: `/home/adamsl/rol_finances/readable_documents/bank_statements/march/non_profit_rol_Statement_december_january_6285/february_march_fifth_third_6285_2025.pdf`
- Dispatch: `2026-07-23T22:54:23Z`
- Verdict: PASS

## Checklist

- `load_wrapper_revision` succeeded with `wrap-v039`.
- `classify_scan.py` classified the PDF as `bank_statement` for `Fifth Third` with confidence `0.95`.
- `parse_statement_scan.py` initially failed on the PDF vision path (`Gemini 429` / PDF-to-vision mismatch), then succeeded on retry with `statement_count=1`, `transactions_parsed=39`, `skipped_credits=20`.
- `store_statement_transactions.py` initially rejected the statement because `account_last4` was missing and the workbook entry was ambiguous, then succeeded with `bank_name="Fifth Third Bank"`, `account_last4="6285"`, `account_last4_source="operator"`, `stored=3`, `duplicates=16`, `deposits_stored=20`, and `archive_paths=["/home/adamsl/rol_finances/readable_documents/bank_statements/2025/february/fifth_third_bank_6285_february_18__march_14/fifth_third_bank_6285_february_18__march_14.pdf"]`.
- `apply_statement_annotations.py` succeeded with `annotation_provider="codex-cli"` and `applied=[]` / `unrecognized=[]`.
- `record_trace` succeeded with `trace_id=167` and `task_name="document-intake"`.
- `judge_trace(167)` returned `PASS` with `failure_type="none"`.
- Dashboard callback was recorded in `/api/expense-stored-events` for this conversation and dispatch (`expense_ids=[1581,1582,1583]`, `duplicate_expense_ids=[1147,1144,1145,1140,1141,1148,1143,1146,1150,1151,1152,1153,1155,1156,1157,1158]`).

## Notes

- The only corrected wrapper issue was statement intake metadata recovery: the first store rejected on missing/ambiguous `account_last4`, then the run retried with the operator-supplied last four and completed cleanly.
