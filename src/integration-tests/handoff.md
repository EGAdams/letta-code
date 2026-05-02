# Handoff — 2026-04-29

## Problem
`StartupFlow_AgentNotFound_2026` test is stuck showing **yellow** (running) in the LED log viewer at localhost:8080. The test logs "Test started" but never reaches PASS or FAIL.

## Test location
`src/integration-tests/startup-flow.integration.test.ts` — test name: `"--agent with nonexistent ID shows error"` (~line 167)

## What we know
- The CLI **does** exit with code 1 and **does** output "not found" to stderr when run manually:
  ```
  bun run dev --agent agent-definitely-does-not-exist-12345 -p test
  # stderr: "Agent agent-definitely-does-not-exist-12345 not found"
  # exit: 1
  ```
- The test itself was timing out when run via `bun test` — it never completed within 90s.
- No `LETTA_API_KEY` is in `.env` (only `LETTA_BASE_URL=http://100.80.49.10:8283`). API key comes from shell environment.
- The `runCli` helper uses `{ expectExit: 1, timeoutMs: 60000 }` for this test.

## Suspected cause
The test is hanging inside `runCli` — possibly because `resetAllLoggers()` in `beforeEach` is blocking, or the spawned `bun run dev` process is not exiting promptly in the test environment (e.g., API key not in subprocess env, or network issue reaching 100.80.49.10:8283).

## Next steps
1. Run with `LETTA_LOGGER_RESET_DISABLED=1` to skip `resetAllLoggers()` and see if that's the hang point.
2. Add `console.log` timing around `resetAllLoggers()` in `beforeEach`.
3. Check if `LETTA_API_KEY` is exported to the subprocess env in the test runner context.
4. Consider adding a FAIL log in a `try/catch` around the `runCli` call so the LED shows red on failure instead of staying yellow.
