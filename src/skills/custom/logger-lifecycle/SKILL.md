---
name: logger-lifecycle
description: >
  Complete workflow for adding a new logger accordion to localhost:8080, initializing and
  writing to it from code, then checking whether its LED is Yellow (running), Green (pass),
  or Red (fail). Covers the three mandatory registration files, the RemoteLogger TypeScript
  API, and both browser (Playwright) and curl verification methods. Use this skill any time
  the user asks: "add a new logger", "check a logger status", "why is my logger yellow/red",
  or "how do I see if a logger is working".
---

# Logger Lifecycle Skill

End-to-end: add → fire → check.

---

## Step 1 — Register the logger (3 mandatory files)

Every new logger ID must be added to **all three** of these, or something breaks:

| File | What to add | Symptom if missing |
|---|---|---|
| `src/integration-tests/logger-helpers.ts` | ID in `ALL_LOGGER_IDS` | Stale state leaks between runs; `resetAllLoggers()` skips it |
| `/home/adamsl/the-factory/public/index.html` | `<accordion-section>` element | Data exists in API but never appears in the viewer |
| Your source file | `new RemoteLogger("MyLogger_2026")` | Nothing is written |

### 1a — logger-helpers.ts

Open `src/integration-tests/logger-helpers.ts` and add your ID to `ALL_LOGGER_IDS`:

```typescript
export const ALL_LOGGER_IDS = [
  // ... existing IDs ...
  "MyFeature_2026",   // ← add here
];
```

### 1b — index.html

Open `/home/adamsl/the-factory/public/index.html` and append before `</body>`:

```html
<accordion-section
    id="accordion-section-myfeature"
    monitored_object_id="MyFeature_2026"
    data_source_location="http://100.80.49.10:8284/libraries/local-php-api/">
</accordion-section>
```

The `monitored_object_id` must exactly match the string passed to `new RemoteLogger(...)`.
The `id` attribute is arbitrary but must be unique within the file.

### 1c — ID naming convention

`PascalCaseFeatureName_<year>` — unique, human-readable, year-suffixed:
```
ScissariToolCalls_2026
ReceiptScanPipeline_2026
```

---

## Step 2 — Fire the logger up

```typescript
import { RemoteLogger } from "../logger/RemoteLogger";

const logger = new RemoteLogger("MyFeature_2026");

// Init: SELECT existing row, or INSERT a fresh one.
// Always call before any log() — never skip.
await logger.init();

// Optional: wipe the terminal text from a previous run without deleting the row.
await logger.clearLogs("MyFeature starting…");

// Write entries. Each call POSTs an update to the API.
await logger.log("step 1: initializing");
await logger.log("step 2: running query");

// Terminal states — these flip the LED color:
await logger.log("step 3 finished.");          // ← "finished" → LED turns green
// OR
await logger.log("ERROR: query returned null"); // ← "ERROR" (uppercase) → LED turns red
```

### LED color rules

| Message contains | LED color | hex |
|---|---|---|
| lowercase `finished` | green | `lightgreen` |
| uppercase `ERROR` | red | `#fb6666` |
| anything else | yellow | `lightyellow` |

These strings are checked by `updatedLed()` in `RemoteLogger.ts` and by the viewer component.
They must match exactly — `error`, `FINISH`, `Finished` will not flip the color.

### Graceful-degradation pattern (recommended for tests)

Wrap logger calls so a broken API never fails the test:

```typescript
let loggerReady = false;
try {
  await logger.init();
  await logger.clearLogs("Test started.");
  loggerReady = true;
} catch (err) {
  console.warn(`[logger] init failed: ${err}`);
}

const log = async (msg: string) => {
  console.log(`[test] ${msg}`);
  if (!loggerReady) return;
  try { await logger.log(msg); } catch {}
};
```

---

## Step 3 — Check the logger status

Two methods: **browser** (see the full viewer UI) or **curl** (fast programmatic check).

---

### Method A — Browser via Playwright (visual)

Use the Playwright MCP tools to open the viewer and take a screenshot.

```
mcp__playwright__browser_navigate  { "url": "http://localhost:8080/" }
mcp__playwright__browser_take_screenshot {}
```

The accordion for `MyFeature_2026` will show its LED color:
- **Yellow** = still running (or never reached a terminal state)
- **Green** = received a message containing `finished`
- **Red** = received a message containing `ERROR`

To scroll to and inspect a specific section:

```
mcp__playwright__browser_snapshot {}
```

This returns the DOM accessibility tree. Search the output for `MyFeature_2026` to find the
accordion row and read its LED text.

To check a logger that may not be visible without scrolling:

```
mcp__playwright__browser_evaluate {
  "expression": "document.querySelector('[monitored_object_id=\"MyFeature_2026\"]')?.shadowRoot?.querySelector('.monitor-led')?.textContent"
}
```

---

### Method B — curl (fast, scriptable)

#### Check LED state

```bash
curl -s \
  "http://100.80.49.10:8284/libraries/local-php-api/object/select?object_view_id=MyFeature_2026" \
  | python3 -c "
import sys, json
raw = sys.stdin.read().strip()
if not raw or raw == 'null':
    print('NOT FOUND — logger has not been initialized yet')
    exit()
d = json.loads(raw)
od = json.loads(d['object_data']) if isinstance(d.get('object_data'), str) else d.get('object_data', {})
led = od.get('monitorLed', {})
color = led.get('classObject', {}).get('background_color', '?')
text  = led.get('ledText', '?')
logs  = od.get('logObjects', [])
status = 'PASS' if color == 'lightgreen' else 'FAIL' if color == '#fb6666' else 'YELLOW'
print(f'Status : {status}')
print(f'LED    : {text}')
print(f'Color  : {color}')
print(f'Entries: {len(logs)}')
if logs:
    print(f'Last   : {logs[-1][\"message\"]}')
"
```

#### Quick smoke test (is the logger reachable at all?)

```bash
# Returns the raw JSON (or 'null' if the record doesn't exist yet)
curl -s --max-time 8 \
  "http://100.80.49.10:8284/libraries/local-php-api/object/select?object_view_id=MyFeature_2026"
```

Expected shapes:
- `null` → record not yet inserted (call `logger.init()`)
- `{"object_view_id":"MyFeature_2026","object_data":"{...}"}` → record exists

#### Check multiple loggers at once

```bash
for id in Scissari_Session_2026 Scissari_Thoughts_2026 Scissari_Tool_Bash_2026; do
  color=$(curl -s --max-time 5 \
    "http://100.80.49.10:8284/libraries/local-php-api/object/select?object_view_id=${id}" \
    | python3 -c "
import sys,json
d=json.loads(sys.stdin.read() or 'null')
if not d: print('NOT FOUND'); exit()
od=json.loads(d['object_data']) if isinstance(d.get('object_data'),str) else {}
c=od.get('monitorLed',{}).get('classObject',{}).get('background_color','?')
print('PASS' if c=='lightgreen' else 'FAIL' if c=='#fb6666' else 'YELLOW')
" 2>/dev/null)
  printf "%-45s %s\n" "$id" "$color"
done
```

---

## Troubleshooting

### Logger is NOT FOUND (curl returns null)

`logger.init()` has not been called, or it threw and was swallowed.
Call `logger.init()` explicitly; check for a thrown error.

### Logger stays Yellow after the code ran

One of:
1. **Terminal message never sent** — `finished` or `ERROR` wasn't logged; check the last entry.
2. **Message casing wrong** — `Finished` or `error` won't flip the color; must be exact.
3. **`clearLogs` called after the terminal message** — that resets LED to yellow.
4. **Code threw before reaching the terminal log** — add logging inside your catch block.

### Logger not visible in viewer (data in API, no accordion)

`index.html` is missing the `<accordion-section>` entry. Add it (see Step 1b) and reload
`localhost:8080`.

### API returns HTTP 500 / 507

- **507 Insufficient Storage** — remote server disk full; inserts silently fail.
- **500** — may still have persisted (the API is unreliable on 5xx). Check via `select` after.
- Use `LETTA_LOGGER_OPTIONAL=1` to soft-fail 503/507 errors without throwing.

### Logger appears in viewer but shows stale data from a previous run

`resetAllLoggers()` (or `resetLogger("MyFeature_2026")`) was not called before the new run.
Add it to `beforeEach` or call it manually:

```typescript
import { resetLogger } from "./logger-helpers";
await resetLogger("MyFeature_2026");
```

---

## Quick reference — full cycle in one block

```typescript
// 1. Import
import { RemoteLogger } from "../logger/RemoteLogger";

// 2. Create and initialize
const logger = new RemoteLogger("MyFeature_2026");
await logger.init();
await logger.clearLogs("MyFeature started.");

// 3. Log progress
await logger.log("doing work…");

// 4. Terminal state
await logger.log("all checks passed finished.");  // → green LED

// 5. Check (bash)
// curl -s "http://100.80.49.10:8284/libraries/local-php-api/object/select?object_view_id=MyFeature_2026"

// 5. Check (Playwright)
// mcp__playwright__browser_navigate { "url": "http://localhost:8080/" }
// mcp__playwright__browser_take_screenshot {}
```
