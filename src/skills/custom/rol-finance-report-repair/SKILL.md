---
name: rol-finance-report-repair
description: Run the automated ROL Finance report-repair loop that finds the next red (broken report.html) or yellow (uncategorized expense) month tab on the live dashboard and drives it to green — or stops and asks a human when it can't. Use this to process report month tabs end to end, not just to audit one report by hand.
---

# ROL Finance Report Repair

Orchestrates `dashboard/report_repair/` (navigator + workflow + blocker
dialog) against the live dashboard. It walks month tabs in visual order,
auto-fixes only when it has ≥90% confidence in both the diagnosis and the
fix, and otherwise shows an explicit OK / YES-NO blocker and waits for a
human answer. Read `~/rol_finances/tools/python_tasks/verification_lib/
REPORT_OUTPUT_CONTRACT.md` before building or repairing any report.html —
this skill is the driver loop, not a substitute for the
`rol-finance-report-verification-audit` skill's checklist.

## What red vs. yellow means

- **Red** (`report-missing` tab class) = at least one of that month's
  `report.html` cards is missing or fails verification. This is a document
  problem — a statement wasn't built, or was built wrong.
- **Yellow** = the month's own report cards are fine, but the *most
  recently scanned expense* in that month is still uncategorized. This is a
  categorization decision, not a document problem.
- A month can only be yellow if it has no red report inside it — the loop
  always finds a broken report card before it ever looks at the month's own
  yellow/green expense signal (`report_repair/navigator.py`'s
  `next_unhealthy`).

## Current priority: reds for the year first, yellows after

Run with `--skip-yellow-months` so yellow month tabs are passed over
instead of stopping the whole run — they're waiting on a specific person
(mom) to categorize an expense in person, not something to guess at. Do
**not** invent a category to turn a yellow tab green; leave it uncategorized
and gray, exactly as `_fetch_month_status` already reports it.

```bash
cd ~/letta-code/dashboard/tests
../.venv/bin/python rol_finance_reports_repair_browser_test.py --skip-yellow-months
```

Once every red tab this pass is a missing `report.html` (the common case —
`_month_broken_report_label` reports the review/fail case too, but a fresh
month is far more often just never built yet), re-run **without**
`--skip-yellow-months` only when told to start working the yellow queue.

Useful flags: `--dashboard-url` (defaults to the live box,
`http://100.102.209.100:8765`), `--finance-root` (defaults to
`~/rol_finances`), `--confidence` (default `0.90`, don't lower it),
`--max-repairs`, `--headless` (only if no one needs to see/answer a
blocker — usually leave this off).

## Reading the emitted lines

The script prints one line per step to stdout (`emit`, default `print`):

- `NEXT <month> -> <tab> (report|month)` — what it picked next, in order.
- `SKIPPED <tab>: yellow ... left for manual review` — only with
  `--skip-yellow-months`; the loop moved on without touching that expense.
- `AUTO <tab>: expense <id> -> <category>; evidence=...` — it found two
  unanimous exact-description/exact-amount precedents and recategorized on
  its own (yellow-tab repair path, still gated at 90%).
- `BLOCKED <tab>: <problem>` followed by a real OK/YES-NO dialog on the
  page. For a **missing report.html**, the dialog names the exact
  destination path — build it there per `REPORT_OUTPUT_CONTRACT.md` and the
  `rol-finance-report-verification-audit` checklist, then click OK; the
  loop re-verifies through the dashboard API before continuing. Clicking
  NO stops the whole run (`Stopped without skipping the unresolved tab.`) —
  it does not skip to the next tab, by design, for anything the loop
  couldn't diagnose or fix on its own. `--skip-yellow-months` is the only
  built-in way to move past a specific *kind* of blocker (yellow months);
  there is no per-tab skip.
- `VERIFIED <tab>: ...` / `ROL Finance Reports: no yellow or red tabs
  remain.` — done states.

## When you get stuck

No automatic Trainer watches this loop (Trainer is wired only to the
document-scan intake callback contract — see `docs/finance-intake.md` — not
this workflow). If you're blocked on the same tab for more than ~15
minutes, or a blocker's instructions don't resolve after two honest
attempts, don't keep looping silently and don't guess to force it green.
Instead:

1. Write a stuck report to `dashboard/trainer/reports/<UTC
   YYYYMMDD-HHMMSS>_report-repair.md` (same directory Trainer's own reports
   live in) with this shape:

   ```markdown
   # Mazda Stuck Report — ROL Finance Report Repair

   - Tab: <month> -> <report/month label>
   - Started: <ISO timestamp>
   - Stuck since: <ISO timestamp> (~N minutes)

   ## What I was doing
   ...

   ## What's blocking me
   ...

   ## What I tried
   ...

   ## What I need from a human
   ...
   ```

2. Message EG directly (normal channel) that you're stuck and point at the
   report file. Then either wait or move to a different tab if one is
   available and unambiguous — don't sit in a silent retry loop.

## After a repair pass

Commit `rol_finances` changes and any `letta-code/dashboard` fixes
separately, each with its own message; never `git add -A` in either repo.
`rol_finances` is multi-agent-edited — check `git status` and diff against
`origin/main` before assuming your working tree is the only thing in
flight (see the verification-audit skill's "Multi-agent caution").

Related: `rol-finance-report-verification-audit` (the actual report-build/
repair checklist), `rol-finance-report-category-colors`,
`receipt-url-audit-linking`.
