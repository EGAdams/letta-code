# Trainer Report — Diagnostic (no live Mazda run)

**Scanner:** Freezer Scanner Multi Expense Red Box Diagnosis
**Dispatch:** 2026-07-29T13:01:10.608Z (d1785330070.6089723)
**Mazda conversation:** conv-d6423b25-796b-4359-a5c7-18130a2cee89
**Mode:** Retrospective diagnosis per dispatch instructions — **no Mazda coaching, no expense-data changes.**

## Task as given

> Diagnose missing red box for itemized child expense 1679 amount 19.50 on this exact
> receipt. Original Trainer graded only parent 1678 and only source-document, while
> children 1679-1683 are accessed through receipt_url/View Receipt. Identify the
> wrapper/dashboard contract gap and require a durable system-level fix so every
> itemized child on a multi-expense receipt is individually boxed.

No `judge_trace`/`record_trace` polling was performed — this dispatch is a targeted
code/data diagnosis, not a watch of a fresh intake. I made no writes to the finance
database, no Letta messages to Mazda, and no edits to `expenses` rows. All commands run
were read-only (`GET`/`POST` against the local dashboard's read endpoints, and a local
OCR read of the receipt image already on disk).

## What I checked

1. `POST /api/supporting-documents` for expenses 1678 (parent) and 1679–1683 (children,
   `expense_role=LINE_ITEM`) — all six report `receipt_url` pointing at the same file,
   `jacob_menninga_03_31_25_67_25.jpg`, and all six report `documents[receipt].available:
   true`. `document_url` is empty/`available:false` for every row (this is a `moms_ledger`/
   invoice-by-email screenshot, not a bank statement — there is no separate source
   document, only the one receipt image).
2. `POST /api/open-supporting-document` (`document_type=receipt`) for the same six ids —
   this is the call that actually runs `ExpenseDocumentAnnotationService.prepare()` (via
   `ImageExpenseDocumentAnnotator`) and reports whether a box was drawn:

   | expense_id | role | highlighted | note |
   |---|---|---|---|
   | 1678 | PARENT (total $67.25) | **false** | "No high-confidence expense row was found in the image." |
   | 1679 | LINE_ITEM ($19.50) | **false** | same |
   | 1680 | LINE_ITEM | **false** | same |
   | 1681 | LINE_ITEM | **true** | (boxed) |
   | 1682 | LINE_ITEM | **false** | same |
   | 1683 | LINE_ITEM | **true** | (boxed) |

   So the failure isn't confined to the one child named in the dispatch (1679) or to
   children generally — the **parent itself also fails to box**, and only 2 of 5 line
   items succeed. This contradicts a narrower theory that "only the parent gets
   graded"; the annotator is failing non-deterministically across the whole itemized
   family.
3. Read the source image directly (`readable_documents/receipts/2025/march/march_31/
   jacob_menninga_03_31_25_67_25.jpg`, 2550×3508) and ran the same OCR path
   (`pytesseract.image_to_string`) that `ImageExpenseDocumentAnnotator` uses. The file is
   a **full-page screenshot of an AOL webmail inbox** — subject line, folder list,
   sidebar, "Reply/Reply All/Forward" buttons, etc. all rendered at full scale. The
   actual invoice (Jacob Menninga's freelance-editing invoice to Rosemary, itemized by
   work date: 3/5, 3/19, 3/25×2, plus one more) occupies a small, low-DPI inset in the
   middle of that huge screenshot. OCR output for the surrounding chrome is clean; OCR
   output for the invoice table itself is comparatively degraded (small font relative to
   the 2550×3508 canvas) — exactly the regime where `_line_score` needs a decisive,
   untied match and gets a marginal one instead.

## Root cause (wrapper/dashboard contract gap, not a Mazda defect)

`document_annotation.py`'s `_line_score`/`_best_line` (used identically by every
annotator strategy) was built around **one document → one identity to box**: a receipt
with a single total, or a statement row that repeats its own date next to its own
amount. Itemization breaks that assumption in two independent ways this run exposes:

1. **No sibling awareness.** Each of the six `open-supporting-document` calls
   independently re-OCRs the same image and independently searches for its own
   expense's row, with zero knowledge that five *other* known amounts/dates also belong
   to rows on this exact page. A one-to-one bipartite assignment across all six known
   line items (six amounts, six dates, one shared image) would let the matcher use
   process-of-elimination — a decisive placement for four unambiguous rows tells you the
   fifth candidate region left over is the fifth expense, even if its own line-level OCR
   score is marginal in isolation. Today, each lookup is islanded, so a globally
   resolvable case still fails closed per-row.
2. **Screenshot-of-a-screenshot resolution.** `ImageExpenseDocumentAnnotator` OCRs the
   full page as delivered. When the evidentiary content (the invoice table) is a small
   fraction of a much larger captured page, OCR fidelity on that sub-region degrades
   even though the rest of the page OCRs cleanly — the annotator has no logic to detect
   "the content of interest is a small dense region" and crop/upscale before re-OCRing
   it. A table-anchor crop (locate a header row like "Description Rate Amount" once,
   crop tightly to that block plus margin, re-run OCR at higher effective DPI on just
   that crop) is a standard fix for this exact failure mode and would very likely turn
   the 4 currently-failing rows into confident matches without changing any matching
   thresholds.

Neither of these is a data problem — the parent's own row (total $67.25, which is
printed plainly once near "INJTM2503"/date) also fails, which means this is not simply
"line items are hard," it's that the whole page's effective OCR resolution for the
invoice block is marginal, and the per-row matcher has no way to recover from that in
isolation.

## Why this is not a Mazda coaching issue

Every one of the six expenses already carries a correct, non-empty `receipt_url`
pointing at the one true source image, and `available: true` is reported correctly by
`_supporting_document_descriptors` for all six (the descriptor only checks that the
reference resolves to a viewable file — it is not itself wrong). The defect is entirely
inside `document_annotation.py`'s per-request OCR/match/box pipeline, which is server
code, not anything Mazda's intake transcript did or didn't call. There is nothing to
coach in this conversation, and I made no correction message to Mazda.

## Recommended durable fix (not applied — flagging per instructions)

- Give `ExpenseDocumentAnnotationService.prepare()` (or a new sibling-aware entry point)
  the full set of `ExpenseEvidence` for an itemized family (parent + all `LINE_ITEM`
  children sharing one `receipt_url`) instead of one `ExpenseEvidence` at a time, and do
  a single OCR pass + one-to-one assignment across all candidate rows and all known
  amounts/dates, falling back to today's single-evidence path for non-itemized expenses.
- In `ImageExpenseDocumentAnnotator.annotate`, detect when OCR confidence/word density in
  the region the top candidates cluster in is low relative to the full image, and retry
  with a cropped + upscaled re-OCR of that region before giving up.
- Until one of these lands, `open-supporting-document`'s current fail-closed behavior
  (no box, explicit `highlight_note`) is the correct interim behavior — it never boxes
  the wrong row, it just under-boxes true rows on this class of low-fidelity
  screenshot-style receipt.

## Verdict

**FAIL (dashboard/annotation defect, confirmed and diagnosed).** Not a Mazda wrapper or
intake-transcript failure — no `propose_improvement`/coaching sent. Human/dev follow-up
needed on `dashboard/document_annotation.py`'s itemized-family and low-fidelity-crop
handling described above.
