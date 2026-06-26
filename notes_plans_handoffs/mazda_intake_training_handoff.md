# Mazda — Document Intake & Self-Improvement Loop (Handoff)

**Last updated:** 2026-06-25 (late night — supervised annual-summary run found a new
zero-row parser failure + live Letta access was blocked. Previous: night — found + FIXED the live classify failure: Mazda's
executor env lacked the Gemini key, so every `document-intake` scan failed at
`classify_scan.py`. Now resolves from gitignored `~/rol_finances/.env` (`rol_finances@320bfe3`,
pushed). Dashboard observability surface DROPPED per EG. Previous: Scanners wired / step #2)

> **⚠️ Status of "make Mazda's deep stages observable":** EG explicitly **dropped** the
> dashboard read-back ("we do not need to show scan results in the scanner dashboard" +
> "you can add polling if you have to"). So step #3's surfacing work was NOT built. The
> real blocker this shift turned out to be that **every live `document-intake` run was
> FAILING at classify** — Mazda's executor environment (SDK-executor container / systemd
> services) does not inherit Win10's interactive `~/.bashrc GEMINI_API_KEY`, so
> `tools/classify_scan.py` raised "No GEMINI_API_KEY ... found in environment" on every
> scan (evidence: `agent_run_trace` rows #4–8). **Fixed** by giving `classify_scan.py` a
> zero-dependency `.env` fallback (keyed off `__file__` → `rol_finances/.env`) and writing
> the key into the gitignored `~/rol_finances/.env` (600). Committed + pushed
> `rol_finances@320bfe3`.
>
> **⚠️ TOPOLOGY CORRECTION (cost me a wrong-box detour):** Mazda's `executor_run` is served
> by **THIS DEV BOX (DESKTOP-2OBSQMC)** — `executor_server.py` on `:8787`
> (`workspace_root: /home/adamsl`) behind the `:8789` mcp-proxy — **NOT** the Win10
> SDK-executor (`:8799`, workspace `/var/www:/work`, which rejects `/home/adamsl/...`). So
> `classify_scan.py` runs on the dev box. The fix was applied on the dev box via
> `git checkout origin/main -- tools/classify_scan.py` + a local `~/rol_finances/.env`
> (Win10 got the same, harmlessly).
>
> **✅ VERIFIED end-to-end through live Mazda** (mom's token back): she ran
> `executor_run python3 tools/classify_scan.py <walgreens.jpg>` → `rc 0`,
> `{"doc_type":"receipt","confidence":0.9}`; the parse step (`parse_and_categorize.py`,
> also Gemini) → `rc 0` with real structured data. The exact command that failed pre-fix
> now succeeds. **Mazda's intake pipeline is unblocked.**
>
> Gotcha for next shift: `record_trace` is idempotent on `input_text`, so re-sending the
> same scan message re-saves the OLD trace id (the failed #24) instead of a new success
> row — judge success by the `executor_run` return, not by a fresh trace row.
>
> **2026-06-25 late-night supervised run:** User asked Mazda to process
> `/home/adamsl/rol_finances/readable_documents/bank_statements/january/diners_0587_whole_year_2025/diners_0587_year_2025.pdf`.
> The dashboard `/api/process-pdf` path classified it correctly as
> `statement.diners_club` with confidence `0.95`, but the facade returned parse
> `success` with `transaction_count: 0`. Manual PyPDF2 text extraction showed this was
> false: the annual summary has 48 itemized rows on pages 4-5. A supervised report was
> written to `.../diners_0587_whole_year_2025/report.html` and the January tracker was
> updated as FAIL / IN_PROGRESS. Treat annual-summary zero-row parses as a bug: if the
> text contains `Transaction Detail`, category totals, and dated rows, Mazda must not
> accept a green zero-row parse.
>
> Live Mazda dispatch could not be confirmed during this run. From the dev box,
> `100.80.49.10` was offline/unreachable on Tailscale and `100.80.49.10:8283` timed
> out; active `desktop-shdbati-1` at `100.69.80.89` reset Letta API requests on `:8283`
> and rejected available SSH keys. Local Mazda MCP/executor services were running, but
> the Letta agent container/API plane was not reachable, so no `record_trace` or
> `propose_improvement` could be verified through live Mazda.
**Agent:** Mazda `agent-6b536cf4-ec88-4290-b595-fed21d14bd8e` (live @ http://100.80.49.10:8283)
**MCP service:** `mazda-tools-mcp.service` on port 8791 — **on Win10 `DESKTOP-SHDBATI` (100.80.49.10)**

---

## ⚠️ READ FIRST — topology (the thing that bites you)

**Letta AND the MCP server Mazda actually uses both live on Win10 `DESKTOP-SHDBATI`
(100.80.49.10).** Letta runs in Docker there and reaches Mazda's tools via the registered URL
`http://172.17.0.1:8791/sse` = Win10's own docker bridge → the Win10 host's
`mazda-tools-mcp.service`.

- The Linux dev box (`DESKTOP-2OBSQMC`) has its **own** copy of the repo and its **own**
  `mazda-tools-mcp.service` on 8791, but **Letta does NOT use it.** Editing/restarting the dev
  box's MCP server does nothing for live Mazda.
- **To change live Mazda's tools you must deploy to Win10:** `ssh adamsl@100.80.49.10`, update
  `~/rol_finances` (git pull), `systemctl --user restart mazda-tools-mcp.service`, then re-run
  the registry (below).
- Win10's venv is at `~/rol_finances/tools/self_improving_agent/.venv`. The dev box's venv is
  at `~/rol_finances/.venv`. (The handoff's old `tools/self_improving_agent/.venv` path was
  right for Win10, wrong for the dev box.)
- Verify what the live server actually serves with a direct MCP `tools/list` against
  `localhost:8791/sse` **on Win10** — NOT the `/v1/agents/<id>/tools` REST endpoint, which
  pages at ~10 and misleads (that's the origin of the old "10 not 12 tools" scare; nothing was
  ever missing).

---

## 🎯 Next shift — make Mazda auto-process every scan end-to-end

The Scanners page is now wired to the intake pipeline (training step #2 — shipped
2026-06-25, commit `95186f0b` on `origin/main`). **Today, the instant a scan finishes the
dashboard auto-fires `POST /api/process-document`:** the deterministic facade
(`mazda_intake.py`: classify + parse) renders inline within seconds, AND Mazda is dispatched
**fire-and-forget** (one Letta message, no polling) to run investigate → categorize → store.
See "Scanner → Mazda event pipeline is live" below for the exact mechanics.

**The goal for this shift: turn that fire-and-forget dispatch into a reliable, observable
end-to-end run.** Right now the dispatch *sends* — but nothing verifies Mazda actually drove
her full pipeline, and her result never lands back on the dashboard (by design — option "Fast
facade + async Mazda", no polling). Pick up here:

1. **Confirm tools are healthy** (verified 2026-06-25): on Win10, direct MCP `tools/list`
   against `localhost:8791/sse` should show **13** tools. Re-run the registry if a restart
   reverted anything. Intake-relevant: `check_vendor_key`, `check_category`,
   `check_duplicates`, `verify_statement_totals`, `record_trace`, `propose_improvement`,
   `load_wrapper_revision`.
2. **Do a live scan and watch Mazda actually process it.** Scan a real receipt on the
   dashboard (Scanners → Window/Freezer → Start Scan). The dashboard auto-runs the facade
   (inline card) and messages Mazda. Then **open Mazda's transcript** (dashboard Agent card,
   or Letta API for `agent-6b536cf4`) and confirm she ran the procedure in order:
   `load_wrapper_revision` → classify/parse → vendor_key → category → dedup → store →
   `record_trace` (and `propose_improvement` on failure). Governing rule still holds:
   **cheapest reliable tool first; LLM only when confidence < 0.90.**
3. **Decide how Mazda's deeper-stage result gets surfaced.** The inline card currently shows
   investigate/categorize/store as `delegated` and stops (no polling — EG's explicit
   constraint). If the next shift wants the *outcome* visible, the no-poll options are: (a)
   Mazda writes a per-scan result file the dashboard reads on next view, or (b) a
   server-side callback Mazda hits when done. **Do NOT add polling** without asking EG.
4. **Every run should leave evidence**: the `record_trace` / `propose_improvement` hygiene
   feeds the Phase 5 hourly reflection job (`mazda-reflect.timer` on Win10), which files gated
   proposals automatically — so good trace hygiene during these live scans directly fuels
   self-improvement.
5. **Mazda's memory is editable only via the gated `propose_memory_note`** (record-only until
   the memfs-commit applier is built — see Memory edit gating below). Don't expect a scan to
   mutate her `system/*` blocks yet.
6. If you change any tool code, deploy to **Win10** and re-register (topology section above) —
   editing the Linux dev box does nothing for live Mazda. **But the scanner→pipeline wiring is
   dashboard code on this box** (`DESKTOP-2OBSQMC`); after editing `dashboard/server.py` run
   `systemctl --user restart dashboard-server.service` then re-Start the Executor.

---

## Current state — what's working

### The self-improvement loop is live (Phases 1–4 closed)

As of 2026-06-25 (evening), Mazda has **13 MCP tools** attached — the full self-improvement
loop including A/B experimentation and gated memory editing:

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
| `propose_memory_note` | 5 | **Gated** memory edit — files a MEMORY_NOTE proposal, runs the gate chain, applies only if it passes (or a human approved). The ONLY sanctioned way for Mazda to edit her own memory. |
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

### Scanner → Mazda event pipeline is live (rewired 2026-06-25, training step #2)

When a scan finishes on the dashboard (Window or Freezer scanner), the frontend
(`dashboard-boot.js` `setReady()` — fired the instant the image is ready) auto-calls
**`POST /api/process-document {scanner}`**. The single dispatch point is now
`process_scanned_document()` in `dashboard/server.py`, which:

1. Runs the deterministic facade `run_intake_facade()` (`mazda_intake.py` classify + parse,
   ~1–5s) → returns a structured 5-stage result rendered inline on the Scanners page
   (classify/parse `done|skipped|error`; investigate/categorize/store `delegated` to Mazda).
2. Fires `_notify_mazda_of_scan()` in a background thread (fire-and-forget, **no polling**) —
   Mazda gets one Letta message with the scan image path + instructions to run
   `load_wrapper_revision` → classify/parse → `record_trace` → `propose_improvement` on
   failure.

**Important change:** the Mazda dispatch was **moved out of `run_scanner()`** into
`process_scanned_document()` so it fires **exactly once per finished scan** (the old code
double-pathed it). A scan via the raw `POST /api/scanner-scan` no longer notifies Mazda —
only `/api/process-document` does (which the UI auto-fires).

**Bug fixed in this commit:** module-level `_notify_mazda_of_scan()` called bare
`log_message(...)`, but `log_message` only exists as a *handler method*
(`DashboardHandler.log_message`) — so every notify thread silently died with `NameError`
(the Letta message still sent, only logging crashed). Module scope in `server.py` uses
`print(...)`; both calls fixed. Verify a clean dispatch with
`grep 'scan→mazda' /tmp/dashboard_8765.log` → should read
`Mazda notified of scan (Window Scanner): HTTP 200`.

GoF frontend: `DocumentPipelineController` (Command) + `DomDocumentPipelineView` (Strategy) +
`DocumentPipelineView` interface — both injected, unit-tested (194 JS + 101 Python tests
pass). This is **checked-in dashboard code on this box** (DESKTOP-2OBSQMC), not a surgical SSH
patch — the diverged `server.py.bak` note below applies to the older ROL Finance/receipt
endpoints, not this wiring.

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

# Re-register tools with Letta (after adding/removing tools).
# Run this ON WIN10 (where Letta is reachable at localhost:8283):
cd /home/adamsl/rol_finances/tools/self_improving_agent
PYTHONPATH=.:/home/adamsl/rol_finances \
LETTA_BASE_URL=http://localhost:8283 \
MAZDA_TEST_AGENT_ID=agent-6b536cf4-ec88-4290-b595-fed21d14bd8e \
MAZDA_TOOLS_MCP_URL=http://172.17.0.1:8791/sse \
.venv/bin/python -m agent_self_improvement.implementations.letta_tools.registry
```

> Running the registry FROM THE LINUX DEV BOX instead: use
> `LETTA_BASE_URL=http://100.80.49.10:8283` (localhost:8283 is dead on the dev box) and the
> dev-box venv `/home/adamsl/rol_finances/.venv/bin/python`. Keep
> `MAZDA_TOOLS_MCP_URL=http://172.17.0.1:8791/sse` (that's how Letta-in-Docker reaches the
> Win10 MCP host — do not change it to a tailnet IP). The registry's `EXPECTED_TOOL_NAMES`
> derives from `LETTA_TOOL_FUNCTIONS` (now 13); it attaches all of them. Verify with the SDK
> `client.agents.tools.list(agent_id)` deduped by `tool.id`, not the REST `/tools` page.

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

**VERIFIED LIVE 2026-06-25** — a *real* minion run end-to-end. Confirmed on this
box (DESKTOP-SHDBATI): `npx tsx` works (tsx 4.22.4 / node 22.18.0), local `claude`
binary 2.1.191 present, SDK executor bridge `:8799` SDK-ready.

- **Minion CLI smoke test** (direct `echo '{...}' | npx tsx src/cli.ts`): returned
  a valid `IMinionTaskResult` → `{"status":"ok","output":"OK","sessionId":...,"usage":{...}}`.
- **Full `run_experiment`** via live `wire_live_ports()` with 1 input (= 2 real
  minion sessions, baseline + candidate, role `categorization`): returned
  `{"ok":true,"ran":1,"baseline_failures":1,"candidate_failures":1,"regressions":[],
  "improvements":[],"recommendation":"NEUTRAL — no measurable difference..."}`. Both
  arms ran as real Claude Agent SDK sessions, the `RuleBasedFinanceEvaluator` scored
  each (1 failure/arm is correct — a plain categorization reply has no finance
  totals/vendor evidence, so it fails the parseability checks), and the NEUTRAL
  recommendation is correct since baseline == candidate revision.
- **`run_experiment` attached to live Mazda** (`agent-6b536cf4`) — confirmed via
  `/v1/agents/.../tools`.

**Failure-path correction to the old note above:** the claim that "a missing/garbled
stdout raises and the tool returns `{"ok": false}`" is **imprecise**.
`AdapterAgentRunner.run` *absorbs* every transport exception (bad `MINIONS_DIR`,
empty/garbled stdout → `minion_cli_transport` raises) into a failed
`RunResult(succeeded_transport=False, output_text="")`. So a broken arm is scored as
a **failure**, and the experiment still returns `ok:true` (that arm just counts toward
`*_failures`). `run_experiment` returns `{"ok": false}` only when (a) `task_inputs`
is empty, or (b) an exception escapes `exp_runner.run()` (e.g. evaluator/detector
fault). Both confirmed: empty inputs → `{"ok":false,"ran":0,"message":"task_inputs
is empty..."}`; a runner that raises → caught by `ConcreteRunExperimentTool.execute`'s
try/except → `{"ok":false,"ran":0,"message":"Experiment failed: RuntimeError: ..."}`.
The key invariant holds: **no exception ever reaches Letta** — every path returns a
structured dict.

(Correction: the old "live Mazda lists **10** tools, not 12 / check_vendor_key +
check_category missing" note was a **REST pagination artifact** — `/v1/agents/<id>/tools`
returns ~10 per page. All tools were attached the whole time. Verify by deduping the SDK
`client.agents.tools.list(agent_id)` by `tool.id`.)

**Loop-code recovery (2026-06-25 evening):** the Phase 2–4 loop tools (run_experiment,
gate_check, judge_trace, activate_wrapper, rollback_wrapper) had never been committed on the
Linux dev box and were missing from its working tree (the dev box's local MCP server served
only 7 tools — which briefly looked like the live tools were "dead stubs"; they were not, Win10
served all of them). The intact code was on Win10, committed as `a52357f`; it is now on
`origin/main` and present on both boxes. Lesson: **always commit the `letta_tools` layer; never
leave it working-tree-only.**

### Phase 5 — Continuous reflection (DONE 2026-06-25 evening)

Native Letta sleeptime is **inert** on this server version: `agents.update(enable_sleeptime=
True)` sets the flag but creates no sleeptime agent / `multi_agent_group`, and there's no
`client.groups` resource. So the flag was reverted to `False` and Phase 5 was delivered via a
**scheduled reflection job** (the cron-style option):

- `implementations/improvement/reflection.py` — `FailureReflectionService`: scans FAIL verdicts
  in the evidence store and files a gated `propose_improvement` per new FAIL (dedup'd against
  already-proposed traces → idempotent), then runs the gate chain. No human prompt.
- `implementations/letta_tools/reflect_main.py` — live entrypoint.
- Live on **Win10** via `systemd --user`: `mazda-reflect.timer` (OnUnitActiveSec=1h,
  Persistent) → `mazda-reflect.service` (oneshot). Check:
  `ssh adamsl@100.80.49.10 'systemctl --user list-timers mazda-reflect.timer'` and
  `journalctl --user -u mazda-reflect.service`.
- Verified live: reviewed 3, 2 FAILs → proposals 9,10 (gate=allow); re-run skipped both.
- Tests: `tests/test_phase_12_reflection.py` (3 pass). Committed `0446938` on origin/main.

The proposals it files are PROPOSED/gated — they are NOT auto-activated. A human (or a future
auto-promotion guarded by `run_experiment` + `gate_check`) still drives `activate_wrapper`.

### Memory edit gating (DONE 2026-06-25 evening — one follow-up left)

Note: Mazda has **no** `memory_insert`/`memory_replace` tools attached (block-edit tools are
detached under the memfs model), so there was never a raw memory write to intercept. Instead, a
**single gated entry point** was added so any future memory edit must pass the gates:

- `propose_memory_note` (tool #13): records a MEMORY_NOTE proposal → runs the gate chain →
  applies only on ALLOW (or recorded human approval); high-risk → block/needs-human. Built to
  interfaces (`IMemoryNoteApplier` Strategy). Committed `2f7b6ba`, deployed to Win10, attached.
- Tests: `tests/test_phase_11_memory_note_gating.py` (5 pass).
- **Follow-up (NOT done):** the live applier is `NullMemoryNoteApplier` — it records the
  approved note but does **not** write live memory (the server treats blocks as a read-only
  projection of memfs). To make approved notes actually land in memory, implement a
  **memfs-commit applier** (write markdown under `system/**`, commit to the agent's memfs
  `state.git`) and inject it in `startup.py` in place of `NullMemoryNoteApplier`. Until then,
  `applied=false` in the tool's output is expected and correct.

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

- `agent-6b536cf4-ec88-4290-b595-fed21d14bd8e` — **current live Mazda** (13 tools, active wrapper)
- `agent-070c201a-8d6d-49ba-a5fd-1489884b3b45` — **old ID** from pre-pivot training (referenced in older docs)

Always use the `6b536cf4` ID. The `070c201a` ID may still have the trained memory
blocks but is not the active orchestrator.
