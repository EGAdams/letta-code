# Verify Mazda Trainer

Check that the Trainer did her job correctly on the most recent scanner run, and that her
self-improvement loop is actually working (not just filing rules that get ignored).

## Steps

1. **Find the latest report** — `ls -t dashboard/trainer/reports/*.md | head -1`. If the
   newest report is older than the scan the user just ran (or missing), the Trainer run
   died — go check `/tmp/mazda_trainer_*.log` (newest file) for the error instead, per
   the `mazda-trainer-ops` skill's debugging order.
2. **Read that report** and confirm:
   - `record_trace` and `judge_trace` were both called (not skipped).
   - The STEP 1-8 contract table has no unexplained `❌`/missing rows.
   - If the verdict is FAIL or CORRECTED, check whether `propose_improvement` /
     `propose_memory_note` fired — that's the self-improvement loop actually engaging.
3. **Check the loop isn't just spinning** — grep the last few reports
   (`ls -t dashboard/trainer/reports/*.md | head -5`) for repeated near-duplicate
   proposals about the same failure. A rule getting re-proposed instead of followed means
   Mazda has the instruction loaded but isn't obeying it (see the 2026-07-20 BJ's
   report for the exact pattern) — that's a real problem worth flagging, not something
   another proposal will fix.
4. **Summarize for EG in plain language**: did the run pass clean, get corrected, or fail;
   did self-improvement fire when it should have; is there a recurring problem (e.g. a
   rule being filed repeatedly instead of followed, or an infra issue like the gemini CLI
   being missing). Keep it short — conclusion first, skip the tool-by-tool walkthrough
   unless asked.

## Notes
- The Trainer is fire-and-forget — it's already spawned automatically by
  `dashboard/server.py` on every scan. This command doesn't launch her; it grades her
  most recent run after the fact.
- Full background: `~/.claude/skills/mazda-trainer-ops.md`.
