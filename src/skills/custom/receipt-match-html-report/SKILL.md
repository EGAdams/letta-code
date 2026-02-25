---
name: receipt-match-html-report
description: Generate a styled HTML receipt match verification report from the TSV export (id, id_light, receipt_url).
---

# Receipt Match HTML Report

## Overview
Generates a clean HTML report from the receipt match TSV for easy review in a browser or VS Code Live Server.

## Inputs
- TSV file with columns: `id`, `id_light`, `receipt_url`

## Output
- HTML file with title, purpose, table, and next-step instructions.

## Usage
Run the script below (inside WSL):

```bash
python /home/adamsl/letta-code/src/skills/custom/receipt-match-html-report/scripts/make_receipt_match_html.py \
  /home/adamsl/rol_finances/reports/receipt_match_report_20260223_000256.tsv \
  /home/adamsl/rol_finances/reports/receipt_match_report_20260223_000256.html
```

## Notes
- Open HTML in VS Code with Live Server for easy review.
- If you see odd characters, ensure plain ASCII punctuation (e.g., use `5-10`, not an en dash).
- Receipts should follow the standard filename format:
  `<vendor>_MM_DD_YY_<amount_dollars>_<amount_cents>.<ext>`
- Raw snippet cells can include hover tooltips with Vendor Key + ID Lite to avoid adding more columns.
- Tooltip pattern: use `<td class="tooltip" data-tooltip="Vendor Key: ...\n\nID Lite: ...">` and CSS `.tooltip:hover::after` with `white-space: pre-line`.