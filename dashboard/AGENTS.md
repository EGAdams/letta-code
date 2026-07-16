# Dashboard — Codex Agent Guidelines

This file is for Codex CLI sessions working in `dashboard/`. The canonical,
always-current architecture doc for this sub-project is `dashboard/CLAUDE.md` —
read it for the server, frontend, voice pipeline, scanners, and deploy notes.
This file covers what Codex most often needs here and is NOT in the repo-root
`AGENTS.md`: **the Mazda Trainer — what it is, how to use it, and how to train
Mazda with it.**

## The Mazda Trainer — using it and training Mazda

### What it is

Mazda (Letta agent `agent-6b536cf4-ec88-4290-b595-fed21d14bd8e`) is the
self-improving document-intake agent: every scanned/PDF financial document is
dispatched to her to classify, dedupe, categorize, and store in the
`nonprofit_finance` MySQL DB. She runs on a cheap mini model, so her runs are
expected to be flawed.

The **Trainer** is a one-shot watcher agent spawned automatically for EVERY
intake dispatch (scanner scan, PDF, and reprocess). It:

1. Watches Mazda's live transcript (Letta API) for that ONE run,
2. verifies her STEP 1–8 intake contract against **successful tool returns**
   (never her prose claims),
3. **coaches** her on failure — one corrective Letta message telling her what
   she did, what the contract required, the exact corrected tool call, and to
   record the lesson in her memory,
4. always writes a verdict report (PASS / FAIL / STALLED) to
   `trainer/reports/<UTC yyyymmdd-HHMMSS>_<scanner>.md`.

Philosophy the Trainer enforces (from Mazda's developer manual): **improve the
wrapper, never blame the model.** Every failure is diagnosed as a defect in her
instructions, tools, or memory — something fixable — and turned into a durable
lesson.

### Key files

| File | Role |
|---|---|
| `trainer/run_mazda_trainer.mjs` | bun runner. Claude (sonnet) primary, `codex exec` (`gpt-5.4-mini`) fallback when a Claude session errors (quota/auth/crash/timeout). Watchdog relaunches up to 3 attempts until a report file exists; writes an emergency STALLED report if all fail. |
| `trainer/mazda_trainer_instructions.md` | The Trainer's system instructions — the STEP 1–8 contract, polling rules, coaching rules, report format. Edit THIS to change how Mazda is trained/graded. |
| `../notes_plans_handoffs/mazda_dev_status.html` | Mazda's developer manual; tag-stripped and appended to the Trainer's system message at launch. The canonical current-direction doc for Mazda. |
| `trainer/reports/` | One markdown report per watched run. Read the newest to see how Mazda's last run went. |
| `server.py` (`build_trainer_command`, `_notify_trainer_of_scan`, ~line 1817) | Fire-and-forget detached Popen wiring from both `process_scanned_document` and `process_pdf_document`. A broken Trainer never blocks intake. |

### The intake contract the Trainer verifies

A correct Mazda run shows all of these in her transcript, in order, each with a
successful tool return: `load_wrapper_revision` → (STEP 0 vision classification
via `executor_run` if the facade said `doc_kind=unknown`, the normal case for
JPEG scans) → `check_vendor_key` + `check_duplicates` → categorize
(`categorizer_main.py`) → store (`parse_and_categorize.py --save`) →
`record_trace` with `task_name="document-intake"` + IntakeVerificationEvidence
JSON → `judge_trace(trace_id)` always → `propose_improvement` on FAIL →
`curl POST /api/expense-stored` dashboard callback (must fire even when
`stored:0`, e.g. duplicates). A correctly-detected duplicate is a PASS.

### Running the Trainer by hand

Automatic dispatch usually suffices, but run it manually to re-grade a run,
after fixing a wrapper defect, or to test instruction changes:

```bash
cd /home/adamsl/letta-code/dashboard/trainer
~/.bun/bin/bun run_mazda_trainer.mjs \
  --scan-path /path/on/executor/scan.jpg \
  --scanner "Window Scanner" \
  --facade '{"ok":true,"doc_kind":"unknown","confidence":0}' \
  --dispatched-at <unix ts of the dispatch you want graded>

# Free prompt-assembly check (no model call) — ALWAYS run after editing
# mazda_trainer_instructions.md or when mazda_dev_status.html moves:
~/.bun/bin/bun run_mazda_trainer.mjs --scan-path /x.jpg --scanner test --dry-run
```

`--dispatched-at` matters: the Trainer ignores transcript entries older than it.
To re-grade a finished run, pass the original dispatch timestamp (see
`recent_report.json` or `/tmp/dashboard_8765.log`).

Env vars: `MAZDA_TRAINER_ENABLED=0` (kill switch, read by server.py),
`TRAINER_MODEL` (default sonnet), `TRAINER_CODEX_MODEL` (default gpt-5.4-mini —
plain `gpt-5-mini` is rejected by the provider), `TRAINER_TIMEOUT_MS` (default
35 min overall), `TRAINER_ATTEMPT_TIMEOUT_MS` (default 20 min per session),
`LETTA_BASE_URL`, `MAZDA_AGENT_ID`, `MAZDA_TRAINER_RUNNER` (bun path),
`MAZDA_TRAINER_CODEX_BIN`.

Logs: `/tmp/mazda_trainer_<dispatch ts>.log` for auto-spawned runs.

### How to train Mazda (change her behavior durably)

Three escalating levers — prefer the least invasive:

1. **One-off lesson**: send Mazda a corrective Letta message (what the Trainer
   does): `POST $LETTA_BASE_URL/v1/agents/$MAZDA_AGENT_ID/messages` with a
   concrete lesson + "record this in your memory". Good for a single mistake.
2. **Permanent memory**: edit her memfs `system/*.md` files
   (`receipt_intake_procedure.md`, `finance_codebase_map.md`) and push — blocks
   are a read-only projection of memfs; NEVER `POST/PATCH /v1/blocks` directly.
   Procedure: memory `mazda_memfs_update_procedure_2026_06_26.md`.
3. **Contract/rubric change**: edit `trainer/mazda_trainer_instructions.md`
   (what the Trainer enforces) and/or the intake judge rubric in
   `~/rol_finances/tools/self_improving_agent` (then
   `systemctl --user restart mazda-tools-mcp`). Keep the STEP 8 field contract
   in sync across the dispatch message (`build_mazda_scan_message` in
   server.py), Mazda's memfs, and the rubric —
   `test_scan_message_instructs_structured_intake_evidence` pins it.

The Trainer must **never do Mazda's work** — no storing expenses, no DB
patches. Its only writes are coaching messages to Mazda and its report file.

### Non-obvious invariants & gotchas

- **The Trainer session dies the moment it stops talking.** No scheduler, no
  background notifications. Waiting = foreground Bash `sleep`/poll loop only,
  and the report must be written before finishing. The watchdog in the .mjs
  exists because models violated this twice.
- The .mjs strips `ANTHROPIC_API_KEY` / `CLAUDECODE` / `CLAUDE_CODE_ENTRYPOINT`
  so an inherited API key can't outrank the box's OAuth login. Codex fallback
  needs `codex` on PATH (`~/.npm-global/bin`); the dashboard service's Popen
  prepends `~/.bun/bin:~/.local/bin`.
- `scan.jpg` / `scan_freezer.jpg` are fixed paths every scan overwrites — the
  document identity comes only from THIS run's transcript evidence, never the
  filename.
- **pytest must never spawn real Trainers** — `tests/conftest.py` has an
  autouse fixture forcing `TRAINER_ENABLED = False`; any new test touching
  `process_scanned_document`/`process_pdf_document` inherits it. If a report
  claims an "infrastructure delivery failure", check its timestamp against a
  concurrent `pytest tests/` run before believing it.
- Debugging order + full ops runbook: skill
  `/home/adamsl/.claude/skills/mazda-trainer-ops.md`; history in memories
  `mazda_trainer_agent_2026_07_10.md`, `mazda_intake_outage_chain_2026_07_10.md`,
  `trainer_claude_primary_att_phantom_repair_2026_07_13.md`.

### Tests

```bash
cd /home/adamsl/letta-code/dashboard
.venv/bin/python -m pytest tests/test_server.py -k trainer   # build_trainer_command etc.
.venv/bin/python -m pytest tests/                            # full suite
```

After editing `server.py`: `systemctl --user restart dashboard-server.service`
(then re-Start the Executor — the restart kills it).
