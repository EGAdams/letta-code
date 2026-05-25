# Scissari Planning Mode Hang Detection Tests

These integration tests detect when Scissari gets stuck in Planning mode without producing output, a known issue where the CLI hangs indefinitely showing "Thinking…" with no progress.

## Test Files

- `scissari-planning-mode-hang.integration.test.ts` — Two tests that catch output starvation and verify timeout recovery
- `scissari-tool-execution-hang.integration.test.ts` — Covers post-approval continuation for both successful and failing tool commands (including `python: command not found`) and asserts no indefinite hang

## What the Tests Do

### Test 1: "detects output starvation during planning mode"
- Sends a complex prompt designed to trigger planning mode: _"Create a comprehensive implementation plan for a multi-agent system..."_
- Monitors for **output starvation** — no new bytes for 15 seconds
- Fails immediately if starvation is detected (rather than waiting 60s)
- Logs detailed diagnostic info: run_id, last stdout/stderr, timing

**Why this matters:** If Scissari's process is running but producing no output, the CLI will appear frozen. This test catches that hang pattern early.

### Test 2: "recovers from partial thinking without full hang"
- Sends a moderately complex prompt: _"Analyze the trade-offs between microservices and monolithic architecture..."_
- Verifies the process completes without starvation
- Confirms a valid success result is returned
- Logs completion stats (run count, output size)

**Why this matters:** Ensures Scissari can handle moderate complexity without getting stuck, even during thinking phases.

## Running the Tests

### Prerequisites
```bash
export LETTA_RUN_SCISSARI_TEST=1
export LETTA_BASE_URL=http://100.80.49.10:8283  # or your local Letta server
export LETTA_API_KEY=6c9f1e4b5a2d8f7c0b3e9a4d7f2c1e8
```

### Run just the hang detection tests
```bash
cd /home/adamsl/letta-code
bun test --test-name-pattern "planning mode hang detection" src/integration-tests/scissari-planning-mode-hang.integration.test.ts
```

### Run a specific test
```bash
bun test --test-name-pattern "detects output starvation" src/integration-tests/scissari-planning-mode-hang.integration.test.ts
```

### Run all Scissari tests together
```bash
bun test --test-name-pattern "scissari" src/integration-tests/*.integration.test.ts
```

## Log Viewer

Monitor test progress at: `http://localhost:8080`

Two accordion sections track these tests:
- **ScissariPlanningModeHang_2026** — Output starvation test
- **ScissariInactivityTimeout_2026** — Recovery/inactivity test

Green LED = test passed
Red LED = starvation detected or test failed
Yellow LED = test running

## Timeout Configuration

| Setting | Value | Purpose |
|---------|-------|---------|
| `STARVATION_TIMEOUT_MS` | 15000 (15s) | How long to wait for output before declaring hang |
| `MAX_TOTAL_TIME_MS` | 60000 (60s) | Absolute max time to wait for process |
| Test timeout | 90000 (90s) | Bun timeout for the entire test |

These timeouts are conservative — a hanging process is killed as soon as 15s of silence is detected, not at the full 60s limit.

## Debugging Hung Scissari Sessions

If a test fails with starvation:

1. **Check the log viewer** at `http://localhost:8080/ScissariPlanningModeHang_2026` for the exact hang point
2. **Reproduce in interactive mode:**
   ```bash
   letta --agent agent-5955b0c2-7922-4ffe-9e43-b116053b80fa --new
   ```
   Then paste the test prompt
3. **Check stream.ts** at `src/cli/helpers/stream.ts` — this is where the CLI should be handling thinking mode timeouts (90s inactivity timeout was added 2026-05-09)
4. **Inspect Letta server logs** on the backend for any signs of stuck model requests or tool calls
5. **Check Scissari's model selection** — memory shows she uses `gpt-5.3-codex`, which may have different behavior under planning scenarios

## Known Root Causes

From project memory (`project_stream_inactivity_hang.md`):
- **Model sends pings only, no content** — happens with gpt-5.3-codex after Planning() approval
- **MCP streaming bug in Letta 0.16.3** — affects reasoning-only scenarios
- **Stale letta.js after source edits** — run `bun run build` to pick up CLI changes like the 90s inactivity timer

## Related Issues

- LET-7101 (approval conflict recovery)
- Scissari stream inactivity hang fix (2026-05-09) — added 90s timeout to drainStream in stream.ts
