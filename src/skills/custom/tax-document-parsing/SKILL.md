---
name: tax-document-parsing
description: Parse tax document folders with Gemini CLI (OAuth), cache meta-text/fields, and route to the IRS tax document router.
---

# Tax Document Parsing (Gemini CLI)

Use this skill for scanned tax documents stored under:
`/home/adamsl/rol_finances/readable_documents/tax_documents/<folder>/`

## What it does
- Runs Gemini CLI (OAuth) to extract structured fields and meta-text.
- Writes/refreshes:
  - `extracted_fields.json`
  - `detail.md`
  - `summary.md`
  - `routing_payload.json`
- Auto-routes to `irs-tax-document-router` with the routing payload.

## Requirements
- Gemini CLI installed and authenticated via OAuth (`gemini` on PATH).
- No GEMINI_API_KEY required.

## Usage

### Parse a single folder
```bash
python3 /home/adamsl/letta-code/src/skills/custom/tax-document-parsing/scripts/parse_tax_doc.py \
  --folder /home/adamsl/rol_finances/readable_documents/tax_documents/form_1040-SR_front_4
```

### Parse by file path
```bash
python3 /home/adamsl/letta-code/src/skills/custom/tax-document-parsing/scripts/parse_tax_doc.py \
  --file /home/adamsl/rol_finances/readable_documents/tax_documents/form_1040-SR_front_4/form_1040-SR_front_4.jpg
```

### Options
- `--gemini-timeout <sec>` (default: 120)
- `--gemini-model <name>` (repeatable)
- `--skip-route` (parse only, no routing)
- `--route-timeout <sec>` (default: 30)

## Notes
- The script **fails** if Gemini CLI is unavailable.
- Override router agent with `IRS_TAX_ROUTER_AGENT_ID` env var if needed.
- Routing uses the IRS routing payload contract (see `irs-tax-document-routing` skill).
