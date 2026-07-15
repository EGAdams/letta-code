# Repository Guidelines

## Parity with Claude Code: Skills & Memory Pointers

Claude Code (the assistant used alongside Codex on this machine) has three
knowledge sources that Codex does not load automatically. Read them
explicitly when they're relevant to the current task — don't rely on this
file alone for anything skill- or memory-shaped.

- **Full repo instructions**: `/home/adamsl/letta-code/CLAUDE.md` — the
  canonical architecture doc (entry points, agent/tools/skills/permissions/
  hooks layers, Bun API conventions, memfs authoring policy, pre-commit
  hook behavior, known pre-existing test failures). The "Repository
  Guidelines" section below is a condensed subset; `CLAUDE.md` has more
  detail and is kept current — prefer it when the two disagree.

- **Project skills** (repo-scoped, git-tracked):
  - `/home/adamsl/letta-code/skills/` — built-in skills bundled with the
    `letta` CLI product itself (copied from `src/skills/builtin/` at build
    time). Each subdirectory has a `SKILL.md` with a `name`/`description`
    frontmatter header — read that header first to decide relevance, then
    open the full file if it matches the task.
  - `/home/adamsl/letta-code/.skills/` — the larger, actively-used set of
    project-authored skills for operating this environment (Mazda/Suzuki
    dashboard, receipt pipeline, WSL/Tailscale recovery, Letta admin,
    memory/memfs migration, etc.). This is the directory to check first for
    anything involving the dashboard, receipt scanning, live Letta agents,
    or infra recovery — it's a superset of `skills/`.

- **Global skills** (user-scoped, apply across all repos):
  `/home/adamsl/.claude/skills/` — either a single `<name>.md` file or a
  `<name>/SKILL.md` dir per skill. See `/home/adamsl/.claude/skills/README.md`
  for an index. Covers logger-API ops, dashboard debugging, invoice tools,
  OAuth/token rotation, and other cross-project operational skills.

- **Persistent memory** (accumulated learnings from past sessions, written
  after task-relevant discoveries or user corrections — not derivable from
  the code itself):
  `/home/adamsl/.claude/projects/-home-adamsl-letta-code/memory/MEMORY.md`
  is the index; each linked file in that same directory is one dated memory
  (incident, fix, standing preference). Read `MEMORY.md` first, then follow
  links for entries relevant to the current task. This directory is the
  closest Codex analog to the "Agent Memory: ..." sections appended below —
  treat both as authoritative, dated, and prone to going stale (verify
  paths/behavior still exist before acting on an old entry).

When starting non-trivial work, skim `MEMORY.md` and check whether
`.skills/` or `skills/` has a matching skill by description before
improvising a solution — that's the equivalent of what Claude Code does
automatically via its skill-matching system prompt.

## Project Structure & Module Organization
- Main source lives in `src/` (CLI runtime, providers, tools, skills, web templates).
- Unit and behavior tests live in `src/tests/`.
- Integration tests live in `src/integration-tests/` with `*.integration.test.ts` and related harness files.
- Build and utility scripts live in `scripts/`; generated/runtime artifacts are in `dist/` and `vendor/`.
- Contributor docs include `README.md` and `CONTRIBUTING.md` at repo root.

## Build, Test, and Development Commands
- `bun install`: install dependencies (project standard package manager).
- `bun run dev`: run the CLI directly from TypeScript sources for local development.
- `bun run build`: produce the standalone build (`letta.js` + packaged assets).
- `bun run lint`: run Biome checks on `src/`.
- `bun run fix`: apply Biome auto-fixes.
- `bun run typecheck`: run strict TypeScript checks with no emit.
- `bun test src/tests`: run unit/behavior tests.
- Example targeted integration test:  
  `bun test src/integration-tests/scissari-agent.integration.test.ts`

## Coding Style & Naming Conventions
- Language: TypeScript (ES modules), strict mode enabled in `tsconfig.json`.
- Formatting/linting: Biome (`biome.json`), 2-space indentation, spaces (no tabs).
- File naming: use descriptive kebab-case; tests end in `.test.ts` or `.integration.test.ts`.
- Keep modules focused; prefer small helpers over large multi-purpose files.

## Testing Guidelines
- Test runner: Bun test.
- Add unit tests under `src/tests/**` for logic changes; add integration tests under `src/integration-tests/**` for end-to-end flows.
- Name tests by behavior and scenario (example: `headless-stream-json-format.test.ts`).
- Before opening a PR, run: `bun run lint && bun run typecheck && bun test`.

## Commit & Pull Request Guidelines
- Follow Conventional Commit style seen in history (`fix: ...`, `docs: ...`, `chore: ...`).
- Keep commits scoped to one concern; include test updates with behavior changes.
- PRs should include: purpose, key changes, test evidence (commands run), and linked issues.
- For user-visible CLI/output changes, include a short example of before/after behavior.

## Security & Configuration Tips
- Do not commit secrets or local tokens; use environment variables (for example `LETTA_BASE_URL`).
- Validate changes touching providers, shell/tool execution paths, or remote logger integrations with focused tests.

## Agent Memory: Approval Recovery Logs
- For yellow/stale integration-test rows, check `src/skills/custom/diagnose-yellow-test-status/SKILL.md` first.
- For approval recovery hangs, check `src/integration-tests/prestream-approval-recovery.test.ts`, `src/headless.ts`, `src/agent/check-approval.ts`, and `src/agent/turn-recovery-policy.ts`.
- `echo`/`printf` shell prompts can be auto-approved as read-only. Tests that need a pending approval should use a harmless approval-required command, such as `ShellCommand` with `touch /tmp/letta-code-prestream-approval-test`.
- Verify remote logger state directly with `curl -s "http://100.80.49.10:8284/libraries/local-php-api/object/select?object_view_id=<LoggerId>"` before assuming the viewer is wrong.

## Agent Memory: Subagent Model Fallback
- If Scissari/Task subagents fail with `NOT_FOUND: Handle letta/auto not found, must be one of []`, inspect `src/agent/subagents/manager.ts`.
- `resolveSubagentModel()` should inherit the parent model or choose a server-available non-auto handle when `letta/auto` is absent.
- Regression tests: `bun test src/tests/agent/subagent-model-resolution.test.ts` and `bun test src/integration-tests/subagent-model-fallback.integration.test.ts`.

## Agent Memory: Scissari Memfs Remote Drift
- Symptom: Scissari runs succeed but startup logs show memfs-git pull failures to stale host `10.0.0.143:8283` while current server is `100.80.49.10:8283`.
- Root cause: persisted per-agent `memfsRemote` can pin an old base URL/remote, which overrides current `LETTA_BASE_URL` during startup sync.
- Fix locations:
  - `src/agent/memoryFilesystem.ts`: `resolveMemfsRemoteUrl()` drops stale HTTP remotes when host differs but path is default `.../v1/git/<agent>/state.git` or bare `/`.
  - `src/agent/memoryGit.ts`: `pullMemory()` now always runs `ensureRemote()` so `origin` is reconciled on every pull.
  - `src/cli/App.tsx`: startup memfs sync now resolves/clears stale persisted remote before `cloneMemoryRepo()` / `pullMemory()`.
- Regression tests:
  - `bun test src/tests/agent/memoryFilesystem.test.ts`
  - `bun test src/tests/agent/memoryGit.auth.test.ts src/tests/agent/memoryGit.remote-heal-wiring.test.ts`
- High-signal Scissari integration commands:
  - `LETTA_RUN_SCISSARI_TEST=1 bun test src/integration-tests/scissari-agent.integration.test.ts`
  - `LETTA_RUN_SCISSARI_TEST=1 bun test src/integration-tests/scissari-tool-execution-hang.integration.test.ts src/integration-tests/scissari-message-persistence.integration.test.ts src/integration-tests/scissari-tool-parity.integration.test.ts`

## Agent Memory: Scissari/Telegram Test Gating
- `src/integration-tests/scissari-telegram-connection.integration.test.ts` is intentionally skipped unless all required env vars are set:
  - `LETTA_RUN_SCISSARI_TEST=1`
  - `SCISSARI_TELEGRAM_CHAT_ID`
  - `SCISSARI_TELEGRAM_BOT_TOKEN` (or `TELEGRAM_TOKEN`)
- Local Scissari integration defaults:
  - Letta API base URL default: `http://100.80.49.10:8283`
  - Logger API base URL used by reset helpers: `http://100.80.49.10:8284/libraries/local-php-api`

## Agent Memory: Rosemary46 WSL Tailscale Access
- Windows node: `rosemary46-11` at `100.106.176.58`; known SSH user: `rbarn`.
- WSL Ubuntu 24 node: `rosemary46-24` at `100.72.34.38`; known SSH user: `adamsl`; WSL distro name: `Ubuntu-24.04`.
- If `rosemary46-24` is offline but `rosemary46-11` is reachable, SSH to Windows first, then run WSL checks:
  - `ssh -o BatchMode=yes rbarn@100.106.176.58 "wsl -e sh -lc \"echo WSL_OK; uname -a; whoami; tailscale status\""`
  - `ssh -o BatchMode=yes adamsl@100.72.34.38 "echo LINUX_AUTH_OK && systemctl is-active tailscaled && tailscale ip -4"`
- Known fix from 2026-06-25: WSL started during diagnostics, then stopped after the command exited, which made direct SSH to `100.72.34.38` time out again. A Windows scheduled task now keeps WSL alive:
  - Task: `Rosemary46 WSL Tailscale Keepalive`
  - Script: `C:\Users\rbarn\start-rosemary46-wsl-tailscale.ps1`
  - Loop: `wsl.exe -d Ubuntu-24.04 --exec /bin/sh -lc 'while true; do /usr/bin/tailscale ip -4 >/dev/null 2>&1 || true; sleep 300; done'`
- Verify the keepalive from Windows with:
  - `ssh rbarn@100.106.176.58 "powershell -NoProfile -Command \"Get-ScheduledTask -TaskName 'Rosemary46 WSL Tailscale Keepalive' | Select-Object TaskName,State; wsl -l -v\""`

## Agent Memory: Dashboard Project Plans Deployment
- The live Windows 10 dashboard is served from the WSL repo at `/home/adamsl/letta-code`, not `/var/www/html`.
- Dashboard shell: `dashboard/dashboard.html`; server: `dashboard/server.py`; default URL: `http://localhost:8765/`.
- `dashboard/server.py` serves static files from both `dashboard/` and repo root (`/home/adamsl/letta-code`), so repo-root plan pages are addressable as `/<file>.html`.
- Project Plans now include `Mazda Orchestrator`, backed by `/home/adamsl/letta-code/team_construction_plan.html`.
- The old Tool Fix plan was removed: `/home/adamsl/letta-code/agent_self_improvement/mazda_tool_fix_plan.html` should stay gone; the old URL should return 404.
- Frita can advise on dashboard deployment details at Letta agent id `agent-881a883f-edd0-4963-bf67-6ef178b8f018`.
- Verify dashboard plan changes with:
  - `curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8765/team_construction_plan.html`
  - `curl -s http://localhost:8765/ | rg 'Mazda Orchestrator|team_construction_plan|Tool Fix|mazda_tool_fix'`
  - `cd dashboard && .venv/bin/python -m pytest tests/`

## Agent Memory: Dashboard Red Health Recovery
- If the dashboard startup modal shows `SSH win10-wsl-letta: down`, first verify the Windows side is reachable at `NewUser@100.69.80.89`, then start/check WSL:
  - `ssh -o BatchMode=yes NewUser@100.69.80.89 "wsl -l -v"`
  - `ssh -o BatchMode=yes NewUser@100.69.80.89 "wsl.exe -d Ubuntu-24.04 --exec /bin/sh -lc 'systemctl is-active tailscaled; tailscale ip -4'"`
  - `ssh -o BatchMode=yes adamsl@100.80.49.10 "echo LINUX_AUTH_OK && systemctl is-active tailscaled && tailscale ip -4"`
- Known fix from 2026-06-25: `DESKTOP-SHDBATI` WSL stopped after one-shot diagnostics, taking `100.80.49.10` offline. A Windows scheduled task now keeps it alive:
  - Task: `Letta WSL Tailscale Keepalive`
  - Windows user: `DESKTOP-SHDBATI\NewUser`
  - Script: `C:\Users\NewUser\start-letta-wsl-tailscale.ps1`
  - Loop: `wsl.exe -d Ubuntu-24.04 --exec /bin/sh -lc 'while true; do /usr/bin/tailscale ip -4 >/dev/null 2>&1 || true; sleep 300; done'`
  - Verify with: `ssh NewUser@100.69.80.89 "powershell -NoProfile -Command \"Get-ScheduledTask -TaskName 'Letta WSL Tailscale Keepalive' | Select-Object TaskName,State; wsl -l -v\""`
- Letta Docker services run on the WSL node `adamsl@100.80.49.10`; important ports are Letta API `8283`, logger API `8284`, memfs `8285`, Frita executor `8799`, and dashboard proxy `8765`.
- After WSL comes back, Letta may briefly show dashboard `concern` while PostgreSQL recovery and migrations finish. Check:
  - `ssh adamsl@100.80.49.10 "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"`
  - `curl -sS -i --max-time 10 http://100.80.49.10:8283/v1/health/`
  - Wait one Docker healthcheck interval if manual `/v1/health/` is `200 OK` but `docker ps` still says `unhealthy`.
- Android phone health in `dashboard/server.py` uses a Tailscale-layer check, not SSH. `tailscale status` can report `samsung-sm-s156v` / `100.111.161.7` as stale `offline` even when DERP ping succeeds; `tailscale_test()` now falls back to `tailscale ping --c=1 --until-direct=false`.
- Dashboard red/green verification commands:
  - `curl -s http://localhost:8765/api/server-health | python3 -m json.tool`
  - `curl -s http://localhost:8765/api/ssh-connection-health | python3 -m json.tool`
  - Browser URL: `http://localhost:8765/?view=rol-finance-reports`
  - Focused tests: `cd dashboard && .venv/bin/python -m pytest tests/test_server.py -q`
- ROL finance report URLs are dashboard aliases, not raw filesystem paths. Example: `/home/adamsl/rol_finances/readable_documents/bank_statements/january/diners_0587_whole_year_2025/report.html` is served as `/rol_finances_reports/jan-2025/diners_0587_whole_year_2025/report.html`. Add new report directories to `ROL_FINANCE_REPORTS` in `dashboard/server.py` or the dashboard list will say the report is missing.
