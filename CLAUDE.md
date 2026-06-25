# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## About This Project

Letta Code is a CLI tool (`letta`) for interacting with stateful Letta agents from the terminal. It is a memory-first coding harness built on top of the Letta API. Unlike session-based tools, each session is tied to a persisted agent that accumulates memory over time.

## Commands

```bash
# Development
bun install           # Install deps
bun run dev           # Run from TypeScript sources directly (no build required)
bun run dev -- -p "Hello world"  # Run with args

# Build
bun run build         # Bundle src/index.ts → letta.js + copy skills/ + generate types

# Linting & type checking
bun run lint          # Check with Biome
bun run fix           # Auto-fix with Biome
bun run typecheck     # TypeScript type checking (tsc --noEmit)
bun run check         # Custom check script (scripts/check.js)

# Testing
bun test
bun run test:update-chain:manual
bun run test:update-chain:startup
```

After editing source files, run `bun run build` before using the linked `letta` binary.

## Testing environment

```bash
bun test src/tests              # unit tests (217 files) — safe to run offline
bun test src/integration-tests  # needs live Letta server at http://100.80.49.10:8283
LETTA_RUN_TOOL_ATTACH_TEST=1 bun test src/integration-tests/tool-attach.integration.test.ts
```

**Pre-commit hook**: Husky runs `bunx lint-staged` (biome `--write` on staged `.ts` files) then `bun run typecheck`. Only `typecheck` gates the commit — biome lint-staged failures are non-fatal. Fix TypeScript errors first; use `// biome-ignore lint/<rule>: <reason>` for non-auto-fixable biome issues.

**Pre-existing failures** (as of 2026-05-25): `bun test src/tests` shows ~17 failures (2193 pass) — all environment-specific or aspirational tests, not regressions. Startup/smoke tests expect "Missing LETTA_API_KEY" but the live server is configured. `reconcileExistingAgentState > updates missing compaction model` expects `tools.list` calls that the implementation doesn't make (unimplemented feature). Some failures (block-tagging, TaskOutput, waitForBackgroundSubagentLink) only appear in the full parallel run — they pass in isolation. Verify pre-existing status via `git stash && bun test <file> && git stash pop`.

**Live agents**: Two letta.js processes run in `--yolo` mode and write to the working tree concurrently. Run `git status` before assuming the tree is clean.

**Rosemary46 WSL Tailscale access**: Mom's PC has Windows node `rosemary46-11`
at `100.106.176.58` with SSH user `rbarn`, and WSL Ubuntu node
`rosemary46-24` at `100.72.34.38` with SSH user `adamsl`. If the Linux node is
offline but Windows is reachable, SSH to Windows and check `wsl -l -v` plus
`wsl -e sh -lc "tailscale status"`. Known fix from 2026-06-25: `Ubuntu-24.04`
was stopping after one-shot WSL commands, so `tailscaled` disappeared again. A
Windows scheduled task named `Rosemary46 WSL Tailscale Keepalive` runs
`C:\Users\rbarn\start-rosemary46-wsl-tailscale.ps1`, which keeps
`Ubuntu-24.04` alive with a harmless `tailscale ip` loop. Verify with
`Get-ScheduledTask -TaskName 'Rosemary46 WSL Tailscale Keepalive'` and direct
`ssh adamsl@100.72.34.38 "echo LINUX_AUTH_OK && systemctl is-active tailscaled && tailscale ip -4"`.

## Runtime

Default to using Bun instead of Node.js.

- Use `bun <file>` instead of `node <file>` or `ts-node <file>`
- Use `bun test` instead of `jest` or `vitest`
- Use `bun build <file.html|file.ts|file.css>` instead of `webpack` or `esbuild`
- Use `bun install` instead of `npm install` or `yarn install` or `pnpm install`
- Use `bun run <script>` instead of `npm run <script>` or `yarn run <script>` or `pnpm run <script>`
- Bun automatically loads .env, so don't use dotenv.

### APIs

- `Bun.serve()` supports WebSockets, HTTPS, and routes. Don't use `express`.
- `bun:sqlite` for SQLite. Don't use `better-sqlite3`.
- `Bun.redis` for Redis. Don't use `ioredis`.
- `Bun.sql` for Postgres. Don't use `pg` or `postgres.js`.
- `WebSocket` is built-in. Don't use `ws`.
- Prefer `Bun.file` over `node:fs`'s readFile/writeFile
- Bun.$`ls` instead of execa.

## Architecture

### Entry points
- `src/index.ts` — CLI entry point (arg parsing, startup, agent resolution). Builds to `letta.js`.
- `build.js` — Bun build script; bundles everything to `letta.js`, copies `src/skills/builtin/` → `skills/`, and generates `dist/types/protocol.d.ts`.

### CLI layer (`src/cli/`)
- `App.tsx` — Main React/Ink component that drives the interactive REPL (conversation state, tool approval UI, streaming).
- `commands/` — Non-visual command handlers (e.g., `/connect`, `/model`, `/skill`).
- `subcommands/router.ts` — Routes CLI subcommands: `letta memfs`, `letta agents`, `letta messages`, `letta blocks`, `letta remote`.
- The UI is built with **Ink** (React for terminals) and **ink-spinner**, **ink-text-input**, etc.

### Agent layer (`src/agent/`)
- `client.ts` — Wraps `@letta-ai/letta-client` SDK; connects to Letta Cloud or a self-hosted server.
- `create.ts` — Creates new agents on the Letta backend with default memory blocks.
- `message.ts` — Streams agent responses via Server-Sent Events.
- `memory.ts` — Defines memory block labels: `persona` and `human` (global blocks). Memory files live at `~/.letta/agents/<agentId>/memory/`.
- `memoryFilesystem.ts` — Helpers for `~/.letta/` directory structure.

> **Memory authoring policy (self-hosted deployment).** The product code above is
> unchanged — `memory.ts` still defines block labels. But on this server, agent memory is
> authored as markdown files committed to the agent's memfs `state.git` (constant facts
> under `system/`), **not** through raw `POST`/`PATCH /v1/blocks` calls. The server
> projects `system/**` files into attached blocks, so blocks are a read-only projection of
> the repository, not a write target. See `notes_plans_handoffs/memory_system_plan.html`.
- `model.ts` — Model resolution and LLM config updates.
- `skills.ts` / `skillSources.ts` — Skill loading and injection into agent context.
- `subagents/` — Parallel subagent support.

### Tools layer (`src/tools/`)
- `toolDefinitions.ts` — Central registry mapping tool names to implementations and markdown descriptions. Supports multiple toolsets for different providers (Anthropic, Gemini, Codex).
- `impl/` — Individual tool implementations (Bash, Read, Edit, Write, Glob, Grep, etc.).
- `descriptions/` — Markdown files that serve as tool descriptions sent to the model.
- `manager.ts` — Loads tools, manages pre/post-tool-use hooks, handles provider-specific tool name mappings.
- Multiple toolsets exist for different AI providers with name mappings (e.g., `glob_gemini` → `glob`).

### Skills system (`src/skills/`)
- `builtin/` — Built-in skills bundled with the CLI (copied to `skills/` at build time).
- `custom/` — Project-local skills.
- Skills are `.skill` files (markdown-based) that teach the agent reusable capabilities.

### Permissions (`src/permissions/`)
- Modes: `default`, `acceptEdits`, `plan`, `bypassPermissions`.
- Settings stored in `~/.letta/settings.json` (global) and `.letta/settings.local.json` (project).

### Hooks (`src/hooks/`)
- `index.ts` — Orchestrates pre/post tool use hook execution.
- `loader.ts` — Loads hook scripts from `.letta/hooks/` in the project directory.
- Hook shell scripts in the repo's `hooks/` directory serve as examples.
