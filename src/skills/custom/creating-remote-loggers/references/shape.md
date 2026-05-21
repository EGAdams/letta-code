# object_data Shape

The `object_data` field stored in the API must match the shape that `MonitoredObject` serializes,
so that the web viewer renders the LED and log correctly.

## Full JSON structure

```json
{
  "object_view_id": "ScissariTest_2026",
  "logObjects": [
    {
      "timestamp": 1716200000123,
      "id": "ScissariTest_2026_4823901234567_1716200000123",
      "message": "Test started",
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
    "ledText": "Test started",
    "RUNNING_COLOR": "lightyellow",
    "PASS_COLOR": "lightgreen",
    "FAIL_COLOR": "#fb6666"
  }
}
```

## Field rules

### `logObjects[].timestamp`
**Milliseconds** since epoch — use `Date.now()`, NOT `Math.floor(Date.now() / 1000)`.
Source: `ILogObject.ts` comment: *"timestamp in milliseconds since epoch"*.

### `logObjects[].id`
Format: `{object_view_id}_{random}_{timestamp_ms}`
Source: `LogObjectFactory.createLogObject` uses `Date.now()` for the trailing number.

### `monitorLed` — required, not optional

**Omitting `monitorLed` crashes the web viewer.** `monitor-led.component.ts` line 75:
```typescript
this.monitor_led_data = data.monitorLed;  // becomes undefined if missing
this.render();                             // crashes: Cannot read properties of undefined (reading 'ledText')
```

The component's `monitor_led_data` must never be set to `undefined`. The fix applied to
`monitor-led.component.ts` guards the assignment:
```typescript
if ( data.monitorLed ) { this.monitor_led_data = data.monitorLed; }
this.render();
```
This fix is in place, but the field should still always be included in `object_data` so the LED
reflects the correct state.

### `monitorLed.classObject.background_color`
Drives the LED color in the viewer:

| Condition on message | background_color | color |
|----------------------|-----------------|-------|
| contains `"ERROR"`   | `#fb6666`       | white |
| contains `"finished"` or `"PASS"` | `lightgreen` | black |
| otherwise (running)  | `lightyellow`   | black |

Source: `MonitoredObject.logUpdate()` — sets fail/pass/running based on message content.

### `monitorLed.ledText`
The last log message — what the LED displays as its current status text.

---

## insert vs update strategy

Do **not** use an upsert (update-then-insert) pattern. Because `affected_rows` is always `null`
in the API response, you cannot tell whether an update matched any rows.

Correct strategy:
- `init()` — SELECT the record; if not found, INSERT (creates the record)
- `log()` — always UPDATE (record is guaranteed to exist after init)

---

## Source files (in this references/ directory)

- `MonitoredObject.ts` — owns `object_view_id`, `logObjects`, `monitorLed`; calls insert on construct, update on logUpdate
- `ILogObject.ts` — interface for a single log entry
- `LogObjectFactory.ts` — creates log entries; timestamp is `Date.now()` (ms)
- `MonitorLed.ts` — LED state: classObject + ledText + color constants
- `MonitorLedClassObject.ts` — CSS properties driving the LED element
- `IMonitorLedClassObject.ts` — interface for MonitorLedClassObject
- `Stringifier.ts` — depth-limited JSON serializer used by MonitoredObject
