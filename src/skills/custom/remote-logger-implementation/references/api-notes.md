# Remote Logger API Notes

Base endpoint example:
- `http://100.80.49.10:8284/libraries/local-php-api`
- This is the canonical Windows 10 machine PHP API endpoint in this repo.

Routes:
- `GET /object/select?object_view_id=<id>`
- `POST /object/insert`
- `POST /object/update`
- `POST /object/delete`

Request body for insert/update:

```json
{
  "object_view_id": "MyLogger_2026",
  "object_data": "{\"object_view_id\":\"MyLogger_2026\",...}"
}
```

Notes:
- `object_data` is a serialized JSON string, not a nested JSON object.
- Some deployments can return non-ideal JSON or occasional 500s while still persisting.
- Verify persistence by re-selecting and checking the last log entry id.
