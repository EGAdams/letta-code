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
