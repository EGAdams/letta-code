# Trainer Report — Freezer Scanner Marked Item Correction

- **Document:** `scan_freezer_1785003474158333662_8f98fd588745.jpg` (Meijer receipt, marked-item: STOOL SOFTENER $10.99)
- **Scanner:** Freezer
- **Dispatch:** 2026-07-25T18:17:57Z (`conv-1e818bbd-00b0-43b2-9c5d-66d92244f568`)
- **Verdict: FAIL (data-integrity defect) — human DB cleanup required**

## Timeline (reconstructed from transcript + `/api/expense-stored-events`)

1. **18:17:58–18:20:50** — First intake attempt. Classify/parse/categorize succeeded (receipt, Meijer, conf 0.95), but `check_duplicates` and the save both crashed on live DB schema drift (`Unknown column 'expense_role'` / `'account_number'`). `judge_trace` → **FAIL** (trace 191). `propose_improvement` → `apply_proposal` activated `wrap-v047` (schema-safety guard). Callback posted `stored:0`.
2. **~18:48:14** (not visible in the live transcript window — almost certainly pruned by context compaction) — Mazda correctly re-ran the marked-item-only parse and **successfully stored `expense_id 1564`** (`"meijer — STOOL SOFTENER (marked item only)"`, $10.99, 2025-03-31). This is the correct, canonical record for this document.
3. **19:04:45** — A `CORRECTIVE TRAINER LESSON` user message (**not sent by this Trainer instance**) re-explained the marked-item-vs-sweeping-mark rule. Mazda replied at 19:04:50 restating the rule in prose but executed **no tool calls** — she did not realize the correction had already been completed in step 2.
4. **19:04:50 → 19:19** — Stalled. No new activity for ~15 minutes despite already having a correct stored record.
5. **19:19** (this Trainer) — Sent one corrective push instructing her to execute the full corrected re-parse/check/save/trace/judge/callback chain now, since her prose reply gave no evidence of action.
6. **19:20:18–19:21:52** — Mazda re-ran the entire pipeline from scratch. Her pre-save `check_duplicates` call used a **placeholder `id_light="scan"`** instead of the canonical vendor+date+amount key, so it returned `is_exact_duplicate:false` (false negative) even though the real record (1564) already existed. She then saved again, creating a **new, erroneous duplicate expense `1566`** for the same real-world transaction. `record_trace`/`judge_trace` (trace 194) → PASS (the deterministic checks don't know 1566 duplicates 1564), and she posted a callback claiming `stored:1, expense_id:1566`.
7. **19:21:55** — A second unsolicited `TRAINER RECOVERY` user message (**again not sent by this Trainer instance**) correctly diagnosed the `id_light="scan"` bug, identified canonical id_light `meijer_03_31_25_10_99`, and instructed Mazda to re-check duplicates properly and record this as duplicate-only against `expense_id 1564` — "do not store another row." Mazda complied: `check_duplicates` (canonical key) correctly returned `is_exact_duplicate:true, exact_duplicate_expense_id:1564`; she recorded trace 195 (PASS) and posted a final callback with `duplicate_expense_ids:[1564], stored:0`.

## Net outcome

- **Correct canonical record:** `expense_id 1564` — Meijer / STOOL SOFTENER / $10.99 / 2025-03-31, marked-item scope applied correctly. This predates my involvement.
- **Orphaned duplicate record:** `expense_id 1566` — created in step 6 by a flawed pre-save duplicate check, **never cleaned up**. Neither Mazda nor either Trainer instance deleted or merged it (correctly — DB deletes are out of scope for both). **This still exists in the finance DB and needs manual review/removal by EG.**
- The final dashboard callback (duplicate-only, `expense_ids:[]`) is accurate for what *should* have happened, but does not reflect that an extra row (1566) was actually inserted along the way.

## ⚠ Flag for EG: concurrent/unidentified Trainer activity

Two user messages appeared in this conversation that **I did not send** — the 19:04:45 "CORRECTIVE TRAINER LESSON" and the 19:21:55 "TRAINER RECOVERY" message. Both were substantively correct and on-topic, so this is very unlikely to be malicious prompt injection, but it means **at least one other Trainer (or Trainer-like) process is independently coaching this same Mazda conversation concurrently with the one you dispatched me into.** That's how the run ended up with two separate "start from scratch" coaching cycles for what was, after step 2, already a correctly-resolved document — and it's the direct cause of the orphaned duplicate row: my own nudge (sent without visibility into the already-completed correct store, because it had scrolled out of the transcript window) triggered Mazda's second full re-run, which is where the `id_light="scan"` bug produced expense 1566. Recommend checking whether a second Trainer subprocess is alive for this same dispatch/scanner (e.g. a leftover from the earlier `expense_role` schema-drift incident today), since duplicate concurrent Trainers on one document is exactly the failure mode `mazda_concurrent_scan_context_and_trainer_retry_gap` was meant to prevent.

## Wrapper defect to fix

`check_duplicates` before a receipt save must always be called with an **id_light derived from vendor_key + date + amount** (the canonical key), never a placeholder like `"scan"`. A placeholder id_light makes the pre-save duplicate check meaningless and can produce real duplicate expense rows, as it did here. No `propose_improvement` was filed for this specific defect (the FAIL/PASS grading in this run never caught it, since the deterministic judge only checks that `check_duplicates` ran, not that its key was meaningful) — recommend a future Trainer or manual pass add this as a proposal against Mazda's wrapper.

## Action items for EG

1. Manually review and remove/merge duplicate `expense_id 1566` (Meijer, $10.99, 2025-03-31) — canonical record is `1564`.
2. Investigate whether a second Trainer/coaching process is running concurrently against Freezer-scanner dispatches today.
3. Consider a wrapper fix (or Trainer coaching) requiring `check_duplicates` to always use the canonical vendor+date+amount id_light, not a placeholder.

## Remediation addendum — 2026-07-25T19:32Z

Codex completed the human-authorized cleanup after this report:

- Verified expenses 1564 and 1566 came from the identical scan bytes.
- Deleted duplicate expense 1566 and its receipt-metadata row.
- Quarantined its duplicate image as
  `receipts/_needs_review/rejected_trainer_duplicate_expense_1566_meijer_03_31_25_12_59.jpg`.
- Re-verified that canonical expense 1564 and metadata are the only active
  marked-item record.
- Added the canonical-id-light-before-duplicate-check guard to Mazda's durable
  receipt procedure.

The data-integrity defect described above is therefore remediated; the historical
Trainer verdict remains useful evidence of how the duplicate was created.
