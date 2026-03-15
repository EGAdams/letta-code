---
name: process-run-duplicate-check
description: Summarizes the last e_two_e_processing.process run and checks inserted id_light rows for duplicates. Use after running process.py or when asked to verify duplicates from the last run.
---

# Process Run Duplicate Check

## When to use
- After running `python3 -m e_two_e_processing.process ...`
- When asked to verify duplicates or confirm inserts from the last run

## What it does
- Reads `events/logs/last_process_run.json`
- Verifies inserted `id_light` rows exist
- Flags any duplicates (count > 1)
- Prints a short summary

## Run (one step)
```bash
source /home/adamsl/rol_finances/.venv/bin/activate && \
python3 /home/adamsl/letta-code/src/skills/custom/process-run-duplicate-check/scripts/check_last_process_run.py
```

## Output
- Summary counts
- Missing inserted ids (if any)
- Duplicate ids (if any)
