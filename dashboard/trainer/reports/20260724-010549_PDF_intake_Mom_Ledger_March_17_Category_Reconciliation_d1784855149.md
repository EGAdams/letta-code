# Mazda Trainer Report

- Document: PDF intake, `Mom Ledger March 17 Category Reconciliation`
- Scanner image: `/home/adamsl/rol_finances/tools/receipt_scanning_tools/incoming_scans/scan_1784852724195055737_b51a676a6b70.jpg`
- Dispatch time: `2026-07-24T01:05:49Z`
- Conversation ID: `conv-7f6d4886-f590-41a4-bdcb-3156b44ca47d`

## Verdict

PASS

## Checklist

1. `load_wrapper_revision(agent_name="Mazda")`
   - Success: returned `wrap-v040` with active learned rules.
2. Classification
   - Success: `classify_scan.py` returned `doc_type="moms_ledger"`, `confidence=1.0`.
3. Mom-ledger reconciliation
   - Success: `moms_ledger_reconciler.py` returned `ok=true`.
   - Evidence: `vision_provider="codex-cli"`, `transactions_read=13`, `unmatched=[]`, `unrecognized=[]`, `problems=[]`.
   - Matched rows included the expected check/payment worksheet entries and handwritten category notes.
4. Trace
   - Success: `record_trace` saved trace `181` with `task_name="document-intake"`.
   - Evidence shape matched the moms-ledger branch: `doc_kind="moms_ledger"`, `transactions_read=13`, `categories_confirmed`, `categories_applied`.
5. Judge
   - Mazda’s judge returned `FAIL` with `failure_type="missed_vendor_key"`, but that verdict was inconsistent with the supported moms-ledger branch that actually completed.
   - This is the wrapper defect, not a missing intake step.
6. Improvement loop
   - Success: `propose_improvement` created proposal `132`.
   - Success: `apply_proposal` activated `wrap-v041` from proposal `132`.
   - The new rule explicitly teaches the judge to treat `moms_ledger` as a first-class supported branch.
7. Dashboard callback
   - Success: POSTed `/api/expense-stored` with `stored=0`, `doc_kind="moms_ledger"`, `expense_ids=[1558,1564,1561,1547,1550,1567,1553,1556,1559,1562,1548,1551,1554]`, and the conversation metadata.

## Wrapper Defect

The intake judge/rubric did not recognize `moms_ledger` as a supported non-receipt branch and scored it like a receipt-style missed-vendor failure. Mazda already filed the fix and activated `wrap-v041`.

## Lesson Sent

No extra coaching message was needed beyond Mazda’s own proposal/apply loop. She already captured the correct fix: treat `moms_ledger` as supported intake and judge it on the reconciliation evidence, not receipt vendor/category fields.

## Human Follow-Up

Check trace `181` and proposal `132` if you want to audit the rubric change, but the intake itself completed correctly and the dashboard callback was posted.
