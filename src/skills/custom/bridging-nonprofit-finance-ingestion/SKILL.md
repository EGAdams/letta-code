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
