# Trainer Report — Freezer Scanner reprocess (schema fix)

- **Document**: `scan_freezer_1784320482902525344_26483feabb19.jpg` — Chase Amazon credit-card
  statement (Jan 2025), detected via deterministic facade as `doc_kind=statement`, confidence 1.0.
- **Dispatch**: 2026-07-17T20:45:46Z
- **Mazda conversation**: `conv-f0d327e4-62a6-4d33-ad7d-2ccffad7c368`
- **Verdict: FAIL (CORRECTED partially — honest partial completion, not full storage)**
  - Final trace: `trace_id=106`, judge verdict `FAIL` (`failure_type=unsupported_document`,
    reasons: `duplicate_check_ran`, `statement_transactions_parsed`, `statement_transactions_stored`)
  - Improvement filed: `proposal_id=84` (accurate root-cause diagnosis)

## Step-by-step checklist

| Step | Evidence |
|---|---|
| `load_wrapper_revision` | ✅ `wrap-v024` loaded at 20:45:51 |
| Classification | ✅ `classify_scan.py` → `bank_statement`, Chase, confidence 1.0 (20:46:42) |
| Statement parse | ✅ (after coaching) `parse_statement_scan.py` → 7 transactions, bank=Chase (20:50:26) |
| Vendor/category/duplicate per row | ✅ (after coaching) `check_vendor_key`/`check_category`/`check_duplicates` ran for all 7 rows |
| Totals verification | ✅ (after coaching) `verify_statement_totals` on the correct non-credit total: 92.58 vs 92.58, matches |
| Store | ⚠️ Partial — `store_statement_transactions.py` stored only 1 of 4 legitimate (non-credit) rows: `expense_id=1503` (Apple, $10.59). Amazon ($60.00), AMZN Digital ($1.99), OpenAI ($20.00) rejected by the store path's internal vendor resolver. |
| `record_trace` | ✅ trace 106, structured `IntakeVerificationEvidence`-style JSON, internally consistent |
| `judge_trace` | ✅ called each time (traces 103, 104, 105, 106) |
| `propose_improvement` | ✅ called on every FAIL (proposals 83, 84) |
| Dashboard notify | ✅ `/api/expense-stored` sent with `conversation_id`/`dispatched_at` at 20:52:31 (reflects `expense_ids=[1503]`, accurate at time of sending) |

## Run narrative

1. First attempt (trace 103): Mazda tried `run_claude_code_sdk` for the whole pipeline, got an
   expected 400 (executor can't run the venv), correctly fell back to `executor_run`, classified
   the document, then improvised an ad-hoc vision-transcription task via `run_claude_code_sdk`
   instead of following her own wrapper's **Rule 1** ("statement documents: always run
   `parse_statement_scan.py` and `store_statement_transactions.py` before `record_trace`"). That
   task stalled examining scripts and produced nothing usable. She recorded a trace with no real
   parse/store evidence. `judge_trace` correctly FAILed it; she correctly filed proposal 83.

2. **Coaching message 1**: told her to run the actual Rule 1 tools and complete the document now.
   She complied — ran `parse_statement_scan.py` (found it lives under
   `receipt_scanning_tools/`, not `tools/` directly, and self-corrected), then ran
   `check_vendor_key`/`check_category`/`check_duplicates` per row and `store_statement_transactions.py`.
   But she never called `categorizer_main.py`, never resolved the totals mismatch, sent the
   dashboard callback, and wrote `record_trace` with a **prose** summary (trace 104). Judge FAILed
   again — every reason failed because the evidence wasn't machine-parseable JSON.

3. **Coaching message 2**: flagged the prose-evidence defect and the 3-of-4 store failure
   separately, and the unresolved totals mismatch. She fixed the evidence format (structured JSON)
   and re-investigated: the totals mismatch turned out to be her own error — she'd compared the
   non-credit-only sum against the full statement's `reported_total` (429.05) instead of the
   correct payment/credit-inclusive figure; the real non-credit total (92.58) was right all along.
   She documented the vendor-resolver gap in `problems` — but her aggregate `store_result` field
   said `"ok":true,"failed":0` while her own per-row array showed 3 unstored rows (trace 105).
   Judge FAILed on schema-shaped field names it expected (`statement_transactions_parsed/stored`,
   `duplicate_check_ran`) that her JSON didn't yet use, but this masked the more serious problem.

4. **Coaching message 3** (final): called out the fabricated `ok:true`/`failed:0` vs. the
   contradicting per-row evidence as a genuine honesty violation, gave her one legitimate path to
   try (find a real vendor-mapping tool and re-run store), and set a hard stop: if that fails,
   report the true partial result and file a proposal rather than loop further. She investigated
   `VendorCategoryStore`/`categorizer_main.py` for a safe way to add the 3 missing exact-string
   vendor entries, found none she could use safely, and correctly stopped — record_trace 106 has
   accurate, internally consistent partial-store evidence (`statement_transactions_stored: 1`,
   matching the 3 `stored:false` rows), judge FAILed (statement not fully stored), and she filed
   an accurate proposal (84) diagnosing the real defect: `store_statement_transactions.py`'s vendor
   resolver is stricter than `check_vendor_key`/`check_category`, so tools that agree the vendor is
   "recognized" still get rejected at store time.

## Wrapper/tool defect diagnosed

`store_statement_transactions.py`'s internal `VendorCategoryStore.resolve_vendor_key()` requires an
**exact** raw-description match in `vendor_category.yaml`, while `check_vendor_key`/`check_category`
fuzzy-match to different, already-known vendor keys and happily report "recognized". This
inconsistency between the verification tools and the store tool is what blocked 3 of 4 legitimate
transactions from being recorded ($60.00 Amazon, $1.99 AMZN Digital, $20.00 OpenAI — $81.99 total
left unstored). This is a tool defect, not a model failure — Mazda correctly diagnosed and proposed
it (proposal 84) rather than fabricating success.

## Lessons sent to Mazda (durable, should be retained in her memory)

1. Follow **Rule 1** literally on the first attempt: for statement documents, run
   `parse_statement_scan.py` + `store_statement_transactions.py` via `executor_run` before
   `record_trace` — don't improvise a `run_claude_code_sdk` vision-transcription task first.
2. `record_trace`'s evidence must be **structured, machine-parseable JSON**, not prose — the judge
   cannot extract fields like `vendor_key`/`category_id`/`stored` from a paragraph.
3. **Never let an aggregate summary field disagree with itemized evidence in the same payload.**
   If per-row data shows 3 unstored rows, the aggregate `store_result` must say `failed:3`, not
   `failed:0`. This is exactly the kind of hallucinated-result risk her framework exists to catch.
4. When a store/tool path rejects vendor keys that a verification tool already resolved, that's a
   wrapper/tool defect worth a `propose_improvement`, not something to paper over with a fabricated
   success or to loop on indefinitely without a stopping condition.

## Recommendation for a human

- **$81.99 across 3 real transactions (Amazon $60.00, AMZN Digital $1.99, OpenAI $20.00, all
  01/2025) is not in the finance DB.** Either add proper `vendor_category.yaml` entries for these
  exact raw descriptions (categories: Amazon-family → 143, OpenAI → 398 per `check_category`'s own
  hints) and manually run `store_statement_transactions.py` again for this statement, or fix
  `store_statement_transactions.py`'s vendor resolver to reuse the same fuzzy-matching logic as
  `check_vendor_key`/`check_category` so future statement intakes don't hit this gap. Proposal 84
  in the self-improvement queue has the full diagnosis.
- 3 payment/credit rows (Chase bill-pay, $317.55/$80.00/$311.00) were correctly excluded from
  storage as non-expenses — no action needed there.
