# Mazda — Document Intake & Self-Improvement Loop (Handoff)

**Last updated:** 2026-06-25 (previous: 2026-06-19)
**Agent:** Mazda `agent-6b536cf4-ec88-4290-b595-fed21d14bd8e` (live @ http://100.80.49.10:8283)
**MCP service:** `mazda-tools-mcp.service` on port 8791 (this box, DESKTOP-SHDBATI)

---

## Current state — what's working

### The self-improvement loop is live (Phases 1–4 closed)

As of 2026-06-25, Mazda has **12 MCP tools** attached — the full self-improvement
loop including A/B experimentation:

| Tool | Phase | Purpose |
|------|-------|---------|
| `load_wrapper_revision` | 1 | Load active wrapper (returns revision IDs for all artifacts) |
| `record_trace` | 1 | Persist run evidence to SQLite |
| `propose_improvement` | 1 | File a structured improvement proposal tied to a trace |
| `judge_trace` | 2 | Deterministic verdict (FinanceVerdictJudge + FailureClassifier) |
| `gate_check` | 3 | Run 4-gate chain: Safety → Cost → Regression → Usefulness |
| `activate_wrapper` | 3 | Snapshot current wrapper, activate a new revision |
| `rollback_wrapper` | 3 | Restore last known-good wrapper from snapshot |
| `run_experiment` | 4 | Baseline-vs-candidate A/B over Minion CLI runs; scores both arms, returns regressions/improvements/cost + promote/block recommendation |
| `verify_statement_totals` | — | Deterministic total verification (pure arithmetic) |
| `check_vendor_key` | — | Vendor key lookup against finance map |
| `check_category` | — | Category verification |
| `check_duplicates` | — | Duplicate expense detection |

All verified end-to-end on 2026-06-24:
- `load_wrapper_revision` → returns `mazda-wrapper-v001` with all artifact IDs
- `record_trace` → Trace saved to SQLite evidence store
- `judge_trace` → FAIL / unsupported_document (correct for test data with no finance evidence)
- `gate_check` → ALLOW through all 4 gates
- `activate_wrapper` → snapshot taken, wrapper activated
- `rollback_wrapper` → restored to known-good revision

### Scanner → Mazda event pipeline is live

When a scan completes successfully on the dashboard (Window or Freezer scanner),
`run_scanner()` in `server.py` fires `_notify_mazda_of_scan()` in a background
thread. Mazda receives a Letta message with:
- The scan image path
- Instructions to run load_wrapper_revision → classify/parse → record_trace →
  propose_improvement on failure

This is deployed on the **live dashboard** (DESKTOP-2OBSQMC, 100.72.158.63) via
surgical SSH patch. Backup at `server.py.bak` on that box.

### Intake training (from 2026-06-19, still current)

Mazda's `system/*` memory blocks encode the full pipeline:
- `system/intake_pipeline` — scan → classify → parse → verify → vendor_key → category → learn
- `system/team_agents` — cost-tier delegation to 5 minions
- `system/environment` — real tool paths
- `system/verification_procedure` — cross-references intake front half

Governing rule: **cheapest reliable tool first; LLM only when confidence < 0.90**.

---

## Infrastructure

### MCP server (`mazda-tools-mcp.service`)

```bash
# Check status
systemctl --user status mazda-tools-mcp.service

# Restart (after code changes)
systemctl --user restart mazda-tools-mcp.service

# Re-register tools with Letta (after adding/removing tools)
cd /home/adamsl/rol_finances/tools/self_improving_agent
PYTHONPATH=.:/home/adamsl/rol_finances \
LETTA_BASE_URL=http://localhost:8283 \
MAZDA_TEST_AGENT_ID=agent-6b536cf4-ec88-4290-b595-fed21d14bd8e \
MAZDA_TOOLS_MCP_URL=http://172.17.0.1:8791/sse \
.venv/bin/python -m agent_self_improvement.implementations.letta_tools.registry
```

Key paths:
- **Venv:** `/home/adamsl/rol_finances/tools/self_improving_agent/.venv`
- **SQLite evidence store:** `/home/adamsl/.mazda/self_improvement.sqlite3`
- **Service file:** `~/.config/systemd/user/mazda-tools-mcp.service`
- **Source:** `agent_self_improvement/implementations/letta_tools/` (mcp_server.py, functions.py, concrete.py, startup.py, registry.py, seed_mazda.py)
- **MCP URL from Docker:** `http://172.17.0.1:8791/sse` (Letta server reaches the host via Docker bridge)

### Initial wrapper seeding

```bash
cd /home/adamsl/rol_finances/tools/self_improving_agent
PYTHONPATH=. SELF_IMPROVEMENT_SQLITE_PATH=/home/adamsl/.mazda/self_improvement.sqlite3 \
.venv/bin/python -m agent_self_improvement.implementations.letta_tools.seed_mazda
```

Idempotent — skips if `mazda-wrapper-v001` already exists and is active.

### How to use the intake facade

```bash
cd /home/adamsl/rol_finances
.venv/bin/python3 tools/mazda_intake.py <path> --org-id=1 [--enable-parse] [--engine=gemini|openai]
```
Output: `{ ok, doc_kind, routing_key, vendor, confidence, classification_method, recommended_action, parsed, error }`

### Talking to Mazda directly

Send a message to `agent-6b536cf4-ec88-4290-b595-fed21d14bd8e` via the Letta API
or the dashboard. She follows her trained pipeline, delegating to her 5 minions.

---

## What's NOT done yet (pick up here)

### Phase 4 — A/B experiment runner (DONE 2026-06-25)

`run_experiment` is now Mazda's 12th MCP tool. Instead of running Mazda-as-self
(which would deadlock — she'd block calling her own Letta agent mid-tool-call),
the experiment runs each arm as a **Claude Agent SDK minion** via the existing
`AdapterAgentRunner(MINION) + MinionCommunicationAdapter + minion_cli_transport`.

What was added (all in `agent_self_improvement/`):
- `contracts/tool_inputs.py` — `RunExperimentInput`.
- `implementations/letta_tools/concrete.py` — `ConcreteRunExperimentTool` (drives
  `BaselineCandidateExperimentRunner`) + `_experiment_recommendation()` helper.
- `implementations/letta_tools/functions.py` — `run_experiment()` function +
  `wire_ports(run_experiment=...)` + added to `LETTA_TOOL_FUNCTIONS`.
- `implementations/letta_tools/startup.py` — constructs the minion runner +
  `RuleBasedFinanceEvaluator` and wires the new port. Env knobs:
  `MAZDA_MINION_ROLE` (default `categorization`), `MINIONS_DIR`
  (default `/home/adamsl/claude-code-sdk-ts/minions`).
- `implementations/agent_runtime/minion_adapter.py` — `to_agent_request` now honors
  a per-run `request.metadata['role']`, so the tool's `role` arg actually selects
  the minion role.
- Tests: `tests/test_phase_10_run_experiment_tool.py` (fake-runner, offline) +
  updated `tests/test_phase_07_tool_contracts.py` to the full 12-tool set (those
  two assertions were already stale from the Phase-2/3 loop tools).

**Verified:** `pytest agent_self_improvement/tests/` → 390 passed (the lone
collection error in `test_phase_1c_finance_mcp.py` is a pre-existing, unrelated
`FinanceVerifiers` import break). Service restarted; registry attached
`run_experiment` to Mazda (12/12) with the right schema.

**Committed:** `rol_finances@42a9755` — note this single commit also *first-committed*
the previously working-tree-only Phase 1–3 loop tools (judge/gate/activate/rollback),
the `seed_mazda` seeder, and the live `mazda-tools-mcp.service` unit. Before this,
the entire `letta_tools` self-improvement layer was running live but uncommitted.

**NOT verified — pick up here:** a *real* minion run end-to-end. The plumbing is
proven only with a fake/synthetic transport; no live Claude Agent SDK minion was
spawned (each arm is a paid ~300s session). Next shift: kick a real
`run_experiment` with 1–2 inputs against `/home/adamsl/claude-code-sdk-ts/minions`
and confirm the minion CLI returns the expected `IMinionTaskResult` JSON shape and
that the evaluator scores it. Watch for: the minion CLI needs `npx tsx` on PATH and
the SDK executor reachable; a missing/garbled stdout raises and the tool returns
`{"ok": false, ...}` (by design — it never throws into Letta).

### Phase 5 — Continuous reflection (NOT started)

Mazda's `enable_sleeptime` is `None`. No scheduled reflection. Two options:
1. Enable Letta sleeptime so Mazda periodically reviews her FAIL traces.
2. Add a cron/scheduled agent that calls `propose_improvement` over recent failures.

Either way, the goal: Mazda proposes a wrapper edit from her own failure history
without a human prompt, and it passes the gates.

### Memory edit gating (architectural gap)

`MemoryNoteCommand` + the gate chain exist as code, but there is **no middleware**
that intercepts Mazda's `memory_insert()` / `memory_replace()` calls and routes
them through the gate chain. Today, memory edits are ungated. Closing this gap
means wrapping the memory tools with a check against approved proposals.

### Other pending items

- `rol_finances` local repo may still be behind `origin/main` with locally-modified
  files from live `--yolo` agent output. Pull when agents are idle.
- The `FinanceEvaluationFactory.create_verdict_judge()` does NOT pass vendor_keys
  or category_map to the evaluator — verdicts for vendor/category checks may
  under-report. Fix: inject from `profile.extra` in the composition root.

---

## Deployment notes

### memfs projection is broken on this box

Two divergent memfs stores; the git-backed block-update path does NOT propagate.
**Working method:** `POST /v1/blocks/` (Postgres-only), detach old, attach new.
Verify via `POST /v1/agents/<id>/recompile`, not the projection count.

Backup: `notes_plans_handoffs/mazda_memory_backup_20260619/blocks_snapshot.json`.

### Dashboard (DESKTOP-2OBSQMC)

The scanner→Mazda wiring is a surgical SSH patch on the live dashboard, NOT in
this repo's checked-in `server.py`. The two boxes' `server.py` files are diverged.
See the `dashboard_deployment_topology` memory for the SSH deploy workflow.

### Two Mazda agent IDs in the wild

- `agent-6b536cf4-ec88-4290-b595-fed21d14bd8e` — **current live Mazda** (10 tools, active wrapper)
- `agent-070c201a-8d6d-49ba-a5fd-1489884b3b45` — **old ID** from pre-pivot training (referenced in older docs)

Always use the `6b536cf4` ID. The `070c201a` ID may still have the trained memory
blocks but is not the active orchestrator.
