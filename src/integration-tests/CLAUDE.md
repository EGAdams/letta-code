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
| `LETTA_LOGGER_RESET_API` | No | Override logger reset API (default: americansjewelry.com PHP API) |
| `LETTA_LOGGER_RESET_DISABLED` | No | Set to `1` to skip `resetAllLoggers()` in `beforeEach` |
| `LETTA_LOGGER_RESET_TIMEOUT_MS` | No | Per-logger reset timeout (default: 15000) |
| `LETTA_LOGGER_RESET_CONCURRENCY` | No | Parallel resets per batch (default: 4) |

Tests automatically set `LETTA_CODE_AGENT_ROLE=subagent` when spawning subprocesses to prevent polluting user LRU agent settings.

## Architecture

### Test structure
Each test file follows the same pattern:
1. `beforeEach` calls `resetAllLoggers()` — clears all remote logger state before each test
2. `runCli()` helper spawns `bun run dev` via `node:child_process`, captures stdout/stderr, handles timeouts and retries
3. `RemoteLogger` streams test progress to the americansjewelry.com PHP API for external visibility (LED status board)
4. Tests parse `--output-format json` stdout to assert on `agent_id`, `conversation_id`, etc.

### Key files
- `logger-helpers.ts` — `ALL_LOGGER_IDS` registry (source of truth for all logger IDs), `resetAllLoggers()`, `resetLogger()`
- `clear-loggers.ts` — standalone script to delete all logger state from the remote API
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

### RemoteLogger and LED status
`RemoteLogger` (at `../logger/RemoteLogger.ts`) posts log entries to a PHP API. The LED color is controlled by message content:
- Messages containing `PASS`, `finished`, or `test complete` → green LED
- Messages containing `ERROR`, `FAIL`, or timeout-like patterns → red LED
- All other messages → yellow (running)

Each test wraps `RemoteLogger` in a graceful-degradation pattern: `loggerReady` flag gates all remote logging so logger failures never fail tests.

`normalizeLoggerMessage()` in each test file maps test assertion keywords to the LED trigger format expected by the viewer.

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
