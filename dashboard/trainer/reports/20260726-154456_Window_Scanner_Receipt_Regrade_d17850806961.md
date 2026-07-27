# Trainer Report — Window Scanner (Receipt Regrade)

- **Document:** `window_scan_1785080690523902433_c9c44bf31aaa.jpg`
- **Dispatch:** 2026-07-26T15:44:56Z
- **Mazda conversation:** `conv-b43f6150-8677-4b54-9f7b-fde2b1a2085e`
- **Run duration:** ~2m03s (dispatch → final assistant message at 15:46:59Z)
- **Verdict: PASS**

## Note on the facade value given to the Trainer

The dispatch task handed to the Trainer named a "Deterministic facade result" of
`{"doc_kind":"receipt","confidence":0.95,...}`, but the actual dispatch message Mazda
received (and correctly acted on) said the facade returned `doc_kind=unknown,
confidence=0.0` — the normal outcome for a JPEG scan with no extractable text. The
number quoted to the Trainer exactly matches Mazda's own later `classify_scan.py`
output, suggesting it was populated from the wrong source when this dispatch's
metadata was assembled. This did not affect grading — Mazda ran STEP 0 as required —
but the dashboard/report-metadata plumbing that supplies "facade result" to the
Trainer may be labeling data incorrectly for scanned images. Worth a look, not a
Mazda wrapper defect.

## Checklist (all confirmed via successful tool returns in-transcript)

1. `load_wrapper_revision(agent_name="Mazda")` → `wrap-v059`, learned rules loaded. ✓
2. STEP 0 (facade `unknown`) → `classify_scan.py` → `doc_type=receipt`, confidence 0.95,
   merchant "Right to Life of Michigan". Then `parse_and_categorize.py --json` →
   single line item ("EF Donations", $24.00), `expense_scope=full_receipt` — no
   selection marks present on this document, so full-receipt scope is correct (not a
   marked-item receipt). ✓
3. Investigate: `check_vendor_key` → normalized `right_to_life_of_michigan` →
   `michigan_corporations_division` (fuzzy match), adopted. `check_duplicates` (date
   2025-03-18, amount 24.00) → not a duplicate. ✓
4. Categorize: `categorizer_main.py` via `executor_run` (gemini provider) →
   `category_id=357`, positive/valid. ✓
5. Store: `parse_and_categorize.py --save --category-id=357` → success,
   `expense_id=1660`, `parse_artifact_verified=true` (matches the STEP 0 parse
   artifact — no second vision pass), amount/date/merchant consistent with STEP 0/
   duplicate-check inputs. Then `itemize_existing_expense` → correctly returned
   `itemizable:false` (single line item equal to the charge, standalone) — proper
   fail-closed outcome per contract. ✓
6. `record_trace(task_name="document-intake")` → evidence JSON matches reality
   (`stored:true`, `expense_id:1660`, normalized vendor_key, `is_duplicate:false`,
   `problems` correctly lists the vendor-key fuzzy-match note and a benign
   `source_file` update warning). `wrapper_revision=wrap-v059`. ✓
7. `judge_trace(trace_id=257)` → **PASS**, `failure_type=none`. ✓
8. `propose_improvement` — correctly skipped (only required on FAIL). ✓
9. Dashboard notify: `POST /api/expense-stored` with correct `conversation_id`,
   `dispatched_at`, `expense_id`, `expense_ids`, `duplicate_expense_ids:[]`,
   `receipt_url`/`document_path` both pointing at the scan (receipt branch, no
   conflicting supporting-document field). Response `{"ok": true}`. ✓

Order of operations (record_trace → judge_trace → dashboard callback) matches the
required sequence.

## Wrapper defect diagnosed

None. No coaching message was sent.

## For a human

Nothing blocking. Only item worth a look: the facade-result value surfaced to the
Trainer for this dispatch looks like it was populated from `classify_scan.py`'s
output rather than the actual text-extraction facade — cosmetic/report-metadata only,
did not affect this run's outcome.
