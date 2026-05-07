---
name: scissari-logging-health
description: >
  Verify that the Scissari Letta agent (agent-5955b0c2-7922-4ffe-9e43-b116053b80fa) is logging
  successfully to the viewer at localhost:8080. Runs the Scissari integration tests from
  src/integration-tests/, polls the localhost:8080 viewer and the upstream logger API for LED
  status, then reads raw log entries and debugs any failures. Use this skill any time the user
  asks about Scissari logging health, whether the viewer is showing correct LED state, or when
  integration tests need to be run to verify Scissari is working end-to-end.
---

# Scissari Logging Health Skill

## What this skill does

1. **Preflight** — verify that localhost:8080 (the viewer) and the upstream logger API are reachable.
2. **Run tests** — execute the Scissari integration tests with the required environment flags.
3. **Read results** — fetch each Scissari logger's state from the API and check LED color.
4. **Debug failures** — apply the standard failure-fingerprint playbook and surface actionable fixes.

---

## Key constants

| Constant | Value |
|---|---|
| Scissari agent ID | `agent-5955b0c2-7922-4ffe-9e43-b116053b80fa` |
| Project root | `/home/adamsl/letta-code` |
| Letta server (WSL→Docker) | `http://100.80.49.10:8283` |
| Letta API key | `6c9f1e4b5a2d8f7c0b3e9a4d7f2c1e8` |
| Viewer URL | `http://localhost:8080/` |
| Local proxy API | `http://localhost:8080/php-api` |
| Upstream API | `https://americansjewelry.com/libraries/local-php-api/index.php` |
| Reset API (from WSL) | `http://100.80.49.10:8284/libraries/local-php-api` |
| Scissari logger IDs | `ScissariTestLogger_2026`, `ScissariMessagePersistence_2026` |

---

## Step 1 — Preflight health checks

Run these three checks before touching any test. If any fail, address the infrastructure first.

```bash
# 1a. Viewer shell (localhost:8080 must respond fast)
curl -i --max-time 5 http://localhost:8080/

# 1b. Local proxy API — per-object select for one known Scissari logger
curl -i --max-time 8 \
  "http://localhost:8080/php-api/object/select?object_view_id=ScissariTestLogger_2026"

# 1c. Upstream API direct check
curl -i --max-time 12 \
  "https://americansjewelry.com/libraries/local-php-api/index.php/object/select?object_view_id=ScissariTestLogger_2026"
```

**Interpret results:**

| 1a | 1b | 1c | Diagnosis |
|---|---|---|---|
| PASS | PASS | PASS | Infrastructure healthy — proceed to Step 2 |
| PASS | FAIL | PASS | Local proxy misconfigured — check `the-factory/webpack.config.js` proxy settings |
| PASS | TIMEOUT | PASS | Proxy timeout — add `proxy./php-api.timeout` in webpack config |
| PASS | any | TIMEOUT | Upstream API slow/down — tests will still run but loggers may not write cleanly; set `LETTA_LOGGER_RESET_DISABLED=1` |
| FAIL | — | — | Viewer not running — start it: `cd /home/adamsl/the-factory && npm start` (or `webpack-dev-server`) |

---

## Step 2 — Run Scissari integration tests

Use a serialized, long-timeout run so logger I/O doesn't compete with test execution:

```bash
cd /home/adamsl/letta-code

LETTA_RUN_SCISSARI_TEST=1 \
LETTA_BASE_URL=http://100.80.49.10:8283 \
LETTA_API_KEY=6c9f1e4b5a2d8f7c0b3e9a4d7f2c1e8 \
bun test \
  --timeout 200000 \
  --max-concurrency 1 \
  src/integration-tests/scissari-agent.integration.test.ts \
  src/integration-tests/scissari-message-persistence.integration.test.ts
```

To also run the Telegram bridge test you need two extra env vars:
```bash
SCISSARI_TELEGRAM_BOT_TOKEN=<token>   # or set TELEGRAM_TOKEN
SCISSARI_TELEGRAM_CHAT_ID=<chat_id>
```

Add `src/integration-tests/scissari-telegram-connection.integration.test.ts` to the file list.

**If the upstream logger API is flaky**, suppress resets so infrastructure noise doesn't fail tests:
```bash
LETTA_LOGGER_RESET_DISABLED=1 \
LETTA_RUN_SCISSARI_TEST=1 \
...
bun test ...
```

---

## Step 3 — Read logger state from localhost:8080

After the tests finish (or at any point during debugging), fetch the current LED + log entries:

```bash
# ScissariTestLogger_2026
curl -s \
  "http://localhost:8080/php-api/object/select?object_view_id=ScissariTestLogger_2026" \
  | python3 -m json.tool

# ScissariMessagePersistence_2026
curl -s \
  "http://localhost:8080/php-api/object/select?object_view_id=ScissariMessagePersistence_2026" \
  | python3 -m json.tool
```

Or hit the upstream directly if the proxy is unreachable:
```bash
curl -s \
  "https://americansjewelry.com/libraries/local-php-api/index.php/object/select?object_view_id=ScissariTestLogger_2026" \
  | python3 -m json.tool
```

**Interpret the `monitorLed.classObject.background_color` field:**

| Color | Meaning |
|---|---|
| `lightgreen` | Test passed and logged `finished` — LED is green |
| `#fb6666` (red) | Logger received an `ERROR`-prefixed message — test failed |
| `lightyellow` | Test is still running OR logger never reached a terminal state |

The `logObjects` array shows the full timestamped message history. Read them in order — the last entry is the most recent state.

---

## Step 4 — Debug failures

Work through the fingerprints below in order. The most common issues are listed first.

### Fingerprint 1: LED stuck yellow at "Test started" — test runner shows PASS

**Cause A (most common):** `normalizeLoggerMessage` template literal bug — the message suffix is
appended without the original message body, so `finished` is logged as `" finished"` (blank-ish)
and the API keeps the previous entry as current.

Check in both Scissari test files:
```typescript
// BROKEN — logs a blank string as the final message:
return message.includes("finished") ? message : ` finished`;
// BROKEN ERROR variant:
return `ERROR: `;

// CORRECT — always interpolates the original message:
return message.includes("finished") ? message : `${message} finished`;
// CORRECT ERROR variant:
return `ERROR: ${message}`;
```

File locations:
- `src/integration-tests/scissari-agent.integration.test.ts` — `normalizeLoggerMessage()`
- `src/integration-tests/scissari-message-persistence.integration.test.ts` — `log()` wrapper

**Cause B:** `RemoteLogger` `fetch()` hung mid-test (no `AbortController`). The test runner
eventually timed out, but the last successfully-committed log message was an early entry.
Check `src/logger/RemoteLogger.ts` — every `fetch()` must have an `AbortController` with an
8-second timeout. Look for bare `await fetch(url, {...})` without a `signal`.

To distinguish A from B: if the Bun runner also showed a _timeout failure_ on the stuck run → B.
If the runner showed _clean pass_ → A.

---

### Fingerprint 2: Test times out with `exitCode: null` / SIGTERM

**Cause:** Outer test timeout (`{ timeout: N }`) is smaller than the sum of sequential `runCli`
phases. The Bun runner kills the child process.

Check the test's outer timeout:
- `scissari-agent.integration.test.ts` uses `{ timeout: 190000 }` — one `runCli` phase with
  `timeoutMs: 300000` (300s). The outer 190s fires first if the agent is slow.
  → Increase outer timeout: `{ timeout: 350000 }` to give the child room.
- `scissari-message-persistence.integration.test.ts` has `{ timeout: 150000 }` for each test.
  Each `runScissariPrompt()` has a 120s inner timeout — fine for one phase.

Formula: **outer timeout ≥ (number of runCli phases) × (per-phase timeout) + 30s buffer**

SIGTERM symptom:
```
error: script "dev" was terminated by signal SIGTERM (Polite quit request)
```

---

### Fingerprint 3: `Script not found "dev"` in runCli stderr

**Cause:** The `cwd` used when spawning `bun run dev` is not the project root.

Both Scissari test files should derive `projectRoot` like this:
```typescript
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
```
Then pass `cwd: projectRoot` to `spawn(...)`. If `process.cwd()` is used instead, fix it.

---

### Fingerprint 4: Exit code check passes but `SCISSARI_TEST_OK` token missing

**Cause:** The Scissari agent responded but didn't include the exact token. This is a model/agent
behavior issue, not an infrastructure issue.

Diagnostic steps:
1. Check Scissari agent health directly:
   ```bash
   cd /home/adamsl/letta-code
   LETTA_BASE_URL=http://100.80.49.10:8283 LETTA_API_KEY=6c9f1e4b5a2d8f7c0b3e9a4d7f2c1e8 \
   bun run dev \
     --agent agent-5955b0c2-7922-4ffe-9e43-b116053b80fa \
     --conversation default \
     -p "Reply with exactly: SCISSARI_TEST_OK" \
     --output-format json
   ```
2. If the agent is not responding or hangs after `Skill(messaging-agents)`, this is the known
   TUI/tool-continuation hang (see `handoff.md`). Address tool attachment first:
   ```bash
   python3 src/skills/custom/scissari-hailey-pairing/scripts/ensure_pair_tools.py --dry-run
   python3 src/skills/custom/scissari-hailey-pairing/scripts/ensure_pair_tools.py
   ```
3. Verify the Letta server is running and Scissari's agent ID is valid:
   ```bash
   LETTA_BASE_URL=http://100.80.49.10:8283 LETTA_API_KEY=6c9f1e4b5a2d8f7c0b3e9a4d7f2c1e8 \
   bun -e '
   import { settingsManager } from "./src/settings-manager.ts";
   import { getClient } from "./src/agent/client.ts";
   await settingsManager.initialize();
   const client = await getClient();
   const agent = await client.agents.retrieve("agent-5955b0c2-7922-4ffe-9e43-b116053b80fa");
   console.log(JSON.stringify({ id: agent.id, name: agent.name, status: agent.agent_state }, null, 2));
   '
   ```

---

### Fingerprint 5: Message persistence test fails — streamed result OK but no persisted assistant message

This is the known bug documented in `handoff.md`. The streamed CLI output contains the nonce token
but `runs.messages.list(run_id)` shows no `assistant_message` with that token.

Diagnostic — inspect the run's persisted messages and steps:
```bash
cd /home/adamsl/letta-code
LETTA_BASE_URL=http://100.80.49.10:8283 LETTA_API_KEY=6c9f1e4b5a2d8f7c0b3e9a4d7f2c1e8 \
bun -e '
import { settingsManager } from "./src/settings-manager.ts";
import { getClient } from "./src/agent/client.ts";
await settingsManager.initialize();
const client = await getClient();
const runs = (await client.runs.list({
  agent_id: "agent-5955b0c2-7922-4ffe-9e43-b116053b80fa",
  order: "desc",
  limit: 5,
})).getPaginatedItems();
const runId = runs[0]?.id;
if (!runId) { console.log("No runs found"); process.exit(1); }
console.log("Latest run:", runId, "status:", runs[0].status, "stop_reason:", runs[0].stop_reason);
const msgs = (await client.runs.messages.list(runId, { limit: 30 })).getPaginatedItems();
const steps = (await client.runs.steps.list(runId, { limit: 10 })).getPaginatedItems();
console.log("Messages:", msgs.map(m => ({ type: m.message_type, id: m.id })));
console.log("Steps:", steps.map(s => ({ id: s.id, status: s.status, completion_tokens: s.completion_tokens, messages: s.messages?.length })));
'
```

If `messages: []` appears on completed steps — that is the streamed-output-vs-persistence drift
described in `handoff.md`. This is a Letta server-side issue. Escalate or wait for a server fix;
the test is correctly failing to document this state.

---

### Fingerprint 6: Logger reset failures (`HTTP 507` / `HTTP 503`)

**Cause:** The upstream PHP API is under storage pressure or briefly overloaded during the reset
burst before tests.

Quick fix — disable resets for a single focused run:
```bash
LETTA_LOGGER_RESET_DISABLED=1 LETTA_RUN_SCISSARI_TEST=1 ... bun test ...
```

Or reduce concurrency:
```bash
LETTA_LOGGER_RESET_CONCURRENCY=1 LETTA_LOGGER_RESET_TIMEOUT_MS=20000 ...
```

For a focused single-test run, reset only the relevant logger rather than all loggers:
```bash
# Delete just the Scissari logger before running
curl -s -X POST \
  "https://americansjewelry.com/libraries/local-php-api/index.php/object/delete" \
  -H "Content-Type: application/json" \
  -d '{"object_view_id":"ScissariTestLogger_2026"}'
```

---

## Step 5 — Viewer registration check

If a test writes logs successfully but the logger doesn't appear in `http://localhost:8080/`:

```bash
# Check if data exists in the API
curl -s "http://localhost:8080/php-api/object/select?object_view_id=ScissariTestLogger_2026" | python3 -c "import sys,json; d=json.load(sys.stdin); print('data found' if d else 'no data')"

# Check if the logger is registered in the viewer HTML
grep -n "ScissariTestLogger_2026" /home/adamsl/the-factory/public/index.html
grep -n "ScissariMessagePersistence_2026" /home/adamsl/the-factory/public/index.html
```

If data exists in the API but there's no matching line in `index.html`, add an accordion section:
```html
<accordion-section class="" id="accordion-section-scissaritestlogger"
    monitored_object_id="ScissariTestLogger_2026"
    data_source_location="https://americansjewelry.com/libraries/local-php-api/index.php/">
</accordion-section>
```

Both `ScissariTestLogger_2026` and `ScissariMessagePersistence_2026` must be registered for their
LEDs to appear in the viewer.

---

## Quick one-liner: full Scissari health sweep

Run this to get a complete picture in one shot:

```bash
cd /home/adamsl/letta-code

echo "=== Viewer health ===" && \
curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://localhost:8080/ && echo "" && \

echo "=== Proxy API (ScissariTestLogger) ===" && \
curl -s --max-time 8 \
  "http://localhost:8080/php-api/object/select?object_view_id=ScissariTestLogger_2026" \
  | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    if d:
        led = d.get('object_data', {}).get('monitorLed', {})
        logs = d.get('object_data', {}).get('logObjects', [])
        print(f'LED: {led.get(\"ledText\",\"?\")} | color: {led.get(\"classObject\",{}).get(\"background_color\",\"?\")}')
        print(f'Last log: {logs[-1][\"message\"] if logs else \"(none)\"}')
    else:
        print('No data found')
except Exception as e:
    print(f'Parse error: {e}')
" && \

echo "=== Running Scissari agent test ===" && \
LETTA_RUN_SCISSARI_TEST=1 \
LETTA_BASE_URL=http://100.80.49.10:8283 \
LETTA_API_KEY=6c9f1e4b5a2d8f7c0b3e9a4d7f2c1e8 \
bun test \
  --timeout 200000 \
  --max-concurrency 1 \
  src/integration-tests/scissari-agent.integration.test.ts && \

echo "=== Post-test logger state ===" && \
curl -s \
  "http://localhost:8080/php-api/object/select?object_view_id=ScissariTestLogger_2026" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
if d:
    led = d.get('object_data', {}).get('monitorLed', {})
    logs = d.get('object_data', {}).get('logObjects', [])
    color = led.get('classObject', {}).get('background_color', '?')
    text = led.get('ledText', '?')
    print(f'LED: {text} | color: {color}')
    for entry in logs[-5:]:
        print(f'  [{entry.get(\"timestamp\",\"?\")}] {entry.get(\"message\",\"?\")}')
else:
    print('Logger not found in API')
"
```

---

## Reference: LED color rules (TypeScript-conformant)

The viewer and `RemoteLogger` both follow this contract — messages written by tests **must** use
these exact strings for the LED to flip correctly:

| To turn LED... | Message must contain |
|---|---|
| Green | exact lowercase `finished` (e.g. `"All assertions passed. Test complete."` + ` finished` suffix) |
| Red | exact uppercase `ERROR` (e.g. `"ERROR: exit code 1"`) |
| Yellow (running) | anything else |

`normalizeLoggerMessage()` in each test file is responsible for adding these suffixes. If the LED
color is wrong after a test, always check that function first.
