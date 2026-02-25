---
name: receipt-parse-html-report
description: "Generates receipt parse HTML reports from scanned receipts, optionally highlighting anomalies. Use when the user asks for a receipt parse report, receipt parsing summary, HTML receipt report, or wants to flag missing merchant/date/total/raw snippet data."
---

# Receipt Parse HTML Report

## Overview
Generate a receipt parse HTML report (same format as `receipt_parse_sample_3_*.html`) using the local receipt parser. Optionally highlight rows with anomalies (missing merchant/date/total/raw snippet).

## Quick start
Run the script with an optional subdirectory and anomaly highlighting:

```bash
python3 /home/adamsl/letta-code/src/skills/custom/receipt-parse-html-report/scripts/make_receipt_parse_report.py \
  --subdir january/january_16 \
  --limit 25 \
  --anomalies
```

The report is saved under:
`/home/adamsl/rol_finances/readable_documents/reports/receipt_parse_sample_3_<timestamp>.html`

To parse specific receipt files (local path or file:// URL) and emit a JSON summary:

```bash
python3 /home/adamsl/letta-code/src/skills/custom/receipt-parse-html-report/scripts/make_receipt_parse_report.py \
  --file file://wsl.localhost/Ubuntu-24.04/home/adamsl/rol_finances/readable_documents/receipts/2024/december_06/gk_12_06_24_8_06.jpeg
```

## Workflow
1. Choose a receipts folder (`--subdir`) or default to the receipts root.
2. Parse receipts with `parse_and_categorize.py` (local engine, JSON output).
3. Build the HTML report with the standard columns and tooltips.
4. (Optional) Highlight anomalies with `--anomalies`.

## Options
- `--file <path-or-url>`: Receipt file path or file:// URL (repeatable). When supplied, overrides `--subdir`.
- `--subdir <path>`: Relative to `/home/adamsl/rol_finances/readable_documents/receipts`.
- `--limit <n>`: Limit the number of receipts parsed.
- `--anomalies`: Adds an “Anomalies” + “Anomaly Details” column and highlights rows with missing merchant/date/total/raw snippet (default when not provided).
- `--include-missing-id-light`: Include receipts that do not provide id_light (default is to skip them).
- `--summary-json`: Emit a JSON summary of parsed rows to stdout.
- `--summary-markdown`: Emit a markdown table summary of parsed rows to stdout (default when no summary flag is provided).

## Notes
- The report format matches the existing receipt parse sample HTML files.
- Use anomalies to quickly find noisy OCR or incomplete parses.
- Merchant-quality checks are included (too short, low alphabetic content, junk phrases like “Today on AOL”).
- Extend anomaly detection by updating `get_anomaly_flags()` in the script.
