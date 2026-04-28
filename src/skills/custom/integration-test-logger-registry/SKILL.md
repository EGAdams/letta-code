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

If the viewer is open with many accordion sections, each section polls `selectAll` every ~2.5s.
That background load can interfere with reset and update calls.

Before large test runs:
- close `http://localhost:8080/` tabs, or
- reduce viewer sections to a minimal set during debugging

## Rule 4: use TypeScript trigger strings for terminal LED state

For logger messages that should end in green/red across all loggers, conform to factory TypeScript rules:
- green only if message includes exact lowercase `finished`
- red only if message includes exact uppercase `ERROR`

Avoid assuming `PASS` or lowercase `error` will flip color in the viewer path.

## Failure fingerprints

1. Infrastructure pressure:
- many `update failed (HTTP 500)` from `RemoteLogger`
- hook/test timeout near 5s
- intermittent pass/fail across reruns

2. Registry mismatch:
- logger appears in test code but not cleaned/reset
- stale LED text/colors survive across runs

## Update checklist

1. Add/remove IDs in `ALL_LOGGER_IDS` when tests change logger names.
2. Keep reset helper docs in sync with actual implementation.
3. Validate with one serialized run:
```bash
bun test --timeout 30000 --max-concurrency 1 src/integration-tests/*.test.ts
```
4. If unstable, verify upstream health directly:
```bash
curl -i --max-time 10 \
  "https://americansjewelry.com/libraries/local-php-api/index.php/object/selectAll"
```
