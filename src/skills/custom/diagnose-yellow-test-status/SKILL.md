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

## Diagnostic Steps

### Step 0: Check localhost:8080 first
**Always start here.** Open `http://localhost:8080` and find the test's accordion section. This is the source of truth for what the test actually logged.

- Note the **last log message** shown
- Check the **LED color** (green = finished, red = error, yellow = running)
- Look at the **exact sequence** of logs to understand where execution stopped

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

## Quick Reference: LED Colors

From `normalizeLoggerMessage()` in test files:

| Color | Trigger | Example |
|-------|---------|---------|
| 🟢 Green | Message contains `PASS`, `PASSED`, or matches `test complete` / `test finished` | `PASS: agent created agent-123 finished` |
| 🔴 Red | Message contains `ERROR` or matches `FAIL`, `FAILED` | `ERROR: CLI exited with code 1` |
| 🟡 Yellow | Anything else | `Using agent_id=...` or `Phase 1 complete` |

**Rule:** To go green, the final message must include the word `PASS` or `finished`.
