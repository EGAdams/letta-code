# Remote Logger PHP API Reference

**Base URL:** `https://americansjewelry.com/libraries/local-php-api/index.php`

All requests/responses use JSON. CORS is open.

## Endpoints

| Action | Method | Path |
|--------|--------|------|
| Select all | GET | `/object/selectAll` |
| Select one | GET | `/object/select/{object_view_id}` |
| Insert | POST | `/object/insert` |
| Update | POST | `/object/update` |
| Delete | POST | `/object/delete` |

### POST body (insert / update / delete)
```json
{ "object_view_id": "MyLogger_1234", "object_data": "<json-stringified state>" }
```
Delete only needs `object_view_id`.

---

## Actual response behavior (differs from docs)

The docs describe clean responses. Reality:

| Endpoint | Documented response | Actual response |
|----------|-------------------|-----------------|
| insert   | `"insert success."` | `"\""` — a stray quote character |
| update   | affected-rows integer | `{"affected_rows":null,"insert_id":null,...,"error":null}` |
| delete   | affected-rows integer | same null-fields object as update |
| select (not found) | (not documented) | `null` |
| select (found) | `{"id":N,"object_view_id":"...","object_data":"..."}` | ✓ matches docs |

### Key facts confirmed by live testing

- **Insert works** despite returning `"\""` — verified by select after insert
- **Update works** despite `affected_rows: null` — verified by select after update
- **`affected_rows` is always null** — do NOT use it to determine whether a write succeeded
- **`error: null` is not an error** — check `body.error` is truthy, not just that the key exists

### Correct error detection in TypeScript

```typescript
// WRONG — fires on every response because "error" key always exists
if ("error" in body) throw ...

// CORRECT — only throws when error is a real value
if (body !== null && typeof body === "object" && (body as Record<string, unknown>)["error"]) throw ...
```

---

## Server health

The server at `americansjewelry.com` can return:

| Status | Meaning | Effect on logger |
|--------|---------|-----------------|
| `507 Insufficient Storage` | Disk full | insert returns HTML, data not stored |
| `503 Service Unavailable` | Server down | all requests fail |

**Always run a curl insert+select smoke test before trusting the logger:**
```bash
# Insert
curl -s -X POST ".../object/insert" -H "Content-Type: application/json" \
  -d '{"object_view_id":"SmokeTest_001","object_data":"{\"test\":true}"}'

# Verify
curl -s ".../object/select/SmokeTest_001"

# Clean up
curl -s -X POST ".../object/delete" -H "Content-Type: application/json" \
  -d '{"object_view_id":"SmokeTest_001"}'
```

If select returns `null` after insert, the server likely had a storage problem at insert time.

---

## Web Viewer (localhost:8080)

The data stored via this API is viewable in a web UI at `http://localhost:8080`, but that URL is
only the local HTML viewer. The viewer is served from
`/home/adamsl/the-factory/public/index.html`, and the PHP API remains the production endpoint at
`https://americansjewelry.com/libraries/local-php-api/index.php`.

The record will be visible only if the `object_view_id` is registered in the viewer's
configuration.

To make a logger visible in the viewer, add an `accordion-section` element to `/home/adamsl/the-factory/public/index.html`:

```html
<accordion-section class="" id="accordion-section-mylogger" 
    monitored_object_id="MyLogger_2026"
    data_source_location="https://americansjewelry.com/libraries/local-php-api/index.php/">
</accordion-section>
```

The viewer fetches `monitored_object_id` from the HTML and queries this API to display:
- Log entries (timestamps, messages)
- Monitor LED (status indicator: yellow=running, green=pass, red=error)
- Full history of state changes

If `index.html` shows no logs, check the `monitored_object_id` registration and viewer script load
before debugging the API.

For browser viewers, direct cross-origin `GET /object/select/<id>` has shown CORS/protocol
instability in practice. Prefer `GET /object/selectAll` and client-side filtering in the viewer
when you need a more resilient read path.

When isolating OAuth viewer failures, temporarily reduce the UI to a single accordion section
containing only the OAuth logger. This avoids request storms and makes fetch failures easier to
trace.

If local HTML is served by a plain static server, `/php-api/...` proxy routes will 404 and the
viewer will parse HTML as JSON (`Unexpected token '<'`). Use a proxy-capable dev server (for
example `webpack-dev-server`) when the viewer is configured with a local proxy path.

For viewer correctness after remote clears, treat API reads as authoritative snapshots:
- clear local rendered rows before writing the latest `logObjects`
- do not append-only forever, or `clearLogs()` server updates will not appear in the accordion
