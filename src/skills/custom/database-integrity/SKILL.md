---
name: database-integrity
description: Investigates missing or inconsistent expense rows after process.py runs. Use when id_light rows are missing or suspected duplicates.
---

# Database Integrity Checks

## When to use
- After a process.py run shows skipped duplicates but rows are missing in DB
- When id_light rows are missing or suspect duplicates

## What it does
- Reads last_process_run.json
- Verifies each skipped/inserted id_light exists exactly once
- Reports missing rows and duplicates

## Run (one step)
```bash
source /home/adamsl/rol_finances/.venv/bin/activate && \
python3 /home/adamsl/letta-code/src/skills/custom/database-integrity/scripts/check_integrity.py
```

## HTML integrity report (all expenses)
```bash
source /home/adamsl/rol_finances/.venv/bin/activate && \
python3 /home/adamsl/letta-code/src/skills/custom/database-integrity/scripts/make_id_light_integrity_report.py
```

Output:
- /home/adamsl/rol_finances/reports/id_light_integrity_report_{ timestamp }.html

## Fix mismatches from integrity report
### Dry-run:
Use the integrity report from the previous step.
```bash
source /home/adamsl/rol_finances/.venv/bin/activate && \
python3 /home/adamsl/letta-code/src/skills/custom/database-integrity/scripts/fix_id_light_mismatches.py \
  --report /home/adamsl/rol_finances/reports/id_light_integrity_report_{ timestamp }.html
```

### Apply (interactive confirmations + YAML/LLM fallback):
```bash
source /home/adamsl/rol_finances/.venv/bin/activate && \
python3 /home/adamsl/letta-code/src/skills/custom/database-integrity/scripts/fix_id_light_mismatches.py \
  --report /home/adamsl/rol_finances/reports/id_light_integrity_report_{ timestamp }.html \
  --apply
```

Flow:
1) YAML (`id_lite.yaml`) candidate
2) Report candidate (if different)
3) LLM vendor_key fallback (Gemini flash-lite)
4) Manual entry

Output:
- /home/adamsl/rol_finances/reports/id_light_mismatch_fix_preview_{ timestamp }.txt

## Added checks (2026-03-06)
- Detects id_light mismatches by vendor key drift (store numbers, location noise).
- Shows similar rows by vendor_key and by (date, amount) to explain duplicates.
- Helps decide whether to rewrite id_light generation.

## Added checks (2026-03-06)
- Uses GenerateIDLight as canonical id_light source.
- Detects vendor_key drift and shows similar rows by vendor/date+amount.
