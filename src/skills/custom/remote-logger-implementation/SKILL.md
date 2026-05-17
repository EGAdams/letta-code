---
name: remote-logger-implementation
description: Explains how RemoteLogger works in letta-code and provides production-aligned implementation patterns in both TypeScript and Python. Use when building a new remote logger client, porting logger behavior across runtimes, or debugging logger persistence/LED behavior.
---

# Remote Logger Implementation

Use this skill when you need to build or port `RemoteLogger` behavior with parity to `src/logger/RemoteLogger.ts`.

Canonical API endpoint:
- Use the Windows 10 machine's PHP API at `http://100.80.49.10:8284/libraries/local-php-api`

## What RemoteLogger is

`RemoteLogger` persists one row per `object_view_id` in the monitored-objects API:
- `GET /object/select?object_view_id=<id>`
- `POST /object/insert`
- `POST /object/update`
- `POST /object/delete`

The `object_data` payload is a JSON string with this shape:

```json
{
  "object_view_id": "Example_2026",
  "logObjects": [
    {
      "timestamp": 1715779200000,
      "id": "Example_2026_123456_1715779200000",
      "message": "step started",
      "method": "createLogObject"
    }
  ],
  "monitorLed": {
    "classObject": {
      "background_color": "lightyellow",
      "text_align": "left",
      "margin_top": "2px",
      "color": "black"
    },
    "ledText": "step started",
    "RUNNING_COLOR": "lightyellow",
    "PASS_COLOR": "lightgreen",
    "FAIL_COLOR": "#fb6666"
  }
}
```

## Required behavior parity

1. `init()` must do `select` first; if missing, then `insert`.
2. `log(message)` appends a new entry and then `update`s.
3. `timestamp` must be milliseconds since epoch.
4. `monitorLed.classObject` must always exist.
5. Always set fetch/http timeouts; never allow indefinite hangs.
6. Treat update failures as possibly persisted; verify via `select` + retry before throwing.

## LED semantics

- PASS (green): message contains `finished`, `PASS`, or `test complete`
- FAIL (red): message contains `ERROR`, `FAIL`, or timeout/hang markers
- RUNNING (yellow): everything else

## Sanitization requirements

Before writing messages, sanitize to avoid transport/API failures:
- remove ANSI escapes
- bound max message length
- normalize control characters
- replace apostrophes and quotes with safe unicode variants

## Reference implementations

- TypeScript: `scripts/remote_logger.ts`
- Python: `scripts/remote_logger.py`
- Endpoint and shape notes: `references/api-notes.md`

## Usage workflow

1. Pick runtime (`TypeScript` or `Python`) and copy the matching reference script.
2. Set endpoint env var:
   - TypeScript: `LETTA_LOGGER_API`
   - Python: `LETTA_LOGGER_API`
   - Point it at the Windows 10 PHP API endpoint above.
3. Choose a unique logger id: `FeatureName_YYYY`.
4. Call:
   - `init()`
   - optional `clear_logs("ready.")`
   - `log(...)` throughout the run
5. Confirm persistence with:

```bash
curl -s "$LETTA_LOGGER_API/object/select?object_view_id=<LoggerId>"
```

## Repo anchors

- Canonical implementation: `src/logger/RemoteLogger.ts`
- Browser-safe variant: `src/skills/custom/creating-remote-loggers/scripts/RemoteLogger.ts`
- Related troubleshooting: `src/skills/custom/diagnose-yellow-test-status/SKILL.md`
