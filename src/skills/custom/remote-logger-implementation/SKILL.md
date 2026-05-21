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

## Known Pitfall: Permanent Logger Disable on First Error (Python Agents)

When porting `RemoteLogger` to Python (especially for multi-agent systems like a2a_communicating_agents), avoid a critical mistake:

**Bad pattern:**
```python
_REMOTE_LOGGER_ENABLED = False

def log_update(msg: str):
    global _REMOTE_LOGGER_ENABLED
    if not _REMOTE_LOGGER_ENABLED:
        return
    try:
        response = requests.post(logger_api_url, ...)
        if response.status_code != 200:
            _REMOTE_LOGGER_ENABLED = False  # ← WRONG: permanent disable
            return
    except Exception:
        _REMOTE_LOGGER_ENABLED = False  # ← WRONG: permanent disable
```

This sets `_REMOTE_LOGGER_ENABLED = False` on the first HTTP error or timeout. Once set, it is never reset, and the agent stops logging entirely — even though the process continues running. The log viewer shows a stale timestamp 44+ hours in the past while the agent is still alive.

**Correct pattern:**
```python
import time

_REMOTE_LOGGER_RETRY_AFTER = 0.0  # Use time.monotonic() + seconds

def log_update(msg: str):
    global _REMOTE_LOGGER_RETRY_AFTER
    now = time.monotonic()
    if now < _REMOTE_LOGGER_RETRY_AFTER:
        return  # Still in backoff period
    
    try:
        response = requests.post(logger_api_url, ...)
        if response.status_code != 200:
            _REMOTE_LOGGER_RETRY_AFTER = now + 60.0  # 60-second backoff
            return
        # SUCCESS: reset backoff so next call goes through
        _REMOTE_LOGGER_RETRY_AFTER = 0.0
    except Exception:
        _REMOTE_LOGGER_RETRY_AFTER = now + 60.0  # 60-second backoff
```

This replaces a permanent flag with a **60-second retry backoff**. After 60 seconds, the agent automatically tries again. On success, it resets the timer immediately. This allows transient API failures to recover without operator intervention or process restart.

For detailed diagnosis and the bug history, see skill `a2a-remote-logger-debug`.
