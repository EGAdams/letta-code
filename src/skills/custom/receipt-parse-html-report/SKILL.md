---
name: receipt-parse-html-report
description: "Generates receipt parse HTML reports from scanned receipts, optionally highlighting anomalies. Use when the user asks for a receipt parse report, receipt parsing summary, HTML receipt report, or wants to flag missing merchant/date/total/raw snippet data."
---

# Receipt Parse HTML Report

## Overview
Generate a receipt parse HTML report (same format as `receipt_parse_sample_3_*.html`) using the shared receipt parser module under `receipt_scanning_tools/receipt_parsing_tools`. Optionally highlight rows with anomalies (missing merchant/date/total). Raw OCR snippets are intentionally omitted for receipts (they remain important for bank/credit card statements).

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
2. Parse receipts via the shared parser module (`parse_and_categorize.py`) using the requested engine (default: `auto`).
3. Build the HTML report with the standard columns and tooltips.
4. (Optional) Highlight anomalies with `--anomalies`.

## Options
- `--file <path-or-url>`: Receipt file path or file:// URL (repeatable). When supplied, overrides `--subdir`.
- `--subdir <path>`: Relative to `/home/adamsl/rol_finances/readable_documents/receipts`.
- `--limit <n>`: Limit the number of receipts parsed.
- `--anomalies`: Adds an “Anomalies” + “Anomaly Details” column and highlights rows with missing merchant/date/total, plus total mismatch checks (default when not provided). When anomalies are present, the report runs a second-engine parse (Gemini/OpenAI) for comparison.
- `--include-missing-id-light`: Include receipts that do not provide id_light (default is to skip them).
- `--engine`: Parser engine to use (`auto`, `gemini`, `openai`, `local`). Default is `auto`.
- `--summary-json`: Emit a JSON summary of parsed rows to stdout.
- `--summary-markdown`: Emit a markdown table summary of parsed rows to stdout (default when no summary flag is provided).

## Notes
- The report format matches the existing receipt parse sample HTML files.
- Use anomalies to quickly find noisy OCR or incomplete parses.
- Merchant-quality checks are included (too short, low alphabetic content, junk phrases like “Today on AOL”).
- Extend anomaly detection by updating `get_anomaly_flags()` in the script.
- Each run writes a log file under `.../readable_documents/reports/logs/` with per-receipt progress and errors.
- OpenAI model can be overridden with `OPENAI_RECEIPT_MODEL` (default: gpt-4o-mini).
