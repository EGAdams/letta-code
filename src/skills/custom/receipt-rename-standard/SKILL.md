---
name: receipt-rename-standard
description: Rename receipt files to the standard <vendor>_MM_DD_YY_<dollars>_<cents> format using parsed date/total.
---

# Receipt Filename Standardization

## Overview
Renames receipt files that do **not** follow the standard format:
`<vendor>_MM_DD_YY_<amount_dollars>_<amount_cents>.<ext>`

## Inputs
- Receipt directory (default: `/home/adamsl/rol_finances/readable_documents/receipts`)
- Receipt parser: `parse_and_categorize.py` (local engine)

## Output
- Renamed files (in-place)
- CSV/HTML report summarizing changes, skips, and errors

## Usage
```bash
python /home/adamsl/letta-code/src/skills/custom/receipt-rename-standard/scripts/rename_receipts.py \
  --root /home/adamsl/rol_finances/readable_documents/receipts \
  --execute
```

## Notes
- If a filename already contains a valid date/amount, it is normalized.
- If missing, the script parses the receipt and uses the parsed date/total.
- Collisions are skipped and logged (no overwrites).