# Mazda Trainer Report

- Scanner: PDF intake (MARCH 2025 — Bank 6285 PDF 2 — Codex vision retry)
- Dispatch: 2026-07-23T22:54:24Z
- Document: `/home/adamsl/rol_finances/readable_documents/bank_statements/march/business_january_february_6285/march_april_fifth_third_6285_2025.pdf`
- Verdict: PASS

## Evidence

- `load_wrapper_revision(agent_name="Mazda")` returned `wrap-v039`.
- `classify_scan.py` returned `doc_type=bank_statement`, confidence `0.95`, merchant `Fifth Third`.
- `parse_statement_scan.py` succeeded with `statement_count=1`, `bank_name=Fifth Third Bank`, `account_number=6285`, `transaction_count=52`, `unreadable_count=0`.
- `store_statement_transactions.py` succeeded with `transactions_parsed=52`, `skipped_credits=18`, `duplicates=34`, `stored=0`, `bank_name=Fifth Third Bank`, `account_last4=6285`, `account_last4_source=statement`, `archive_paths=[/home/adamsl/rol_finances/readable_documents/bank_statements/2025/march/fifth_third_bank_6285_march_17__april_15/fifth_third_bank_6285_march_17__april_15.pdf]`, `problems=[]`.
- `apply_statement_annotations.py` succeeded with `annotation_provider=codex-cli`, `applied=[]`, `unrecognized=[]`, `problems=[]`.
- `record_trace` saved trace `166`.
- `judge_trace(166)` returned `PASS` with `failure_type=none`.
- Dashboard callback was sent and returned `{"ok": true}`; the post-dispatch stored-event record exists for this conversation and dispatch.

## Notes

- This was a correct duplicate-only statement intake.
- No coaching message or `propose_improvement` was needed because the verdict was PASS.
