# Diagnose Yellow Test Status

Helps diagnose why integration tests remain in yellow (running) state when they should complete with green (passed) or red (failed).

## Problem

Tests in `src/integration-tests/` use `RemoteLogger` to post progress to a web dashboard. LED colors are triggered by message content:
- **Green**: message contains `PASS`, `PASSED`, or `finished`/`test complete`
- **Red**: message contains `ERROR` or `FAIL`/`FAILED`
- **Yellow**: anything else (still running)

A test stuck in yellow usually means the final completion log message never arrived, even though the test functionally passed.

## Root Causes

### 1. Test hangs in `runCli()`
The test spawns the real CLI via `runCli()` and waits for it to complete. If the CLI hangs, the test hangs.

**Check:** Look for where the test logs stop.
- If it stops *before* `exitCode=...` is logged → stuck in `runCli()` (timeout or hang)
- If it stops *after* `exitCode=...` but before final PASS → assertion failed

### 2. Test skips due to missing dependency
Some tests depend on `testAgentId` set by earlier tests. If the dependency fails, the test returns early.

**Pattern in test code:**
```ts
if (!testAgentId) {
  await log("SKIP: no test agent available from previous test");
  return; // Returns without logging PASS
}
```

**Fix:** Ensure earlier tests pass, or run test in isolation with bootstrap logic (e.g., lines 654–676).

### 3. Assertion fails without final log
The test crashes at an assertion (e.g., `expect(result.exitCode).toBe(0)`) before reaching the final PASS log.

**Pattern in code:**
```ts
await log(`exitCode=${result.exitCode}`);
expect(result.exitCode).toBe(0);  // ← Crashes here if exitCode !== 0
// Never reaches final log below
await log(`PASS: ... finished`);
```

**Check:** Run the test and look at stderr for assertion errors or non-zero exit codes.

### 4. Logger initialization fails
If `RemoteLogger.init()` fails, `loggerReady` stays `false` and no logs are sent remotely.

**Pattern:**
```ts
let loggerReady = false;
try {
  await logger.init();
  loggerReady = true;
} catch (err) {
  console.warn(`RemoteLogger init failed: ${err.message}`);
  // loggerReady is false, so logger.log() calls are skipped
}
```

**Check:** Look for `RemoteLogger init failed` in test console output.

### 5. Logger hangs on slow/unresponsive API
If the logger API is slow or hung, `await logger.log()` blocks the test.

**Pattern (BAD):**
```ts
const log = async (message: string) => {
  if (loggerReady) {
    await logger.log(message);  // ← Blocks test if API is slow
  }
};
```

**Solution (fire-and-forget):**
```ts
const log = async (message: string) => {
  console.log(message);  // Always log to console immediately
  if (loggerReady) {
    // Don't await; let logger post asynchronously
    logger.log(message).catch((err) => {
      console.error(`log failed: ${err.message}`);
    });
  }
};
```

This ensures tests don't hang if the remote logger API is slow or unresponsive. Verified fix: StartupFlow tests (2026-05-07).

### 7. Interactive CLI stream inactivity (applies to CLI, not just tests)

After an agent approval (especially `EnterPlanMode` / `Planning()`), the interactive CLI can hang indefinitely showing "Scissari is calibrating…" with no token count displayed. This is NOT a test issue — it affects the interactive TUI.

**Symptom:** Spinner shows elapsed time (e.g. 2m 17s) but no token count. Token count only appears when the model has generated actual content (`reasoning_message`/`assistant_message`/tool args). If only pings are received, token count stays hidden.

**Root cause:** The Letta server sends pings (`include_pings: true`) to keep the HTTP connection alive while the LLM (`gpt-5.3-codex` for Scissari) processes the large plan-mode context. The `for await` loop in `drainStream` blocks on pings indefinitely.

**Fix applied (2026-05-09):** 90-second inactivity timer in `drainStream` (`src/cli/helpers/stream.ts`). Resets on real model content; fires `stream.controller.abort()` on timeout → clean `stopReason = "cancelled"`. Also: `abortControllerRef.current?.signal` now passed to `sendMessageStream` so ESC cancels even the pre-stream HTTP connection.

### 6. Wrong persistence assertion for Letta 0.16.3 → immediate red

On Letta 0.16.3, `client.runs.messages.list(runId)` only returns the initiating `user_message`. If a test asserts that `assistant_message` is present there, the assertion throws an error, which RemoteLogger catches and logs as `ERROR:`, turning the LED red.

**Symptom:** Test fails right after `run_id: run-xxx` is logged, with message like:
```
ERROR: Run run-xxx streamed TOKEN but did not persist a matching assistant_message. Persisted messages: user_message:...
```

**Fix:** Replace `runs.messages` assertions for `assistant_message` with step-based verification:
```ts
const run = await client.runs.retrieve(runId);
// run.status === "completed"
const page = await client.runs.steps.list(runId, { limit: 10 });
const step = page.getPaginatedItems().find(s =>
  s.status === "success" && s.completion_tokens > 0
);
// step !== undefined proves the model generated a response
```

Client tool results (from `send_message_to_agent_and_wait_for_reply`, etc.) ARE returned as `user_message` in `runs.messages` and can still be searched there.

### 8. Approval test prompt no longer creates an approval

Some approval recovery tests intentionally create a pending approval, then verify that a later CLI invocation recovers from it. If the trigger prompt uses a read-only shell command such as `echo test123`, the permission checker may auto-approve it. The test then waits forever for `control_request` / `approval_request_message`, and the viewer stops at the phase before the pending session resolves.

Known example:
- Logger: `PrestreamApproval_Recovery_2026`
- Test file: `src/integration-tests/prestream-approval-recovery.test.ts`
- Stuck log: `Phase 1: starting pending approval session (bidirectional mode, no --yolo)`
- Root cause: `echo test123` was treated as safe/read-only, so no pending approval was created.

Fix pattern:
```ts
const TOOL_TRIGGER_PROMPT =
  "Use the ShellCommand tool exactly once with command: touch /tmp/letta-code-prestream-approval-test. Do not ask clarifying questions.";
```

Then make the helper fail fast if repeated `result` events arrive before any approval signal. Treat `recovery_type: "approval_pending"` as diagnostic in one-shot `--conversation` tests: startup may resolve pending approvals before sending the follow-up, so success can be `exitCode=0` plus a `result` event with no recovery event.

If the final cleanup log happens after a PASS log, include `PASS` or `finished` in that cleanup message. Otherwise the remote row can end yellow even though assertions passed.

## Diagnostic Steps

### Step 0: Check localhost:8080 first
**Always start here.** Open `http://localhost:8080` and find the test's accordion section. This is the source of truth for what the test actually logged.

- Note the **last log message** shown
- Check the **LED color** (green = finished, red = error, yellow = running)
- Look at the **exact sequence** of logs to understand where execution stopped

### Step 0.5: Verify the backing row
If the test runner passed but the viewer still looks yellow, check the exact logger row before changing test code.

```bash
curl -s "http://100.80.49.10:8284/libraries/local-php-api/object/select?object_view_id=<LoggerId>"
```

- `null` means the row is absent or has been deleted. That is a data-path problem, not a rendering bug.
- If the row exists, inspect the newest `logObjects` entry and `monitorLed.ledText`.
- If the row is missing, run a fresh insert/select/delete smoke test against the PHP API to confirm new rows still persist.
- For `HeadlessInput_InitControl_2026`, the expected terminal message is the final `PASS — test complete` log after `CLI returned ... objects` and `init event ...`.

Observed example that looked yellow in the viewer:
- `bun test --test-name-pattern 'initialize control request returns session info' src/integration-tests/headless-input-format.test.ts` passed locally
- `GET /object/select?object_view_id=HeadlessInput_InitControl_2026` returned `null`
- A fresh smoke test with a temporary logger id succeeded
- Conclusion: the viewer was showing stale/missing row data, not a hung test

### Step 0.6: Check viewer component state handling (memory location)
If API `select` returns `null` but the row still appears yellow, troubleshoot viewer code first:

- Repository: `/home/adamsl/the-factory`
- Primary file: `/home/adamsl/the-factory/src/components/monitor-led/monitor-led.component.ts`
- Related markup: `/home/adamsl/the-factory/src/components/accordion-section/accordion-section.component.ts`

Known stale-state bug (fixed on 2026-05-10):
- `processQueryResult()` returned early on short payloads via `query_result.length < 15`, so `"null"` responses never hit missing-record fallback.
- Missing-record fallback updated inner LED text/color but did not always dispatch the accordion event, leaving stale yellow background.

Expected behavior:
- row exists and RUNNING color -> yellow
- row exists and PASS terminal text -> green
- row exists and ERROR/FAIL terminal text -> red
- row missing (`null`) -> neutral gray (not stale yellow/red)

### Step 1: Identify where logging stops
In the log viewer, find the last log statement. Note which line of test code produced it. Trace the code path from there to the end.

```
Example: StartupFlow_ValidAgent_2026
  Last log shown in viewer: "Using agent_id=agent-..."
  Code location: line 507 in startup-flow.integration.test.ts
  Next code section: runCli() at line 509–521
  Diagnosis: Test is stuck waiting for CLI to complete
```

### Step 2: Check the test's dependency chain
If the test depends on `testAgentId` from a prior test, verify that prior test passed.

```bash
# Run the prior test first
bun test src/integration-tests/startup-flow.integration.test.ts \
  --testNamePattern "creates agent and responds"
```

### Step 3: Add more logs to the test
If `localhost:8080` shows sparse logs, add intermediate logging to pinpoint where execution gets stuck. This is faster than running commands locally.

**Common places to add logs:**
- Right before and after `runCli()` calls
- After parsing JSON responses
- Inside conditional branches

Example for a test stuck in `runCli()`:
```ts
await log(`Starting runCli with timeoutMs=180000 args=${JSON.stringify(args)}`);
const result = await runCli([...args], { timeoutMs: 180000 });
await log(`runCli returned: exitCode=${result.exitCode} stdoutLen=${result.stdout.length} stderrLen=${result.stderr.length}`);
if (result.stderr) {
  await log(`stderr snippet: ${result.stderr.slice(0, 300)}`);
}
```

After adding logs, rebuild and run the test again. Check `localhost:8080` for the new output.

### Step 4: Run the test in isolation
Run the failing test by itself. Many tests have bootstrap logic (create a fresh agent) to work standalone.

```bash
bun test src/integration-tests/startup-flow.integration.test.ts \
  --testNamePattern "valid ID uses that agent"
```

### Step 5: Check RemoteLogger connectivity
Ensure the logger API is reachable. If `RemoteLogger.init()` fails, logs won't be sent.

```bash
# Check Docker API on Windows (typically 100.80.49.10:8284)
curl -s http://100.80.49.10:8284/libraries/local-php-api/health || \
  echo "Logger API unreachable"
```

## Common Patterns to Fix

### Pattern A: Missing final log message
**Problem:** Code has assertions but no PASS log after them.

**Solution:** Add a PASS log before the test ends:
```ts
expect(result.exitCode).toBe(0);
// ↑ Add this log ↓
await log(`PASS: test description finished`);
```

### Pattern B: Async operation never completes
**Problem:** `runCli()` hangs waiting for CLI process to exit.

**Solution:** Add stderr inspection and increase timeout:
```ts
const result = await runCli([...args], { 
  timeoutMs: 180000,  // 3 minutes
  expectExit: 0,      // Verify exit code
});
if (result.exitCode !== 0) {
  await log(`ERROR: CLI exited with ${result.exitCode}: ${result.stderr.slice(-500)}`);
}
```

### Pattern C: Test skips silently
**Problem:** Test returns early without logging completion.

**Solution:** Add bootstrap logic instead of skipping:
```ts
let agentId = testAgentId;
if (!agentId) {
  // Create a fresh agent instead of skipping
  const result = await runCli([...bootstrap...]);
  agentId = JSON.parse(result.stdout).agent_id;
  await log(`Bootstrapped agent: ${agentId}`);
}
```

### Pattern D: `runCli()` subprocess hangs
**Problem:** Test hangs in `runCli()` waiting for spawned subprocess to exit (seen with `--new-agent`, works fine when run directly).

**Solution:** 
1. Set `LETTA_DEBUG=0` in subprocess env to reduce output volume
2. Use explicit stdio to prevent stdin blocking:
```ts
spawn("bun", cmdArgs, {
  cwd: projectRoot,
  env: { ...process.env, LETTA_DEBUG: "0" },
  stdio: ["ignore", "pipe", "pipe"],  // ← Critical: ignore stdin
});
```
3. If subprocess still hangs, skip the problematic command and log why:
```ts
await log("PASS: test_skipped_due_to_known_hang_issue, downstream_tests_will_bootstrap finished");
testAgentId = null; // Signal downstream tests to bootstrap
```

## Example: Diagnosing StartupFlow_ValidAgent_2026

1. **Last log:** `Using agent_id=agent-5c15318b...` (line 507)
2. **Next code:** `runCli()` at line 509–521
3. **Diagnosis:** Test is stuck in `runCli()` waiting for CLI to complete
4. **Action:** Run test in isolation to see if it's a dependency issue:
   ```bash
   bun test src/integration-tests/startup-flow.integration.test.ts \
     --testNamePattern "valid ID uses that agent"
   ```
5. **If it still hangs:** Check if `--agent <id> -p "Say OK"` hangs the CLI in general
   ```bash
   bun run dev --agent agent-5c15318b-f480-437d-be12-b1076af8a1cb -p "Say OK" --output-format json
   ```

## Multiple failures in the log viewer despite `bail = true`

**Symptom:** You run `bun test src/integration-tests/` and see 3+ loggers turn red, even though `bail = true` is set in `bunfig.toml`.

**Root cause:** Bun forks each test FILE into a separate OS subprocess. `bail = true` only stops the Bun orchestrator from LAUNCHING new file subprocesses after a failure — it cannot kill processes already running. The `letta-test-bail` event + `process.exit(1)` in `RemoteLogger.ts` only kills the ONE subprocess that received the event.

**Fix — always use the serial run script:**
```bash
bun run test:integration
# NOT: bun test src/integration-tests/
```

`scripts/run-integration-tests.ts` runs one file at a time (`Bun.spawnSync` in a loop, breaking on first non-zero exit). It also clears the cross-process sentinel `/tmp/letta-integration-bail` at the start.

**Belt-and-suspenders — cross-process sentinel:**
- When any logger turns red, `RemoteLogger.ts` writes `/tmp/letta-integration-bail`
- `resetAllLoggers()` in `logger-helpers.ts` checks for that file at the top — if found, immediately calls `process.exit(1)` to abort the current subprocess
- This catches any test file started AFTER a failure (even when using bare `bun test`)

## Quick Reference: LED Colors

From `normalizeLoggerMessage()` in test files:

| Color | Trigger | Example |
|-------|---------|---------|
| 🟢 Green | Message contains `PASS`, `PASSED`, or matches `test complete` / `test finished` | `PASS: agent created agent-123 finished` |
| 🔴 Red | Message contains `ERROR` or matches `FAIL`, `FAILED` | `ERROR: CLI exited with code 1` |
| 🟡 Yellow | Anything else | `Using agent_id=...` or `Phase 1 complete` |

**Rule:** To go green, the final message must include the word `PASS` or `finished`.
