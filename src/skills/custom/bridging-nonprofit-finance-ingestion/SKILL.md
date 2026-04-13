---
name: bridging-nonprofit-finance-ingestion
description: Runs nonprofit_finance_db ingestion from rol_finances through a bridge wrapper so code is not copied between repos. Use when the user asks to classify or ingest a scanned statement/receipt/tax file from the rol_finances project.
---

# Bridging nonprofit_finance ingestion

Use this skill to run ingestion/classification in `nonprofit_finance_db` from `rol_finances`.

## When to use
- User asks to classify a scanned file from `rol_finances/tools/scan.jpg`.
- User asks to ingest a statement/receipt/tax file while keeping repos separate.

## Command
Run:

```bash
bash /home/adamsl/letta-code/src/skills/custom/bridging-nonprofit-finance-ingestion/scripts/bridge_ingest.sh <file_path> [options]
```

## Common examples

Classify only:

```bash
bash /home/adamsl/letta-code/src/skills/custom/bridging-nonprofit-finance-ingestion/scripts/bridge_ingest.sh \
  /home/adamsl/rol_finances/tools/scan.jpg \
  --org-id 1 --force auto --receipt-engine openai --dry-classify
```

Full run:

```bash
bash /home/adamsl/letta-code/src/skills/custom/bridging-nonprofit-finance-ingestion/scripts/bridge_ingest.sh \
  /home/adamsl/rol_finances/tools/scan.jpg \
  --org-id 1 --force auto --receipt-engine openai
```

## Behavior expectations
- Statement docs follow statement ingestion path.
- Receipt docs follow receipt ingestion path.
- IRS/tax docs route to IRS specialist pipeline and do not insert as receipt/expense.

## Mom ledger routing lane
If a scanned page is identified as a mom-ledger/check-history page (printed bank web ledger used as checkbook history):

1. Route first to `moms-ledger-parser` for row extraction and normalization.
2. Extract transaction rows with statement-like fields (date, description/payee, amount, check number, references, running balance when present).
3. After parse output is produced, process through the same downstream flow used for bank statements.

This lane is intended to avoid misclassifying ledger pages as receipt content while preserving statement-grade transaction ingestion behavior.

## Runtime caveat: image-read capability by execution environment

In some Letta subagent runtimes, direct image reading is unavailable (error like "server does not support images in tool responses").

When this happens:
1. Keep routing decision as `statement.moms_ledger`.
2. Use local OCR fallback (`tesseract`) to extract text.
3. Produce transaction JSON with explicit `confidence`, `warnings`, and `evidence` per row.
4. Save under:
   - `/home/adamsl/rol_finances/readable_documents/ledger_documents/<page_folder>/`

Example fallback command:

```bash
tesseract /home/adamsl/rol_finances/tools/scan.jpg stdout --dpi 300
```

Do not fabricate unreadable fields; set `null` and add warnings.

## Tax document follow-up workflow
After tax classification, place file in:
- `/home/adamsl/rol_finances/readable_documents/tax_documents/<document_folder>/`

Then ensure folder contains:
- primary scan file
- `summary.md`
- `detail.md`
- `routing_payload.json`
- `extracted_fields.json`

Keep `/home/adamsl/rol_finances/readable_documents/tax_documents/INDEX.md` updated as a quick inventory.

Run calculation-grade extraction after scan/file placement:

```bash
/home/adamsl/planner/.venv/bin/python /home/adamsl/rol_finances/tools/tax_docs/extract_tax_document_fields.py --folder <document_folder_path>
```

This step is required so critical numbers and checkbox states are persisted without rereading documents later.

For Form 9325 page-pair workflow, use folder pairs like:
- `form_9325_front_2`
- `form_9325_back_2`

Markdown should follow standardized headings used by IRS routing skill so later JSON conversion is straightforward.
