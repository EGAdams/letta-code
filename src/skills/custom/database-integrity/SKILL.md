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

## Added checks (2026-03-06)
- Detects id_light mismatches by vendor key drift (store numbers, location noise).
- Shows similar rows by vendor_key and by (date, amount) to explain duplicates.
- Helps decide whether to rewrite id_light generation.

## Added checks (2026-03-06)
- Uses GenerateIDLight as canonical id_light source.
- Detects vendor_key drift and shows similar rows by vendor/date+amount.
