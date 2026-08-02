# Mazda → Suzuki Escalation Contract

**Status:** LIVE contract, wired 2026-08-01. This is the boundary between document
processing (Mazda) and software engineering (Suzuki) under the SOLID + Gang-of-Four
engineering strategy. It is the *one abstraction the strategy hinges on*: a defect only
reaches the engineering system through this contract.

> Guiding rule: **every bug is both a defect to fix and an architectural signal to
> investigate.** Suzuki fixes the bug *and* reduces the architectural conditions that
> allowed it.

---

## 1. What already exists (do not rebuild)

The escalation machinery is already built and **live-verified 2026-08-01**
(`suzuki_run_bug_hunt.py --check-ready` → all 6 stage agents resolve):

| Piece | Where | Role |
|---|---|---|
| **Escalation packet** | `BugHuntRequest(run_id, bug_id, repo_path, bug_description, metadata)` in `agent_packages/suzuki/debug_orchestrator.py` | The typed handoff Mazda produces. **No new schema is needed.** |
| **Handoff contract** | `DebugStageEnvelope` (`debug-stage-envelope/v1`) | Shared JSON envelope every Suzuki specialist speaks. |
| **Orchestrator + fleet** | Suzuki (`agent-c4e58e29-…`) + 6 specialists (router, reproducer, static-analysis, patch, test-runner, regression) | The 12-stage debug workflow. |
| **Entry point** | `rol_finances/tools/self_improving_agent/suzuki_run_bug_hunt.py` | CLI that runs the workflow. |
| **Result contract** | `SuzukiOrchestrationResult` — `called_stages`, `reproduction_achieved`, `patch_produced`, `fix_verified`, `has_failed_stages` | What Suzuki returns. |

Suzuki's canonical stage order:
`triage → reproduce → localize → patch → verify → regression_check → record_trace →
evaluate → propose_improvement → experiment_and_gate → activate_or_reject → report_and_learn`.

The first six stages run on live Letta specialists; the rest feed the shared
self-improvement kernel Suzuki inherits from Mazda.

---

## 2. The routing decision (Outcome A / B / C)

**The Mazda Trainer is the actual detector**, not Mazda herself — every scan already
spawns a Trainer that watches the run, and it now classifies before coaching (see
`dashboard/trainer/mazda_trainer_instructions.md`, "When something went wrong — teach",
step 0). Wired 2026-08-01. After a document runs, classify:

- **Outcome A — success.** Record it, change no code, keep scanning.
- **Outcome B — document-reasoning problem Mazda can self-correct.** A misread field, a
  bad category, a classification miss — anything her self-improvement loop (STEP 5/6
  evidence + `judge_trace`) is designed to handle. Let Mazda self-correct, verify, keep
  scanning. **Do NOT escalate.**
- **Outcome C — application-code defect.** Escalate to Suzuki. Signals:
  - a Python traceback / crash in dashboard or `rol_finances` code (not an LLM refusal),
  - duplicated logic, tightly-coupled components, hard-coded behavior,
  - a fix that would touch several unrelated components,
  - an architectural assumption that blocks a new document type,
  - code that cannot be tested independently.

**The test for C vs B:** *Would fixing this require editing application source?* If yes → C.
If it only requires Mazda learning/adjusting her own reasoning or wrapper → B. **Fail toward
B** — never escalate something Mazda's own loop already handles; that just spawns a redundant
bug hunt.

---

## 3. How the escalation gets filed and invoked

**The Trainer detects and fills the fields; it does NOT invoke Suzuki itself** — its Bash
allowlist deliberately never touches `rol_finances` or executes anything (see the ops
skill). It writes a `## Escalation` block in its report
(`dashboard/trainer/reports/<ts>_<scanner>.md`) with `repo_path`, `bug_description`,
`metadata`. A human (today) or an automated dispatcher (future — grep new reports for
`## Escalation`) turns that block into a `BugHuntRequest` and invokes the workflow via
`executor_run` or directly. Field mapping:

| BugHuntRequest field | Source |
|---|---|
| `run_id` | the intake `run_id` that hit the defect |
| `bug_id` | short stable slug, e.g. `intake-duplicate-rows` |
| `repo_path` | Trainer report's `repo_path` |
| `bug_description` | Trainer report's `bug_description` |
| `metadata` | Trainer report's `metadata` (`failing_command`, `document_path`, etc.) |

Exact command (note the venv + PYTHONPATH — bare `python3` dies with `ModuleNotFoundError`):

```bash
cd /home/adamsl/rol_finances/tools/self_improving_agent
PYTHONPATH=/home/adamsl/rol_finances \
  /home/adamsl/rol_finances/.venv/bin/python3 suzuki_run_bug_hunt.py \
  --live --repo <repo_path> --bug "<bug_description>"
```

Use `--dry-run` (fake stage agents, no Letta calls) to validate wiring for free;
`--check-ready` confirms the live specialists resolve before a real run.

---

## 4. The SOLID / GoF mandate — and the SwarmForge gap

Suzuki's `localize → patch` stages fix the defect. They do **not**, on their own, satisfy the
strategy's second half: *reduce the architectural conditions that allowed the bug.* Suzuki's
stage vocabulary has no dedicated **architect / cleaner / hardener** role (SOLID review,
dependency-direction, CRAP/DRY, separation-of-concerns, mutation hardening).

**Decision rule for the architectural half:**

- **Small, local fix** (one component, no boundary change) → Suzuki inline. Her
  `regression_check` stage already emits a `wrapper_lesson`; capture the SOLID observation there.
- **Multi-component / boundary / "new document type won't fit" refactor** → escalate a second
  hop to **SwarmForge six-pack** (`/home/adamsl/swarm-forge`, branch `six-pack`):
  `specifier → coder → cleaner → architect → hardener → QA`. That pipeline *is* the SOLID+GoF
  refactor loop — each quality gate owned by a separate agent in its own git worktree. Check out
  `six-pack` into a scratch copy of the target repo; never run it against the live checkout.

SwarmForge has **no persistent memory** (state is torn down at `close-swarm`). Suzuki does
(shared self-improvement kernel). So Suzuki owns the durable architectural lessons; SwarmForge
is the heavy short-lived refactor swarm it can dispatch.

---

## 5. Report before significant changes

Before a Suzuki/SwarmForge run makes non-trivial edits, state:
1. What failed. 2. B (Mazda self-improve) or C (code defect). 3. Which SOLID principle is
violated, if any. 4. Which GoF pattern fits, if any. 5. Which interfaces/abstractions change.
6. How Suzuki vs SwarmForge split the work. 7. What tests will prove the fix.

Then take the **smallest well-designed** step.

---

## 6. Verification / tests

- Suzuki contract tests: `test_suzuki_gof_seams.py` (offline, fake stage agents).
- Readiness: `suzuki_run_bug_hunt.py --check-ready`.
- Fix is proven when: `SuzukiOrchestrationResult.reproduction_achieved` **and**
  `fix_verified` are true, `has_failed_stages` is false, and re-processing the original
  document yields Outcome A.

Related: memory `mazda_suzuki_engineering_strategy_2026_08_01`, `suzuki_dev_manual.html`,
`swarm-forge/README.md` (six-pack).
