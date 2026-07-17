# Trainer Report — PDF intake (February-March Fifth Third 6285 (2025))

- **Document**: `/home/adamsl/rol_finances/readable_documents/bank_statements/february/february_march_fifth_third_6285_2025.pdf`
- **Scanner/source**: PDF intake (not a physical scan)
- **Dispatch**: 2026-07-16T21:53:05Z
- **Conversation**: `conv-6f48aa9d-2e3c-4b22-a5d8-337e1f53d45e`
- **Verdict**: **FAIL** (corrected as far as possible — see below)

## Step-by-step evidence

| Step | Status | Evidence |
|---|---|---|
| `load_wrapper_revision` | ✅ | Loaded `wrap-v022` at 21:53:11 |
| Classify | ✅ | `classify_scan.py` (vision fallback, text extraction failed on missing `PyPDF2`) → `doc_type=bank_statement`, `merchant=Fifth Third Bank`, `confidence=1.0` |
| Run `parse_statement_scan.py` / `store_statement_transactions.py` (wrapper Rule 1) | ❌ then ✅ (after coaching) | First attempt: **skipped entirely**. Mazda instead tried raw `python3` scripts importing `fitz`/`pypdf`, both `ModuleNotFoundError` (neither library exists anywhere in this environment, confirmed independently). She then web-searched and grepped old reports instead of calling the documented script. |
| `record_trace` (first) | ✅ (but premature) | Trace 95, `agent_output` blamed missing PDF libraries instead of noting the correct script was never tried |
| `judge_trace` (first) | ✅ | Trace 95 → FAIL / `unsupported_document`, all 6 checklist items failed |
| `propose_improvement` | ❌ initially, ✅ after coaching | Not called after the first FAIL (contract violation). Filed as proposal 76 after coaching, referencing trace 95. |
| Dashboard `/api/expense-stored` callback | ❌ initially, ✅ after coaching | Not sent on the first pass. Sent after coaching with `stored:0`, empty id lists, and the real error. |
| `record_trace` (final) | ✅ | Trace 96, accurate final-state evidence |
| `judge_trace` (final) | ✅ | Trace 96 → FAIL / `unsupported_document` (unavoidable — see root cause) |

## Wrapper defect diagnosed

Mazda's own active wrapper (Rule 1, wrap-v022) explicitly requires running
`parse_statement_scan.py` + `store_statement_transactions.py` for bank-statement
documents before `record_trace`. On the first pass she never called either script —
she went straight to ad-hoc `fitz`/`pypdf` extraction with plain `python3` (not even
the rol_finances venv), which can never work: verified independently that
`PyPDF2`, `pypdf`, `fitz`, and `pdfplumber` are **all absent from the rol_finances venv**
in this environment. She then spent several tool calls web-searching and grepping old
reports instead of reading/following her own wrapper instructions.

## Coaching given (2 corrective messages)

1. Told her to run the documented `parse_statement_scan.py` (Gemini-vision based, does
   not need fitz/pypdf/PyPDF2) via `executor_run` with the rol_finances venv, then
   `store_statement_transactions.py`, then re-fire trace/judge/propose_improvement.
2. After she discovered the real blocker (all vision providers down), told her to still
   fire the `/api/expense-stored` callback with `stored:0` and record/judge a final
   accurate trace, since the always-fire rule applies to no-store outcomes too.

Mazda responded correctly to both messages: retried via the correct script (confirming
the wrapper-usage defect was real and fixable), filed proposal 76 for trace 95, sent the
dashboard callback, and recorded/judged a final trace (96).

## Root cause of the persisting FAIL — infrastructure, not Mazda

After correcting her tool usage, `parse_statement_scan.py` itself failed for a reason
outside Mazda's control: **all three configured vision providers are currently
unusable**:
- Gemini: `429 ResourceExhausted` — free-tier daily quota (20 requests) exhausted for
  `gemini-3-flash`.
- ChatGPT OAuth fallback: rejects `application/pdf` MIME type in `image_url` content.
- OpenAI: no `OPENAI_API_KEY` configured.

This document cannot be parsed until one of these is restored (wait for Gemini quota
reset, or fix the ChatGPT-OAuth PDF path, or add an OpenAI key). This is an
infrastructure gap in `parse_statement_scan.py`'s multi-provider fallback, not a wrapper
instruction problem — flagging for a human to look at.

## For a human to check

- **Gemini quota**: confirm today's free-tier usage/reset time; consider a paid tier or
  request throttling across concurrent scanner/PDF intakes so 20/day isn't burned by
  retries.
- **`parse_statement_scan.py` PDF→ChatGPT path**: it currently sends the raw PDF as an
  `image_url`, which OpenAI rejects — this fallback is effectively dead for PDF
  statements (only useful for JPEG scans) unless it's changed to convert page images
  first.
- Proposal 76 is pending review in the self-improvement evidence store (trace 95, task
  `document-intake`).

## Summary

Mazda initially violated her own wrapper's Rule 1 by skipping the documented
`parse_statement_scan.py`/`store_statement_transactions.py` pipeline in favor of
unsupported ad-hoc PDF library calls, and skipped `propose_improvement` and the
dashboard callback after her first FAIL — a real wrapper-usage defect, since corrected
via a filed proposal (76) and a completed trace/judge/callback cycle. However, the
document itself could not be stored even after correction because every configured
vision provider for statement parsing is currently unavailable (Gemini quota exhausted,
ChatGPT OAuth rejects PDF input, no OpenAI key) — an infrastructure gap requiring human
attention, not a further Mazda lesson.
