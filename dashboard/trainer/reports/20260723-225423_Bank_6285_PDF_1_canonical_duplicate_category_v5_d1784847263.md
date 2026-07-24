# Mazda Trainer Report

- Scanner: `Bank 6285 PDF 1 canonical duplicate category v5`
- Source document: `/home/adamsl/rol_finances/readable_documents/bank_statements/march/non_profit_rol_Statement_december_january_6285/february_march_fifth_third_6285_2025.pdf`
- Dispatch time: `2026-07-23T22:54:23Z`
- Verdict: `PASS`

## Checklist

1. `load_wrapper_revision(agent_name="Mazda")`
   - Successful tool return: `wrapper_revision = wrap-v039`
2. Report rebuild
   - Rebuilt `/home/adamsl/rol_finances/readable_documents/bank_statements/march/non_profit_rol_Statement_december_january_6285/report.html`
   - Preserved all 19 expense/debit rows in source debit order
3. `restructure_verified_transactions.py`
   - Successful return: `updated .../report.html`
4. `hydrate_report_categories_from_db.py .../report.html`
   - Successful return: `ok: true`
   - `blank_expense_id_rows: 0`
   - `missing_expense_ids: []`
   - `rows_with_expense_id: 19`
5. `audit_statement_reports.py`
   - Successful return: `PASS`
6. `record_trace`
   - Trace saved: `178`
   - Included `report_path`, `report_generated: true`, `report_audit_status: "PASS"`, and `report_hydrator_result`
7. `judge_trace(178)`
   - Successful return: `PASS`
8. Dashboard callback
   - `/api/expense-stored` resent with `report_path`

## Notes

- Mazda initially produced an incomplete 3-row report during the correction cycle, but the final rerun restored the full 19-row statement table and passed hydration, audit, and judge checks.
- Final report artifact exists at the required path.
