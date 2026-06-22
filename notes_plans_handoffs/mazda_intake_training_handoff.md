# Mazda — Document Intake & Categorization Training (Handoff)

**Date:** 2026-06-19
**Agent:** Mazda `agent-070c201a-8d6d-49ba-a5fd-1489884b3b45` (live @ http://100.80.49.10:8283)

## What was done (two complementary layers)

| Layer | Who | What |
|---|---|---|
| **Wrapper / memory** (this work) | trained Mazda's `system/*` memory blocks | She now *knows* the scan→parser→parse→vendor_key→category workflow, cheapest-first, 0.90 confidence gate, sub-agent strategy, self-improvement |
| **Code / tools** (other team, in `rol_finances` repo) | `tools/mazda_intake.py` + `agent_self_improvement` GoF framework | The actual executable wrappers Mazda's instructions now point at |

Neither overwrote the other. The training was aligned to **use the team's interfaces** (GoF Facade + Abstract Factory) rather than raw CLI calls.

## What Mazda learned (her live memory blocks)

- **`system/intake_pipeline`** (new, 7.3 KB) — the front half of the pipeline:
  1. **Scan/triage** — PyPDF2 text → Tesseract OCR fallback (<300 chars).
  2. **Choose parser** — rules-first (`RuleBasedClassifier`, <10 ms) → Gemini/OpenAI LLM **only when confidence < 0.90**.
  3. **Parse** — via the facade (below).
  4. **Verify totals** → `system/verification_procedure` (back half).
  5. **vendor_key** from description (`resolve_vendor_key_with_fallback`).
  6. **Category from vendor_key** — use the lookup, don't ask the user.
  7. **Category from description** — LLM fallback (`find_category/`), **involve the user when confidence < 90%**.
  8. **Learn** — fold durable lessons (new vendor aliases, parser choices) back into memory / `vendor_category.yaml`.
  - Governing rule: **cheapest reliable tool first**; flexible workflow — enter at any step.
- **`system/team_agents`** — added cost-tier delegation (which minion per step) + the `mazda_run_team.py` factory runner.
- **`system/environment`** — added the real tool paths (facade + components).
- **`system/verification_procedure`** — cross-references the intake front half.

## How to use it

### 1. The cheapest-first intake facade (the team's `mazda_intake.py`)
A **Facade** over `parsing_router.DocumentRouter`; returns one clean JSON object — ideal for `executor_run`.
```bash
cd /home/adamsl/rol_finances
.venv/bin/python3 tools/mazda_intake.py <path> --org-id=1 [--enable-parse] [--engine=gemini|openai]
```
Output: `{ ok, doc_kind, routing_key, vendor, confidence, classification_method, recommended_action, parsed, error }`
`recommended_action`: `auto` (≥0.90) · `review` (0.70–0.89 → involve user) · `reject` (<0.70).
Default is classify-only; add `--enable-parse` to parse + insert.

### 2. The full team workflow (the team's Abstract-Factory runner)
```bash
cd /home/adamsl/rol_finances/tools/self_improving_agent
../../.venv/bin/python3 mazda_run_team.py --live --source-uri <path>   # drop --live for offline dry run
```
Built on `MazdaTeamFactory` / `MazdaFinanceWorkflowRunner` / `StageEnvelope`.

### 3. Talking to Mazda
Just ask her — e.g. "scan and categorize this statement," "re-parse X," "why is this row categorized as transportation?" She enters at the step you ask for and follows the workflow above, delegating to her 5 minions and preferring the cheapest reliable tool.

## Important deployment note (the memfs projection is broken here)
On this self-hosted box there are **two divergent memfs stores**: the memfs-service repo (`~/.letta/memfs-repos`, served on :8285) vs. the letta-server's `LocalStorageBackend` (`/app/.letta/memfs`). A `git push` to `/v1/git/...` updates the **service** repo but the post-push sync reads the **other** store, so it never reaches Postgres. The documented "author memfs files → projected into blocks" path therefore does **not** propagate, and the git-backed block-update API 500s.
**Working method used here** (per your approval): create a fresh standalone block (`POST /v1/blocks/`, Postgres-only), detach the old, attach the new. **Verify by grepping the compiled context** (`POST /v1/agents/<id>/recompile`), **not** the `<projection>` count (that reflects the stale memfs file tree).

A full backup of Mazda's original blocks is at `notes_plans_handoffs/mazda_memory_backup_20260619/blocks_snapshot.json`.

## Still pending (your call)
- `rol_finances` local repo is **13 commits behind** `origin/main` with 14 locally-modified files (live `--yolo` agent output) + 3 untracked collisions. Pull it when the live agents are idle to avoid clobbering their report output.
