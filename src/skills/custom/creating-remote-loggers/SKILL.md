---
name: creating-remote-loggers
description: Creates persistent remote loggers that write structured log entries to a PHP-backed API at americansjewelry.com. The object_data shape matches MonitoredObject so the web viewer renders the LED status and log correctly. Use when the user wants to log operations, test steps, or workflow events to a persistent remote store for later inspection. Handles insert/update/select/delete against the monitored_objects API.
---

# Creating Remote Loggers

Loggers persist named `object_view_id` records to the PHP API. Each record holds a `logObjects`
array (timestamped messages) and a `monitorLed` block that drives the web viewer's status LED.
All API errors propagate as thrown exceptions — logger failures should exit the calling code
immediately.

System layout to keep straight:
- `http://localhost:8080/` is only the local HTML viewer.
- That viewer is served from `/home/adamsl/the-factory/public/index.html`.
- The PHP API stays at `https://americansjewelry.com/libraries/local-php-api/index.php`.
- Logger writes must match the viewer's `monitored_object_id` exactly, or the record will exist
  in the API but never appear in the accordion.

## Quick start

Copy `scripts/RemoteLogger.ts` into the project (e.g., `src/logger/RemoteLogger.ts`), then:

```typescript
import { RemoteLogger } from "../logger/RemoteLogger";

const logger = new RemoteLogger("MyFeature_2026");
await logger.init();             // SELECT existing record, or INSERT fresh one
await logger.clearLogs();        // optional: keep object, clear terminal text/logObjects
await logger.log("step 1");     // appends entry, updates monitorLed, POSTs update
await logger.log("finished.");  // "finished" in message → LED turns green
await logger.log("ERROR: ...");  // "ERROR" in message → LED turns red
```

## Naming convention

`FeatureName_<year or timestamp>` — human-readable, unique enough for a run:
```
ScissariTest_2026
ReceiptScan_1716200000
```

## LED color logic (TypeScript-conformant)

`monitorLed.classObject.background_color` is set automatically based on message content:

| Message contains | LED color |
|-----------------|-----------|
| exact uppercase `"ERROR"` | `#fb6666` (red), white text |
| exact lowercase `"finished"` | `lightgreen`, black text |
| anything else | `lightyellow` (running), black text |

This must match `MonitoredObject.logUpdate()` in the TypeScript viewer source.

## Critical: always include monitorLed in object_data

Omitting `monitorLed` crashes the web viewer with:
```
TypeError: Cannot read properties of undefined (reading 'ledText')
```
`monitor-led.component.ts` line 75 assigns `data.monitorLed` directly to `monitor_led_data` before
calling `render()`. If the field is missing, `monitor_led_data` becomes `undefined` and `render()`
crashes. A defensive guard (`if (data.monitorLed)`) has been applied to the component, but the
field should always be present in any record written by a logger.

## Critical: monitorLed must always have classObject

Even when `monitorLed` is present, a missing `classObject` crashes the web viewer with:
```
TypeError: Cannot read properties of undefined (reading 'classObject')
    at accordion-section.component.ts:50
```
`accordion-section.component.ts` reads `event.detail.monitorLed.classObject.background_color` and
`.color` directly. If `classObject` is absent (e.g. a record written by an older logger version),
it throws.

**How this happens:** `init()` loads an existing record where `monitorLed` exists but has no
`classObject`. The `??` fallback does not fire because `monitorLed` is truthy. The corrupted shape
is kept in memory, and each `log()` call spreads `{ ...undefined }` into `classObject`, producing
an empty `{}` that still lacks `background_color`/`color`.

**The fix (already in `scripts/RemoteLogger.ts`):**

In `init()`, after loading state, check `rawLed.classObject` and repair + re-POST immediately:
```typescript
const rawLed = state.monitorLed ?? defaultLed();
this.monitorLed = rawLed.classObject
  ? rawLed
  : { ...rawLed, classObject: defaultLed().classObject };
if (!state.monitorLed?.classObject) {
  await this._post("update");  // push repair to server so browser sees it on next poll
}
```

In `updatedLed()`, spread `defaultLed().classObject` as the base so all keys survive:
```typescript
classObject: { ...defaultLed().classObject, ...(current.classObject ?? {}) },
```

## Critical: timestamp is milliseconds

`ILogObject.timestamp` is **milliseconds** since epoch. Use `Date.now()`, not `Date.now() / 1000`.

## insert vs update strategy

Do **not** use an upsert (update-then-insert) pattern. The API always returns `affected_rows: null`
regardless of whether the update matched any rows — you cannot use it to detect misses.

Correct strategy used in `RemoteLogger`:
- `init()` → SELECT; if not found, INSERT
- `log()` → always UPDATE (record is guaranteed after init)

## Clearing terminal text without deleting logger

Use `clearLogs()` when you want to keep the same logger object but reset the accordion terminal.

```typescript
await logger.init();
await logger.clearLogs("MyFeature ready.");
```

This clears `logObjects`, resets LED state/text, and updates the same `object_view_id` row.
It does **not** delete the record.

## API response quirks

The live API does not match its documentation. See [references/api.md](references/api.md) for the
full breakdown, but the key points:
- `insert` returns `"\""` (not `"insert success."`) — insert still works, verified by select
- `update`/`delete` return `{"affected_rows":null,...,"error":null}` — operations still work
- `error: null` is **not** an error — only throw when `body.error` is truthy
- `select` returns `null` for non-existent records (not a 404)

## Browser usage: POST requests must use `mode: 'no-cors'`

When `RemoteLogger` runs **in a browser** (e.g. an Angular app at `localhost:8080`), POST
requests with `Content-Type: application/json` trigger a CORS preflight OPTIONS check. If that
preflight fails for any reason (server disk full, transient error), the browser blocks the
request with:

```
Access to fetch at 'https://americansjewelry.com/.../object/insert' from origin
'http://localhost:8080' has been blocked by CORS policy: No 'Access-Control-Allow-Origin'
header is present on the requested resource.
```

**The fix** — match the pattern used by `FetchRunner.ts` in the-factory:

```typescript
await fetch(`${BASE_URL}/object/${action}`, {
    method:  "POST",
    mode:    "no-cors",   // no preflight OPTIONS, no CORS failure
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify({ object_view_id: ..., object_data: ... }),
});
```

`mode: 'no-cors'` bypasses the preflight entirely. The browser silently strips the
`Content-Type` header, but the PHP backend reads the body via `file_get_contents('php://input')`
and decodes it regardless — inserts and updates still work. The trade-off: the response is
opaque (unreadable), so `_post()` becomes fire-and-forget. This is acceptable for logging.

GET requests (used in `init()` for select) are simple CORS requests — they do **not** need
`no-cors` and work fine as-is.

The browser-facing `scripts/RemoteLogger.ts` already applies this fix. The Bun-based
`src/logger/RemoteLogger.ts` runs server-side where CORS does not apply, so it retains
full response checking.

## Viewer registration (index.html)

To see your logs in the web viewer at `localhost:8080`, register the `object_view_id` in
`/home/adamsl/the-factory/public/index.html`:

```html
<accordion-section class="" id="accordion-section-mylogger" 
    monitored_object_id="MyFeature_2026"
    data_source_location="https://americansjewelry.com/libraries/local-php-api/index.php/">
</accordion-section>
```

The viewer reads `monitored_object_id` attributes to know which records to fetch from the API.
Without this registration, the data is stored correctly but won't appear in the UI.
If `index.html` shows no logs, verify two things first: the logger's `monitored_object_id`
registration exists in the viewer and the viewer script actually loaded.

For legacy viewers that split IDs, keep the OAuth logger name numeric-suffixed, for example
`OAuthHealthCheck_2026`.

For local browser viewing with `/php-api`, run a proxy-capable dev server (for example
`webpack-dev-server`). A plain static server on `localhost:8080` will not proxy API requests and
the viewer will show 404/HTML parse errors instead of logs.

## Critical: `/php-api/object/selectAll` can hang in `pending`

A common failure pattern is:
- viewer HTML loads at `http://localhost:8080`
- accordion sections are constructed in console logs
- browser network shows many `GET /php-api/object/selectAll` requests stuck in `pending`
- console shows `TypeError: Failed to fetch` from `FetchRunner.run`
- integration tests time out during logger reset calls to `http://localhost:8080/php-api/...`

This indicates the local viewer is up, but the proxy target (`https://americansjewelry.com`) is
not responding in time. In that state, the webpack proxy keeps connections open and the UI appears
to stall on logger fetch.

Quick verification sequence:
```bash
# 1) Viewer static shell should respond fast
curl -i --max-time 5 http://localhost:8080/

# 2) Proxy path should respond; timeout here means proxy/upstream issue
curl -i --max-time 5 http://localhost:8080/php-api/object/selectAll

# 3) Upstream direct check; timeout here confirms upstream outage/latency
curl -i --max-time 10 \
  "https://americansjewelry.com/libraries/local-php-api/index.php/object/selectAll"
```

Interpretation:
- Step 1 pass + steps 2/3 timeout: viewer is healthy; upstream API is unavailable/slow.
- Step 2 fail + step 3 pass: local proxy misconfiguration.
- Step 1 fail: viewer dev server not running.

Optional hardening (to fail fast instead of hanging):
- add proxy timeouts in `the-factory/webpack.config.js` (`proxy./php-api.timeout`,
  `proxy./php-api.proxyTimeout`) so failed upstream calls surface quickly.

When debugging one logger (for example OAuth), temporarily keep only one `accordion-section` in
`index.html` to avoid concurrent polling noise from many sections.

## Server health check

Before relying on the logger, verify the server is up and has disk space:
```bash
curl -s "https://americansjewelry.com/libraries/local-php-api/index.php/object/selectAll"
```
A `507 Insufficient Storage` or `503 Service Unavailable` response means the server can't store
data. Inserts will appear to succeed but nothing will be saved. See [references/api.md](references/api.md).

## Usage in tests

Place `init()` at the start of the test body, `log()` around each key operation.
Leave the record in place after the test (don't call `destroy()`) so failures can be inspected:

```
GET https://americansjewelry.com/libraries/local-php-api/index.php/object/select/ScissariTest_2026
```

Log the key decision points:
- What is being invoked and with what args
- Exit codes / return values
- Pass/fail for each assertion
- Caught errors (log then rethrow)

If you want each run to start with a clean accordion terminal, call `clearLogs()` right after
`init()` and before the first `log()`.

If logger init or any `log()` call fails, stop the process immediately. Do not continue after a
failed logger state.

## tsconfig.json

When copying factory source files into a skill's `references/` directory, exclude them from
TypeScript compilation or they will break the host project's build:

```json
"exclude": [
  "src/skills/custom/**/scripts/**",
  "src/skills/custom/**/references/**"
]
```

## Reference files

- [references/api.md](references/api.md) — PHP API endpoints, actual response behavior, server health
- [references/shape.md](references/shape.md) — full object_data JSON shape, field rules, insert/update strategy
- `references/MonitoredObject.ts` — canonical shape source
- `references/ILogObject.ts` — log entry interface (timestamp = ms)
- `references/LogObjectFactory.ts` — log entry factory
- `references/MonitorLed.ts` / `MonitorLedClassObject.ts` — LED state classes
- `references/Stringifier.ts` — depth-limited serializer
