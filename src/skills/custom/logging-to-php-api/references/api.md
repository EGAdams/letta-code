# PHP API Reference

Base URL: `https://americansjewelry.com/libraries/local-php-api/index.php/object`

## Endpoints

### Select All
```
GET /selectAll
Response: JSON array of { object_view_id, object_data } objects
```

### Select One
```
GET /select/{object_view_id}
Response: JSON object { object_view_id, object_data }
```

### Insert
```
POST /insert
Body: { "object_view_id": "ClassName_2026", "object_data": "<json string>" }
Response: "insert success."  (on success)
          "*** ERROR: ..." (on duplicate key or DB error)
```

### Update
```
POST /update
Body: { "object_view_id": "ClassName_2026", "object_data": "<json string>" }
Response: null/empty (always — no error detection possible from response)
```

### Delete
```
POST /delete
Body: { "object_view_id": "ClassName_2026" }
```

## Notes

- `object_data` must be a **string** (JSON-encoded), not a raw object
- Timeout: use 5s max to avoid blocking the host object
- The update endpoint returns no useful success/failure signal — always insert first
