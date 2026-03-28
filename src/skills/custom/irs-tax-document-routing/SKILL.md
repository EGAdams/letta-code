---
name: irs-tax-document-routing
description: Routes IRS tax documents (including Form 9325 acknowledgements) to specialist IRS agents instead of receipt/expense ingestion. Use when classification indicates IRS/tax content or routing_key tax.irs_*.
---

# IRS Tax Document Routing

Use this skill when a scanned/ingested file appears to be an IRS tax document.

## Trigger conditions
- classifier returns `routing_key` starting with `tax.irs_`
- document contains IRS language (Internal Revenue Service, Form 9325)

## Folder structure contract
- Store tax documents under:
  - `/home/adamsl/rol_finances/readable_documents/tax_documents/<document_folder>/`
- Each document folder should contain:
  - primary scan file (jpg/jpeg/png/pdf)
  - `summary.md`
  - `detail.md`
  - `routing_payload.json`
  - `extracted_fields.json`
- Keep an index file at:
  - `/home/adamsl/rol_finances/readable_documents/tax_documents/INDEX.md`
  to track current folder/file mappings.
- For multi-side pages, use pairing folders such as:
  - `form_9325_front_2`
  - `form_9325_back_2`

## Routing policy
1. Do **not** route IRS tax docs into receipt/expense insertion.
2. Route to `irs-tax-document-router` agent.
3. For Form 9325, route to `irs-form-9325-expert`.
4. Reuse existing IRS agents; only create new specialist agents when a newly scanned form requires dedicated handling.

## Markdown output contract (JSON-friendly)
### summary.md
- `# Document Summary`
- `## Identity`
- `## Classification`
- `## Filing Period`
- `## Key Flags`
- `## One-line Description`

### detail.md
- `# Document Detail`
- `## Identity`
- `## Source Files`
- `## OCR and Parsing Metadata`
- `## Parties`
- `## Filing / Tax Year Data`
- `## Numeric Fields`
- `## IDs and References`
- `## Date Fields`
- `## Calculation Inputs`
- `## Calculation Notes`
- `## Data Quality Warnings`
- `## OCR Preview`

Use machine-friendly `key: value` lines where possible for future `.json` conversion.

## Calculation-grade extraction requirement
Before routing is considered complete, run:

```bash
/home/adamsl/planner/.venv/bin/python /home/adamsl/rol_finances/tools/tax_docs/extract_tax_document_fields.py --folder <document_folder_path>
```

This generates/refreshes:
- `extracted_fields.json` (source of truth for numbers, checkbox states, ids, dates)
- `detail.md` (human-readable mirror of extracted JSON)
- `summary.md`

Important: Do not rely on placeholder metadata for calculation workflows.

## Naming hygiene
- Prefer `form_<FORM>_<front|back>_<n>` when form identity is known.
- Use OCR confirmation before locking a form number in folder/file names.
- Correct mismatches immediately (example: `1024-SR` -> `1040-SR` when OCR confirms 1040-SR).

## Handoff payload shape
Use a structured payload with:
- file path
- sha256 (if available)
- routing key
- confidence
- classification reasons

## Helper script
Use `scripts/route_irs_tax_doc.py` to emit a normalized payload for routing.
