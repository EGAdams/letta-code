# Trainer Report — Window Scanner Choice 7580 Correction

- **Scanner:** Window Scanner
- **Document:** `window_scan_1785186447546854038_6e86c96559cd.jpg`
- **Dispatch time:** 2026-07-27T21:07:32Z (1785186452)
- **Mazda conversation:** `conv-cfb4ad7b-0de5-4b36-9d0a-3a18d9b99c04`
- **Verdict: CORRECTED**

## What actually happened

The dispatch message Mazda received in this conversation instructed her to store this
statement as **`Wells Fargo` / account last4 `4884`**. But the deterministic facade
result supplied for this Trainer run (for this exact scanned file) resolves the
statement's branding uniquely against `Known_Credit_Cards_and_Banks.xlsx` to
**`Choice Privileges Mastercard` / last4 `7580`** (`workbook_matched_names:
["choice_7580"]`). Neither the bank name nor the last4 digits in the dispatch matched
the workbook-authoritative identity.

Mazda executed the (wrong) dispatch faithfully — including a prior Trainer's
in-conversation coaching that fixed an unrelated report.html formatting defect
(trace_id 271 → 273) — and `judge_trace` PASSed both times, because judging only
checks deterministic finance steps, not account identity. Per the manual's rule
("independently resolve the visible primary card/product letterhead... any mismatch
is a FAIL even when judge_trace says PASS"), trace 273 was a FAIL.

## Checklist (post-coaching, trace 275)

| Step | Evidence |
|---|---|
| Independently re-verified workbook | `executor_run` read `Known_Credit_Cards_and_Banks.xlsx` row 13: `choice_7580 / 7580 / Choice` — unique match confirmed |
| Re-ran `store_statement_transactions.py` with corrected `--bank-name 'Choice Privileges Mastercard' --account-last4 7580` | returncode 0; all 5 parsed rows resolved to 3 duplicates (1366, 1390, 1674) + 2 skipped credits, 0 newly stored — **no orphan/duplicate expense created** for the previously wrong-identity store |
| Verified DB rows for 1366/1390/1674 | queried directly; `document_url` already pointed at this scan, unaffected by the identity fix |
| Corrected archive built, obsolete archive removed | `{"report_path": ".../choice_privileges_mastercard_7580_july_31__august_15/report.html", "rows":3, "skipped_rows":2, "removed_old_dir": true}` — old `wells_fargo_4884_july_31__august_15` directory removed only after the corrected copy was built |
| `apply_statement_annotations.py` re-run with corrected IDs | `annotation_provider: "gemini"`, existing handwritten note on 1674 confirmed unchanged (category_id 160) |
| Report pipeline re-run | `restructure` → `hydrate` (`rows_with_expense_id: 3, blank_expense_id_rows: 0, uncategorized_rows: 0`) → `audit` (`WARN: no source PDF found` only — acceptable, no FAIL) |
| `record_trace` (trace_id 275) | correct `bank_name`, `account_last4="7580"`, `account_last4_source="known_cards_workbook"`, corrected `archive_paths`/`report_path`, `problems` documenting the original misidentification |
| `judge_trace(275)` | **PASS** |
| `propose_improvement` + `apply_proposal` | proposal 192 filed and activated → `wrap-v060`, correctly diagnosing the root cause as the **dispatch-construction path**, not Mazda's own tool use |
| Dashboard callback | `POST /api/expense-stored` with corrected `bank_name`/`account_last4`/`report_path` → `{"ok": true}` |

## Wrapper defect diagnosed

Not a Mazda-side defect. The dispatch text built for this "Choice 7580 Correction" job
embedded stale/wrong `Wells Fargo`/`4884` values instead of the corrected
`Choice Privileges Mastercard`/`7580` identity that this Trainer run's own facade
result already carried. This points at a bug in the dashboard's dispatch-message
construction for statement corrections — it did not thread the corrected
workbook-resolved bank/last4 into the message actually sent to Mazda's conversation.

## Lesson sent to Mazda

Coached her (in-conversation) to independently re-verify bank/last4 against
`Known_Credit_Cards_and_Banks.xlsx` whenever a statement dispatch specifies explicit
bank/account values, treat a unique workbook mismatch as authoritative over the
dispatch text, and correct storage/archive/report/trace/callback accordingly. She
recorded this via `propose_memory_note` and it was folded into the activated proposal
192 (`wrap-v060`).

## For a human

**The dashboard's statement-dispatch builder needs to be fixed** so a "correction"
dispatch actually carries the corrected bank/last4 values instead of repeating the
original wrong ones — this Trainer run only caught it because the facade data handed
to the Trainer differed from what was actually sent to Mazda. Recommend auditing
`build_mazda_scan_message()` / whatever code assembled this dispatch's `--bank-name`
/`--account-last4` values for the "Choice 7580 Correction" scanner run.
