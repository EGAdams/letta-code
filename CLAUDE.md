# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Answering style

**Keep replies to about a quarter of their natural length.** Short answer
first, then only what the user cannot infer. Skip preamble, restatements of
the request, and summaries of work the diff already shows. Tables and bullet
lists over paragraphs. Flag real risks in one line, not a section.

## About this project

Letta Code is a CLI (`letta`) for driving stateful Letta agents from the
terminal — a memory-first coding harness on the Letta API. Each session is
tied to a persisted agent that accumulates memory, rather than starting cold.

`dashboard/` is a separate app in the same repo with its own `CLAUDE.md`.
Read that before touching anything under it.

## Commands

```bash
bun install
bun run dev                      # run from TS sources, no build
bun run build                    # bundle -> letta.js, copy skills/, gen types
bun run lint | fix | typecheck | check
bun test
```

Run `bun run build` after editing sources if you use the linked `letta` binary.

## Testing

```bash
bun test src/tests               # unit; safe offline
bun test src/integration-tests   # needs the live Letta server
```

- **~17 pre-existing failures** in `src/tests` (2193 pass) — environment-specific
  or aspirational, not regressions. Startup/smoke tests expect a missing
  `LETTA_API_KEY` but the live server is configured. Some (block-tagging,
  TaskOutput, `waitForBackgroundSubagentLink`) fail only in the full parallel
  run and pass alone. Confirm anything you suspect with
  `git stash && bun test <file> && git stash pop`.
- **Pre-commit**: husky runs lint-staged (biome `--write`) then `typecheck`.
  Only typecheck gates the commit. Use
  `// biome-ignore lint/<rule>: <reason>` where biome can't auto-fix.
- **Live agents write to this tree.** Two `letta.js` processes run in `--yolo`.
  Run `git status` before assuming the tree is clean.

## Git

**Never branch. Everything lands on `origin/main`.** Run the `sync-all` skill
at the start of any session touching `letta-code` or `dashboard/` — the box
serving the dashboard is usually not the one you are typing on. That skill
holds the canonical machine list. Mom's PC: `notes_plans_handoffs/rosemary46_wsl_tailscale.md`.

## Runtime — Bun, not Node

`bun <file>`, `bun test`, `bun build`, `bun install`, `bun run <script>`.
Bun loads `.env` itself; no dotenv.

Prefer built-ins over packages: `Bun.serve()` (not express), `bun:sqlite`,
`Bun.redis`, `Bun.sql`, the global `WebSocket`, `Bun.file`, `` Bun.$`ls` ``.

## Architecture

| Path | What lives there |
|---|---|
| `src/index.ts` | CLI entry: args, startup, agent resolution. Builds to `letta.js`. |
| `build.js` | Bundles, copies `src/skills/builtin/` -> `skills/`, generates types. |
| `src/cli/` | `App.tsx` drives the Ink REPL; `commands/` non-visual handlers; `subcommands/router.ts` routes `letta memfs\|agents\|messages\|blocks\|remote`. |
| `src/agent/` | `client.ts` SDK wrapper, `create.ts`, `message.ts` (SSE), `memory.ts`, `model.ts`, `skills.ts`, `subagents/`. |
| `src/tools/` | `toolDefinitions.ts` registry, `impl/` implementations, `descriptions/` markdown sent to the model, `manager.ts` hooks + per-provider name mapping. |
| `src/skills/` | `builtin/` bundled, `custom/` project-local. |
| `src/permissions/` | Modes `default\|acceptEdits\|plan\|bypassPermissions`; `~/.letta/settings.json` + `.letta/settings.local.json`. |
| `src/hooks/` | Pre/post tool-use hooks loaded from `.letta/hooks/`. |

Agent memory files live at `~/.letta/agents/<agentId>/memory/`.

> **Memory authoring policy (this self-hosted deployment).** Product code is
> unchanged — `memory.ts` still defines the block labels. But here, agent memory
> is authored as markdown committed to the agent's memfs `state.git` (constant
> facts under `system/`), **never** through raw `POST`/`PATCH /v1/blocks`. The
> server projects `system/**` into attached blocks, so blocks are a read-only
> projection of the repo, not a write target. See
> `notes_plans_handoffs/memory_system_plan.html`.
