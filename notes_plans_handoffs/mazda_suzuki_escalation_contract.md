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

## 4a. SwarmForge operational notes (live-verified 2026-08-08)

First real six-pack run against this repo: `dashboard/document_annotation.py`'s image-receipt
OCR matcher had no fallback for check-style/handwritten receipts (a "new document type won't
fit" case per the decision rule above — Trainer had already correctly flagged it as a dashboard
defect across multiple reports, never as something to coach Mazda about). Full pipeline
completed end to end; commits `9beea7d8`→`bc2bbfa2` merged into `fix/intake-duplicate-rows`.
What actually mattered in practice, that the README/AGENTS.md don't say:

**Prerequisites this box didn't have out of the box:** `zsh` (`apt-get install zsh`) and
`babashka`/`bb` (official installer: `curl -sLO https://raw.githubusercontent.com/babashka/babashka/master/install && chmod +x install && sudo ./install`). `tmux`, `git`, and the `codex`/`claude`
CLIs were already present. Check with `zsh --version; bb --version; tmux -V` before launching —
a missing prerequisite fails `./swarm` messily partway through.

**Isolation, for real, not just in principle:** `git clone` the target repo into a scratch
directory (e.g. `~/swarmforge-runs/<task-name>`), then `git remote remove origin` immediately —
a clone's origin defaults to pointing back at the source repo, and a role pushing a ref there
would touch the live repo even though no working-tree file changed. Pull the `six-pack` branch
into that clone per the README's `curl | tar -xz --strip-components=1`, then launch `./swarm`
from there. **Roles will still try to reach outside the scratch dir** — both `architect` and
`coder` proposed running `PYTHON_BIN=/home/adamsl/letta-code/dashboard/.venv/bin/python`
(the live checkout's venv) instead of building their own local venv. Watch every `pip
install`/`PYTHON_BIN=`/`acceptance/run.sh` approval prompt for an absolute path outside the
worktree and reject-and-redirect ("build a local venv, same pattern the last role used") rather
than approving it.

**A real gap in this SwarmForge distribution:** the constitution (`swarmforge/scripts/shared-
articles/handoffs.prompt`, `constitution/articles/local-workflow.prompt`) instructs every role
to run `merge_and_process <sender-role> <commit>` when accepting a handoff, but no such script
ships in `swarmforge/scripts/`. Every role hit this and stalled ("Startup blocked:
merge_and_process is missing from PATH... I stopped without manually merging"). Fix: drop a
thin wrapper at `swarmforge/scripts/merge_and_process` in **every** worktree (each worktree has
its own copy, not a symlink) that just runs `git merge "$commit" --no-edit`:
```bash
#!/usr/bin/env bash
set -euo pipefail
[[ $# -ge 2 ]] || { echo "usage: merge_and_process <sender-role> <commit>" >&2; exit 2; }
git merge "$2" --no-edit
```
`chmod +x` it, and it's picked up automatically (`swarmforge/scripts/` is already on each role's
PATH and already gitignored, so this never pollutes a role's own commits). Worth upstreaming to
`swarm-forge` `main`/`six-pack` at some point rather than reapplying by hand every run.

**Model/effort tuning — this is the lever that actually controls cost**, not just wall-clock:
`six-pack`'s default config (`swarmforge/swarmforge.conf`) runs every role on `codex` with
whatever the CLI's own default model is (`gpt-5.6-sol high` in this environment) — the
"frontier" tier at max reasoning, for every role including pure verification passes. In this
run, `cleaner`/`hardener`/`QA` each burned **~1–1.4M input tokens just on tool-fetch setup**
(cloning `clj-mutate`/`crap4clj`/`dry4clj`/Acceptance-Pipeline-Specification into every worktree
separately) before doing any real review work — those roles are inherently repetitive/mechanical
(CRAP/DRY scans, mutation hardening, UI-only verification), not deep-architecture reasoning, so
a lighter model is the right trade there. What was actually done, switched live mid-run via each
role's own `/model` command in its tmux pane (does not require a restart):

| Role | Why | Final setting |
|---|---|---|
| `specifier` | Defines behavior/acceptance criteria — keep full capability, but effort can drop once past the exploratory research phase | `gpt-5.6-sol low` |
| `coder` | Writes the real implementation — same reasoning | `gpt-5.6-sol low` |
| `cleaner` | Mechanical CRAP/DRY/coverage work, but still **edits real implementation code** (behavior-preserving refactors) — cheaper model, kept reasoning high since a sloppy cleanup here costs more downstream than it saves | `gpt-5.6-luna high` |
| `architect` | Structural/boundary review, same reasoning-drop rationale as specifier/coder | `gpt-5.6-sol low` |
| `hardender` | Pure verification (mutation hardening, re-running suites) — cheapest safe tier | `gpt-5.6-luna medium` |
| `QA` | Pure verification (acceptance/UI checks) — cheapest safe tier | `gpt-5.6-luna medium` |

`gpt-5.6-luna` is this environment's fast/affordable tier (`gpt-5.4-mini` migrated to it — see
`~/.codex/config.toml`'s `[notice.model_migrations]`). **Switch before a role starts its real
work, not mid-task** — a model swap doesn't lose context, but do it at an idle/NO_TASK boundary
so you're not second-guessing a switch that landed mid-tool-call. The general rule that
generalizes past this one run: roles that *write or redesign* code stay on the strongest
available model at whatever effort the task complexity needs; roles that *mechanically verify*
already-reviewed code (re-running suites, static analysis, CRAP/DRY, UI checks) are a safe place
to drop to a cheaper/faster tier, because their job is binary pass/fail against tests other roles
already wrote, not judgment calls.

**Merging the result back to the live repo:** the scratch clone is disposable and has no
push target (`origin` was removed), so bring commits back by fetching the scratch clone as a
temporary remote from the *live* checkout (`git remote add swarmforge-scratch <scratch-path> &&
git fetch swarmforge-scratch <branch> && git merge swarmforge-scratch/<branch> --no-edit`, then
`git remote remove swarmforge-scratch`) rather than pushing outward from the scratch copy. If the
live checkout has uncommitted work touching the same files SwarmForge also touched (likely — two
letta.js `--yolo` sessions run against this repo concurrently per the top-level `CLAUDE.md`),
`git stash push` (tracked changes only, not `--include-untracked`) before merging, then `git
stash pop` after — expect it to fail once on `dashboard/claude_toolcalls.json` (a log file
actively rewritten by a live process; `git checkout -- ` it immediately before retrying, possibly
more than once) and possibly on any file both sides genuinely edited (resolve by hand; it will be
a small, real, human-reviewable conflict, not a `.rej` avalanche, since SwarmForge's own commits
are usually orthogonal to unrelated concurrent work).

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
