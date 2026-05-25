---
name: letta-message-search-sql-fallback
description: Fix the 400 "Message search requires message embedding, OpenAI, and Turbopuffer to be enabled" error on self-hosted Letta. Patches search_messages_org_async in message_manager.py to fall back to SQL instead of throwing when Turbopuffer isn't configured.
---

# Letta Message Search SQL Fallback Patch

## The problem

Self-hosted Letta 0.16.7 has two message search paths:

| Endpoint | Function | Turbopuffer missing |
|---|---|---|
| `GET /v1/agents/{id}/messages` with `query_text` | `search_messages_async` | Falls back to SQL ✓ |
| `POST /v1/agents/messages/search` | `search_messages_org_async` | **Throws 400 ✗** |
| `POST /v1/messages/search` | `search_messages_org_async` | **Throws 400 ✗** |

The error: `"Message search requires message embedding, OpenAI, and Turbopuffer to be enabled."`

This is a cloud-only feature in stock Letta — self-hosted servers without Turbopuffer and OpenAI embeddings get a hard error. The fix: add a SQL fallback to `search_messages_org_async` so it behaves like the per-agent search.

## The fix

**Source file**: `/home/adamsl/letta-src/letta/services/message_manager.py`  
**Function**: `search_messages_org_async` (~line 1298)

Replace:
```python
        if not should_use_tpuf_for_messages():
            raise ValueError("Message search requires message embedding, OpenAI, and Turbopuffer to be enabled.")
```

With:
```python
        if not should_use_tpuf_for_messages():
            # SQL fallback: Turbopuffer not configured, fall back to SQL text search
            messages = await self.list_messages(
                actor=actor,
                agent_id=agent_id,
                query_text=query_text,
                roles=roles,
                limit=limit,
                ascending=False,
                conversation_id=conversation_id,
            )

            def _extract_text(m):
                parts = [c.text for c in (m.content or []) if hasattr(c, "text") and c.text]
                return " ".join(parts)

            return [
                MessageSearchResult(
                    embedded_text=_extract_text(m),
                    message=m,
                    fts_rank=None,
                    vector_rank=None,
                    rrf_score=0.0,
                )
                for m in messages
            ]
```

## Applying the patch

```bash
# 1. Edit the source file on the host
ssh 100.80.49.10
nano /home/adamsl/letta-src/letta/services/message_manager.py
# (make the change above)

# 2. Copy into the running container
docker cp /home/adamsl/letta-src/letta/services/message_manager.py letta-server:/app/letta/services/message_manager.py

# 3. Restart the server
docker restart letta-server

# 4. Wait for healthy, then reload nginx DNS
until docker inspect letta-server --format '{{.State.Health.Status}}' | grep -q healthy; do sleep 3; done
docker exec letta-bridge nginx -s reload

# 5. Test
curl -s -X POST http://100.80.49.10:18283/v1/agents/messages/search \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "limit": 3}' | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('OK:', len(d), 'results') if isinstance(d, list) else print('Error:', d)
"
```

## Important: patch is not persistent across image rebuilds

The patch lives in:
- Source: `/home/adamsl/letta-src/letta/services/message_manager.py` (persists on host ✓)
- Container: `/app/letta/services/message_manager.py` (lost on `docker compose up` with rebuild ✗)

After any `docker compose up --build` or image rebuild, re-run step 2 (`docker cp`) and step 3 (restart).

## Why `nginx -s reload` after restart

`letta-bridge` nginx resolves the `letta-server` hostname at startup and caches the IP. When `letta-server` restarts, it may get a different internal IP. `nginx -s reload` forces a fresh DNS lookup without downtime.

## Notes

- SQL fallback returns `rrf_score=0.0` and `fts_rank=null` / `vector_rank=null` — no ranking, just recency order
- `query_text` filters by SQL LIKE match on message text content
- The patch is already applied as of 2026-05-23
