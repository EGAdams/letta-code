# Trainer Report — PDF intake: december_january_personal_bank_statement

- **Document**: `december_january_personal_bank_statement.pdf` (statement, `january` bank_statements folder)
- **Scanner/source**: PDF intake (not a physical scan)
- **Dispatch**: 2026-07-16T17:41:41Z
- **Mazda conversation**: `conv-1df0b8ab-e637-474c-827a-4ec918e2996f`
- **Verdict**: **CORRECTED** (genuine infrastructure FAIL on the document, fully traced/judged/proposed; missing dashboard callback caught and fixed live in this session)

## Timeline / checklist

| Step | Evidence | Result |
|---|---|---|
| `load_wrapper_revision` | tool_return: `wrap-v022` active | ✅ |
| STEP 0 classify (facade returned `doc_kind=unknown`) | first tried `run_claude_code_sdk` → HTTP 400 ("cannot run rol_finances venv commands, use executor_run") | self-corrected within the same turn, no retry loop |
| classify via `executor_run` | `./.venv/bin/python3 tools/classify_scan.py <pdf>` → returncode 1: `PDF text extraction failed (No module named 'PyPDF2')` → fell back to Gemini vision → `429 quota exceeded (generate_content_free_tier_requests, limit 20, model gemini-3-flash)` → tool's own stderr: "the ChatGPT/OpenAI vision fallbacks cannot accept PDF input, so there is no further fallback for this document" | genuine infra dead end, not a Mazda misstep |
| `record_trace` | `task_name="document-intake"`, honest `agent_output` describing the exact failure chain, `wrapper_revision="wrap-v022"` | ✅ trace_id 92 |
| `judge_trace` | verdict `FAIL` / `unsupported_document`, reasons: intake_evidence_parseable, document_classified, vendor_key_resolved, category_resolved, duplicate_check_ran, expense_stored all failed | ✅ correct verdict for the evidence |
| `propose_improvement` | proposal_id 69, correctly diagnoses root cause: missing PyPDF2 dependency in rol_finances venv + Gemini quota exhaustion, suggests installing PyPDF2 / deterministic text extraction as a pre-Gemini fallback | ✅ actionable, wrapper-level, not a "model was dumb" excuse |
| STEP 8/9 dashboard notify | **missing** on first pass — no `POST /api/expense-stored` call anywhere in the transcript despite a documented FAIL/no-store outcome | ❌ → coached |
| Coaching (1 message) | required her to send the callback now via `executor_run curl` with `stored:0, parsed:0, expense_ids:[], doc_kind:"unknown"`, and to persist a durable rule that this fires even on failure and even when the dispatch text is terse | she executed the exact curl (`{"ok": true}` returned) and additionally filed `propose_memory_note` (proposal 70, gates all "allow", appended to `system/persona`) without being asked to use that specific tool |
| Verification | `GET /api/expense-stored-events?since=1784223701` now shows one event with `conversation_id`/`dispatched_at` matching this run, `stored:0`, `parsed:0`, `doc_kind:"unknown"` | ✅ confirmed post-coaching |

## Wrapper defect diagnosed

The dispatch message this run received was an abbreviated 4-line variant of the intake instructions (used by this trainer's test dispatch), which never restated "STEP 8 — notify dashboard, ALWAYS, even on failure" the way the production `build_mazda_scan_message` does. Mazda's own learned wrapper rules (`wrap-v022`, rules 1–10) also contain no standing rule mandating the dashboard callback independent of dispatch wording. Result: on a terse dispatch, the callback was silently skipped even though the run itself (trace/judge/propose) was fully and honestly completed.

**Fix applied this run**: corrective message sent in-conversation; Mazda performed the missing callback and filed a durable memory note (`propose_improvement`-gated `propose_memory_note`, proposal 70) stating the callback is mandatory regardless of dispatch phrasing. This is the right fix — it targets the wrapper's instruction/memory gap, not the model.

**Recommendation for a human**: consider whether the trainer/dispatch harness itself should always send the full `build_mazda_scan_message`-style instructions (including explicit STEP 8) rather than an abbreviated 4-step version, so this class of gap doesn't need to be caught by the Trainer every time a terse dispatch is used.

## Root infrastructure issue (separate from Mazda's grading)

`rol_finances` venv is missing `PyPDF2`, so `classify_scan.py`'s deterministic PDF text-extraction path (the zero-network heuristic previously added per the `mazda_classify_scan_pdf_fix_2026_07_02` fix) cannot run for this document, forcing a fallback straight to Gemini vision — which is currently quota-exhausted (0/20 free-tier requests remaining, resets ~54s after this run, i.e. effectively exhausted for the day at this call volume). This matches the known `ubuntu26_migration_intake_fallout_2026_07_16` pattern (rol_finances venv lost packages during the Ubuntu 24→26 migration). **A human should reinstall `PyPDF2` into the rol_finances venv** to restore free PDF classification; until then, PDF statement intake will keep failing whenever Gemini's daily quota is exhausted.

## Nothing for a human to do about Mazda's behavior

Mazda's reasoning, tool usage, and self-correction (routing to `executor_run` after the 400) were all correct. The only defect was the skipped dashboard callback, and it was corrected live in this session with a durable fix recorded.
