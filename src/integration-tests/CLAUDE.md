# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## About This Directory

Integration tests for the `letta-code` CLI. Tests spawn the real CLI process (`bun run dev`) and interact with a live Letta API, verifying end-to-end behavior of flags, wire formats, approval flows, and agent interactions.

## Commands

```bash
# Run from the project root (/home/adamsl/letta-code)
bun test                                                      # All tests
bun test src/integration-tests/startup-flow.integration.test.ts  # Single file
bun test --testNamePattern "creates agent"                    # Single test by name

# Run the full integration suite with a one-time logviewer reset
bash src/integration-tests/run-integration-tests.sh

# Clear all remote loggers (run from this directory)
bun clear-loggers.ts

# Run CLI as the tests do
bun run dev --new-agent -m gpt-5.4-mini-plus-pro-medium -p "Say OK" --output-format json
```

## Required Environment Variables

| Variable | Required | Description |
|---|---|---|
| `LETTA_API_KEY` | Yes | Authenticates with the Letta API |
| `LETTA_BASE_URL` | No | Defaults to `http://100.80.49.10:8283` in Scissari tests |
| `LETTA_RUN_SCISSARI_TEST` | No | Set to `1` to enable Scissari agent tests |
| `SCISSARI_TELEGRAM_BOT_TOKEN` | No | Telegram bot token for Scissari bridge test (falls back to `TELEGRAM_TOKEN`) |
| `SCISSARI_TELEGRAM_CHAT_ID` | No | Telegram chat ID used by Scissari bridge test |
| `LETTA_LOGGER_RESET_API` | No | Override logger reset API (default: `http://localhost:8080/php-api`) |
| `LETTA_LOGGER_AUTO_RESET` | No | Set to `1` to re-enable automatic `resetAllLoggers()` in `beforeEach` |
| `LETTA_LOGGER_RESET_DISABLED` | No | Set to `1` to force `resetAllLoggers()` to skip even if auto-reset is enabled |
| `LETTA_LOGGER_RESET_TIMEOUT_MS` | No | Per-logger reset timeout (default: 15000) |
| `LETTA_LOGGER_RESET_CONCURRENCY` | No | Parallel resets per batch (default: 4) |

Tests automatically set `LETTA_CODE_AGENT_ROLE=subagent` when spawning subprocesses to prevent polluting user LRU agent settings.

## Architecture

### Test structure
Each test file follows the same pattern:
1. `beforeEach` calls `resetAllLoggers()` — this now skips by default unless `LETTA_LOGGER_AUTO_RESET=1`
2. `runCli()` helper spawns `bun run dev` via `node:child_process`, captures stdout/stderr, handles timeouts and retries
3. `RemoteLogger` streams test progress to the logger API, with the local viewer proxy defaulting to `http://localhost:8080/php-api` for explicit flush operations
4. Tests parse `--output-format json` stdout to assert on `agent_id`, `conversation_id`, etc.

### Key files
- `logger-helpers.ts` — `ALL_LOGGER_IDS` registry (source of truth for all logger IDs), `resetAllLoggers()`, `resetLogger()`
- `clear-loggers.ts` — standalone script to explicitly flush all logger state from the remote API
- `run-integration-tests.sh` — full-suite launcher; clears every logger once before Bun starts, then runs all `*.test.ts` and `*.integration.test.ts` files
- `oauth-health-check.ts` — standalone script (not a test) for checking OAuth token validity

### Test files
| File | What it covers |
|---|---|
| `startup-flow.integration.test.ts` | CLI flags: `--agent`, `--conversation`, `--new-agent`, `--import`, `--init-blocks` |
| `headless-input-format.test.ts` | `--input-format stream-json` bidirectional wire protocol |
| `headless-stream-json-format.test.ts` | `--output-format stream-json` message shape/structure |
| `headless-error-format.test.ts` | Error message subtypes and structure in headless mode |
| `lazy-approval-recovery.test.ts` | Approval conflict recovery (LET-7101) |
| `prestream-approval-recovery.test.ts` | Pre-stream approval state recovery |
| `scissari-agent.integration.test.ts` | Specific agent (ID hardcoded) — requires `LETTA_RUN_SCISSARI_TEST=1` |
| `scissari-tool-parity.integration.test.ts` | Live regression check that loading/reconciling Scissari does not rewrite her tool set to the legacy `web_search`/`fetch_webpage` pair — requires `LETTA_RUN_SCISSARI_TEST=1` |
| `scissari-message-persistence.integration.test.ts` | Verifies Scissari's run completes with a model response and that the second test confirms no reasoning-only output — requires `LETTA_RUN_SCISSARI_TEST=1` |
| `scissari-hailey-interaction.integration.test.ts` | Verifies Scissari can ask Hailey a question and relay the answer; also checks `tool_return_message` context is persisted in the run — requires `LETTA_RUN_SCISSARI_TEST=1` |
| `scissari-tool-execution-hang.integration.test.ts` | Detects post-approval tool-execution hang: approves a tool, asserts agent completes within 95 s; fails if agent loops in `stopReason="error"` retry after tool result — requires `LETTA_RUN_SCISSARI_TEST=1` |
| `scissari-telegram-connection.integration.test.ts` | Telegram bridge wiring into Scissari — requires `LETTA_RUN_SCISSARI_TEST=1`, `SCISSARI_TELEGRAM_CHAT_ID`, and `SCISSARI_TELEGRAM_BOT_TOKEN` (or `TELEGRAM_TOKEN`) |

### RemoteLogger and LED status
`RemoteLogger` (at `../logger/RemoteLogger.ts`) posts log entries to a PHP API. The LED color is controlled by message content:
- Messages containing `PASS`, `finished`, or `test complete` → green LED
- Messages containing `ERROR`, `FAIL`, or timeout-like patterns → red LED
- All other messages → yellow (running)

Each test wraps `RemoteLogger` in a graceful-degradation pattern: `loggerReady` flag gates all remote logging so logger failures never fail tests.

`normalizeLoggerMessage()` in each test file maps test assertion keywords to the LED trigger format expected by the viewer.

#### Yellow viewer incident note
If `HeadlessInput_InitControl_2026` appears stuck on `Test started: initialize control request returns session info`, do not assume the test is hanging. The fastest triage sequence is:

1. Reproduce the test in isolation:
   `bun test --test-name-pattern 'initialize control request returns session info' src/integration-tests/headless-input-format.test.ts`
2. Inspect the live row directly:
   `curl -s "http://100.80.49.10:8284/libraries/local-php-api/object/select?object_view_id=HeadlessInput_InitControl_2026"`
3. If that returns `null`, run a fresh insert/select smoke test with a new temporary logger id to confirm the API still persists new rows.
4. If smoke-test persistence works, treat the yellow viewer state as stale/missing row data rather than a test failure.

### Adding a new test logger
1. Add the logger ID string to `ALL_LOGGER_IDS` in `logger-helpers.ts`
2. Register it in the log viewer at `/home/adamsl/the-factory/public/index.html` (accordion section)

### Bidirectional tests (stream-json)
`runBidirectional()` in `headless-input-format.test.ts` uses an event-driven approach:
- Waits for a `system:init` event before sending the first input
- Tracks expected response count based on input types (`user` → result, `control_request` → control_response)
- Closes stdin 500ms after all expected responses are received

### Timeouts
- `TEST_TIMEOUT_MS = 30000` — default for `testWithTimeout` wrapper
- `runCli` default timeout: 30s for simple operations, 180s for agent-creating operations
- Tests that create agents pass `{ timeout: 190000 }` to `test()` to override the suite-level timeout

### Stale bail sentinel and process cleanup
- `resetAllLoggers()` aborts the file if `/tmp/letta-integration-bail` exists and is newer than the current test process.
- If that file is stale from a previous run, `resetAllLoggers()` now clears it automatically.
- To kill the integration test runner and its tracked child process, use:
  `src/integration-tests/kill-running-tests.sh`
- The test launcher writes a pidfile at `/tmp/letta-integration-tests.*.pid` by default. The killer script reads that file first, then falls back to matching `bun test src/integration-tests` and `bun run dev` processes if needed.
- If you see `[resetAllLoggers] Bail sentinel detected — aborting test file.`, look first for a stale pidfile or an unclean shutdown from a previous integration run.

### First checks for logviewer issues
- If the logviewer starts dirty or a run looks contaminated, start with `src/integration-tests/run-integration-tests.sh` because it performs the one-time full reset before the suite begins.
- If you need to clear log state manually outside the runner, use `bun clear-loggers.ts` from this directory.

### Letta 0.16.3: runs.messages persistence quirk

`client.runs.messages.list(runId)` only ever returns the initiating `user_message` on Letta 0.16.3. The step's `messages` field is always `[]`. **Do not assert for `assistant_message` in `runs.messages`.**

To verify a run completed with a real model response, use:
```ts
const run = await client.runs.retrieve(runId);          // check status === "completed"
const page = await client.runs.steps.list(runId, { limit: 10 });
const step = page.getPaginatedItems().find(s => s.status === "success" && s.completion_tokens > 0);
```

Client tool results (e.g. from `send_message_to_agent_and_wait_for_reply`) ARE returned as `user_message` entries in `runs.messages` and can be searched normally.

### Scissari agent details

- Agent ID: `agent-5955b0c2-7922-4ffe-9e43-b116053b80fa`
- Model: `gpt-5.3-codex`
- Known issue: after `Planning()` approval, the interactive CLI can hang 2+ minutes with no content (only pings). Fixed in `src/cli/helpers/stream.ts` with a 90-second content-inactivity timer (2026-05-09).
