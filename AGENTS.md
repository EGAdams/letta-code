# Repository Guidelines

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
