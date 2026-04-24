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

### POST body (insert / update)
```json
{ "object_view_id": "MyLogger_1234", "object_data": "<json-stringified state>" }
```

### POST body (delete)
```json
{ "object_view_id": "MyLogger_1234" }
```

### object_data shape
```json
{
  "logObjects": [
    { "timestamp": 1776212055, "id": "MyLogger_rand_ts", "message": "...", "method": "createLogObject" }
  ],
  "object_view_id": "MyLogger_1234"
}
```

### Responses
- Insert: `"insert success."`
- Update / Delete: affected-rows integer
- Errors: `{ "error": "..." }` with HTTP 404 / 422 / 500
