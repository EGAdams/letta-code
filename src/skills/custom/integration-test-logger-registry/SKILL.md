---
name: integration-test-logger-registry
description: Maintains logger ID coverage and reset stability for src/integration-tests. Use when adding/changing RemoteLogger IDs, when resetAllLoggers() behavior changes, or when integration tests intermittently time out due logger transport and cleanup pressure.
---

# Integration Test Logger Registry

## Purpose

`src/integration-tests/logger-helpers.ts` controls:
- `ALL_LOGGER_IDS` (every logger ID used by tests)
- `resetLogger()` behavior and timeout
- `resetAllLoggers()` batching/concurrency
- reset API target selection

If this registry is stale or reset behavior is too aggressive, tests fail for infrastructure reasons and logger LEDs remain in running/yellow states.

## Current expected behavior

`logger-helpers.ts` should:
- default reset API to direct upstream:
  - `https://americansjewelry.com/libraries/local-php-api/index.php`
- allow override with `LETTA_LOGGER_RESET_API`
- use bounded reset concurrency (batched, not all-at-once)
- use a reset timeout longer than Bun's default per-test timeout
- avoid `selectAll` for health checks and logger persistence verification

Environment knobs:
- `LETTA_LOGGER_RESET_API`
- `LETTA_LOGGER_RESET_TIMEOUT_MS`
- `LETTA_LOGGER_RESET_CONCURRENCY`

## Rule 1: keep ALL_LOGGER_IDS complete

Every `new RemoteLogger("SomeId_2026")` used in tests must be present in `ALL_LOGGER_IDS`.

If missing:
- old logs leak between runs
- viewer state becomes misleading
- pass/fail interpretation becomes noisy

Viewer registration policy:
- `http://localhost:8080/` should include only loggers that currently have data, unless intentionally debugging a placeholder.
- Each visible logger must have a matching `<accordion-section ... monitored_object_id="...">` in
  `/home/adamsl/the-factory/public/index.html`.
- Missing rows produce `404` from per-object fetch. Do not add every ID from `ALL_LOGGER_IDS` to the viewer by default.

## Rule 2: treat Bun timeout/concurrency as part of test config

Bun defaults:
- per-test timeout: `5000ms`
- max concurrency: `20`

These defaults are too aggressive for remote logger-heavy integration tests.

Recommended full-suite run:
```bash
bun test --timeout 30000 --max-concurrency 1 src/integration-tests/*.test.ts
```

If stabilizing first:
```bash
bun test --timeout 30000 --max-concurrency 1 src/integration-tests/headless-error-format.test.ts
```

## Rule 3: avoid compounding API load while tests run

If the viewer is open with many accordion sections, each section polls its own
`/object/select?object_view_id=<id>` endpoint on an interval. Keep the visible list small during
debugging so browser polling does not compete with test logger writes.

Before large test runs:
- close `http://localhost:8080/` tabs, or
- reduce viewer sections to a minimal set during debugging
- avoid suite-wide `resetAllLoggers()` from a focused test; reset only the logger used by that test

## Rule 4: use TypeScript trigger strings for terminal LED state

For logger messages that should end in green/red across all loggers, conform to factory TypeScript rules:
- green only if message includes exact lowercase `finished`
- red only if message includes exact uppercase `ERROR`

Avoid assuming `PASS` or lowercase `error` will flip color in the viewer path.

## Rule 5: normalizeLoggerMessage must preserve the full message

Every test file that wraps RemoteLogger calls has a local `normalizeLoggerMessage()` helper that
adds LED trigger suffixes. A common silent bug: using a bare template literal suffix without
interpolating the original message.

**Broken pattern** (logs a blank/near-blank string):
```typescript
return message.includes("finished") ? message : ` finished`;
// ERROR variant:
return `ERROR: `;
```

**Correct pattern** (appends suffix to the full message):
```typescript
return message.includes("finished") ? message : `${message} finished`;
// ERROR variant:
return `ERROR: ${message}`;
```

When broken, PASS messages are stored as `" finished"` in the API — effectively invisible in the
viewer — so the LED shows the last non-blank message (usually "Test started…") and stays yellow
even after the test passes. This is hard to notice because the test runner itself still shows
green; only the log viewer LED is wrong.

**Diagnostic**: if the log viewer shows "Test started: …" as the last state and the test runner
shows pass, the `normalizeLoggerMessage` template literals are almost certainly the cause.

## Rule 6: testWithTimeout must forward the timeout override

The `testWithTimeout` helper wraps bun's `test()` with the suite's default timeout. Tests that
create agents, run multi-phase CLI invocations, or do network I/O pass a larger timeout as a
third argument — but if `testWithTimeout` is declared with only two parameters, the third arg is
silently dropped.

**Broken declaration** (drops `{ timeout: N }`):
```typescript
const testWithTimeout = (name: string, fn: () => Promise<void> | void) =>
  test(name, fn, TEST_TIMEOUT_MS);
```

**Correct declaration** (forwards the override):
```typescript
const testWithTimeout = (name: string, fn: () => Promise<void> | void, options?: { timeout?: number }) =>
  test(name, fn, options?.timeout ?? TEST_TIMEOUT_MS);
```

Call-site form that requires the fix:
```typescript
testWithTimeout("--conversation with serialized list value…", async () => { … }, { timeout: 190000 });
```

**Symptom when broken**: multi-phase tests time out at the default 30s with:
- `exitCode: null` (process was SIGTERM'd by the test runner)
- bun reports `"Unhandled error between tests"` for any `expect()` that runs after the timeout
- the specific `expect()` line shows `Expected: 0  Received: null`

If you see `"Unhandled error between tests"` with `Received: null` on an `exitCode` assertion,
check whether the enclosing `testWithTimeout` call has a `{ timeout: N }` third arg that needs
the fix above.

## Rule 8: every fetch in RemoteLogger must have an AbortController timeout

`fetch()` has no built-in timeout. If the americansjewelry.com server accepts the TCP connection
but stalls on the response, `await logger.log()` hangs indefinitely. The test's try-catch never
fires (no exception is thrown — the promise just doesn't resolve). The test runner eventually
kills the test via its outer timeout, leaving the remote logger stuck at whatever message was
last *successfully* posted.

**Symptom**: the log viewer shows "Test started: …" (or an early log entry) and the LED stays
yellow, even though the Bun test runner shows the test passed on its *next* run.  The difference
from Rule 5: here the test runner may also show a *timeout failure* on the affected run, not a
clean pass.

**The fix** — wrap every `fetch()` in `RemoteLogger` with an `AbortController`:

```typescript
const controller = new AbortController();
const timer = setTimeout(() => controller.abort(), 8000);
let res: Response;
try {
  res = await fetch(url, { ...opts, signal: controller.signal });
} catch (err) {
  clearTimeout(timer);
  // existing error handling
}
clearTimeout(timer);
```

Apply this to every `fetch()` call: `_post()`, `destroy()`, `_tryInsertFallback()`,
and `_fetchExistingState()`.  8 seconds is a reasonable default —
slow enough to tolerate a momentary hiccup, fast enough to unblock a test that is waiting on a
dead connection.

**If adding new fetch calls to RemoteLogger**, always include the AbortController pattern.
A bare `fetch()` with no signal is a latent hang risk for every test that uses a logger.

## Rule 11: do not use selectAll in integration logger paths

`selectAll` can return a large payload and can be destabilized by unrelated oversized rows. Tests and
`RemoteLogger` should use the per-object endpoint:

```typescript
`${BASE_URL}/object/select?object_view_id=${encodeURIComponent(objectViewId)}`
```

Do not use `selectAll` for:
- `RemoteLogger` write verification
- `resetAllLoggers()` preflight health checks
- viewer polling

If manual per-object `curl` returns `200` but the test path reports `507`, search for hidden
`selectAll` calls and suite-wide reset bursts first.

## Rule 12: focused tests should reset only their own logger

For a single test, prefer:

```typescript
await resetLogger("StartupFlow_StaleConvFallback_2026");
```

Avoid calling `resetAllLoggers()` in `beforeEach` for focused startup-flow runs. A large delete burst can
push the remote PHP API into transient `503/507`, causing logger init failures even when the actual
application test passes.

## Rule 13: stale bail sentinels are a shutdown artifact, not a test assertion

`RemoteLogger` writes `/tmp/letta-integration-bail` when a logger turns red, and
`resetAllLoggers()` aborts if that file is present. That is a useful failure signal only
when it was created by the current process.

If a run aborts immediately with:
```text
[resetAllLoggers] Bail sentinel detected — aborting test file.
```
check for an old shutdown first. The integration runner now writes a pidfile at
`/tmp/letta-integration-tests.*.pid`, and `src/integration-tests/kill-running-tests.sh`
uses it to stop the tracked test process group. If the sentinel file is older than the
current test process, `resetAllLoggers()` clears it and continues.

## Rule 7: outer test timeout must cover the sum of all sequential runCli calls

Each `runCli(args, { timeoutMs: N })` call has its own per-invocation deadline, but the
*test runner* enforces a separate outer deadline via the third arg to `test()` (or
`testWithTimeout`). If the outer deadline expires first, Bun sends SIGTERM to the child
process, and the error looks like:

```
error: script "dev" was terminated by signal SIGTERM (Polite quit request)
```

**Common trap**: a multi-phase test has `{ timeout: 190000 }` (190s) and three sequential
`runCli` calls each with `timeoutMs: 180000`. If phase 1 takes 60–90s, the outer timer
fires before phase 3 even starts.

**Formula**: outer timeout ≥ (number of sequential runCli phases) × (per-phase timeoutMs) + overhead

Example fix for a 3-phase test where each phase allows 180s:
```typescript
// before — too tight, phases 2–3 can be SIGTERM'd
testWithTimeout("...", async () => { ... }, { timeout: 190000 });

// after — 3 × 180s + buffer
testWithTimeout("...", async () => { ... }, { timeout: 600000 });
```

**Diagnostic shortcut**: if the failure message contains `SIGTERM` and the test has
multiple `runCli` or async I/O calls, always check the outer timeout first before
investigating the CLI logic itself.

Note: if there is also an optional *bootstrap* phase (creates an agent when `testAgentId`
is unset), count that as an additional `runCli` invocation when sizing the outer timeout.

## Rule 9: never derive runCli cwd from process.cwd()

Integration tests are often launched from different working directories (for example
`/home/adamsl`, `src/integration-tests`, or CI workspace roots). If `runCli` uses
`process.cwd()` for spawn `cwd`, `bun run dev` can fail with:

```
error: Script not found "dev"
```

This is an infrastructure failure, not a product behavior failure, and it can mask the actual
test intent.

Use a deterministic repo root based on the test file location:

```typescript
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
```

Then spawn with `cwd: projectRoot`. Do not use `process.cwd()` for integration-test CLI spawns.

## Rule 10: log non-zero runCli exits as ERROR before expect()

When a phase fails early (especially bootstrap phases), the test can throw on
`expect(result.exitCode).toBe(0)` before writing a terminal red-state message. In that case,
localhost viewer may stay yellow at the last "started" log even though the test failed.

Before each `expect(result.exitCode).toBe(0)` in multi-phase flows:
- if `result.exitCode !== 0`, log an explicit `ERROR:` line
- include stderr tail (and stdout tail when useful)

Pattern:

```typescript
if (result.exitCode !== 0) {
  await logNonZeroExit("Phase name", result); // emits ERROR-prefixed remote log lines
}
expect(result.exitCode).toBe(0);
```

## Rule 14: keep inner CLI timeout + retry budget below outer test timeout

A test can fail silently in the viewer (stuck at "Test started...") when Bun kills it at the
outer timeout before local `catch` blocks run.

Observed case (2026-05-10):
- `HeadlessInput_UnknownControl_2026` called:
  - `runBidirectionalWithRetry(..., timeoutMs=180000, retryOnTimeouts=1)` (default values)
  - worst-case inner runtime ~360s
- test outer timeout was `{ timeout: 200000 }`
- Bun terminated test first; `catch` did not log `ERROR:`, so fail-fast signal never fired.

Required invariant:
`(inner timeout × (retries + 1)) + overhead < outer test timeout`

Example safe call:
```typescript
await runBidirectionalWithRetry(inputs, [], 90000, 0); // <= outer 200000
```

If this invariant is violated, viewer state can look stale even when assertions fail, because no
terminal red log message is emitted.

## Rule 15: memory location for stale UI state fixes

When viewer color is stale (yellow persists after row delete/reset), inspect these files first:

- `/home/adamsl/the-factory/src/components/monitor-led/monitor-led.component.ts`
- `/home/adamsl/the-factory/src/components/accordion-section/accordion-section.component.ts`

Do not start with test code until per-object API checks are done:
```bash
curl -s "http://localhost:8080/php-api/object/select?object_view_id=<LoggerId>"
curl -s "http://100.80.49.10:8284/libraries/local-php-api/object/select?object_view_id=<LoggerId>"
```

If both return `null`, row should be neutral gray. Any yellow/red at that point is viewer-state
handling, not integration-test behavior.

Apply this to optional bootstrap calls too (`--new-agent` setup paths), not just main phases.

## Failure fingerprints

1. Infrastructure pressure:
- many `update failed (HTTP 500)` from `RemoteLogger`
- hook/test timeout near 5s
- intermittent pass/fail across reruns
- reset output shows many `DELETE ... HTTP 507` lines before the test starts

2. Registry mismatch:
- logger appears in test code but not cleaned/reset
- stale LED text/colors survive across runs

3. Log viewer stuck at "Test started" (test actually passes on rerun):
- `normalizeLoggerMessage` template literal bug (Rule 5) — check first
- OR `RemoteLogger` fetch call hung (no AbortController timeout, Rule 8) — test timed out
  mid-log; previous run's "Test started" was committed but the next `log()` call never resolved
- To distinguish: if the Bun test runner also showed a timeout on the stuck run, it's Rule 8;
  if the runner showed a clean pass, it's Rule 5

4. "Unhandled error between tests" / `exitCode: null`:
- `testWithTimeout` missing `options` parameter (Rule 6)
- fix the declaration; long-running tests were silently capped at 30s

5. `SIGTERM (Polite quit request)` on a child process mid-test:
- outer `{ timeout: N }` is smaller than the sum of sequential `runCli` timeouts (Rule 7)
- increase outer timeout to ≥ phases × per-phase timeoutMs + buffer

6. `error: Script not found "dev"` in runCli stderr:
- spawn `cwd` is not repo root (Rule 9)
- replace `process.cwd()` with path-from-`import.meta.url` resolution

7. Manual per-object `curl` works but test logger gets `507`:
- hidden `selectAll` in `RemoteLogger` or helper diagnostics (Rule 11)
- `resetAllLoggers()` burst before focused test (Rule 12)
- oversized remote row, commonly array-style loggers such as `UserManager_2026`

## Update checklist

1. Add/remove IDs in `ALL_LOGGER_IDS` when tests change logger names.
2. Add/remove matching accordion sections in `/home/adamsl/the-factory/public/index.html` for any logger you need in viewer UI.
3. Keep reset helper docs in sync with actual implementation.
4. Validate with one serialized run:
```bash
bun test --timeout 30000 --max-concurrency 1 src/integration-tests/*.test.ts
```
5. If logger is missing in UI, verify API-vs-HTML registration mismatch:
```bash
curl -s "http://localhost:8080/php-api/object/select?object_view_id=LoggerId_2026"
curl -s http://localhost:8080/ | rg "LoggerId_2026"
```
6. If unstable, verify upstream health directly:
```bash
curl -i --max-time 10 \
  "https://americansjewelry.com/libraries/local-php-api/index.php/object/select?object_view_id=LoggerId_2026"
```
