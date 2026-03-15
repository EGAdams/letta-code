---
name: db-integrity-agent
description: Runs the db_integrity_agent CLI to generate id_light integrity reports, apply mismatch fixes, and record summaries. Use when validating database integrity, id_light mismatches, or when asked to run the DB integrity agent.
---

# DB Integrity Agent

## Quick start (dry-run)
```bash
env PATH=/home/adamsl/rol_finances/.venv/bin:${PATH:-/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/bin} \
  python -m tools.db_integrity_agent.cli run --dry-run
```

## Apply fixes (non-interactive)
```bash
env PATH=/home/adamsl/rol_finances/.venv/bin:${PATH:-/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/bin} \
  python -m tools.db_integrity_agent.cli run --auto-accept-yaml --auto-accept-vendor
```

## Options
- `--summary-dir` (default: `/home/adamsl/rol_finances/reports`)
- `--history-path` (default: `/home/adamsl/rol_finances/reports/db_integrity_strategy_history.json`)
- `--report-script-path` (default: `/home/adamsl/letta-code/src/skills/custom/database-integrity/scripts/make_id_light_integrity_report.py`)
- `--fixer-script-path` (default: `/home/adamsl/letta-code/src/skills/custom/database-integrity/scripts/fix_id_light_mismatches.py`)
- `--dry-run`, `--auto-accept-yaml`, `--auto-accept-vendor`

## Prereqs
- DB creds in `/home/adamsl/planner/.env` (`DB_HOST`, `DB_PORT`, `NON_PROFIT_USER`, `NON_PROFIT_PASSWORD`, `NON_PROFIT_DB_NAME`)
- `vendor_category.yaml` at `/home/adamsl/rol_finances/tools/categorizer/vendor_category.yaml`
- Reports dir `/home/adamsl/rol_finances/reports` writable

## Outputs
- Summary: `/home/adamsl/rol_finances/reports/db_integrity_summary_<timestamp>.md` (printed to stdout)
- History: `/home/adamsl/rol_finances/reports/db_integrity_strategy_history.json`
- Fix preview: `/home/adamsl/rol_finances/reports/id_light_mismatch_fix_preview_<timestamp>.txt`

## Notes
- The fixer runs only when **not** `--dry-run`.
- For non-tty runs, use the auto-accept flags to avoid prompts.
