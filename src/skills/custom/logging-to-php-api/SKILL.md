---
name: logging-to-php-api
description: Attaches loggers to Python and TypeScript objects in letta-src and letta-code that send structured log data to the americansjewelry.com PHP REST API. Uses the monitored_objects envelope pattern (ClassName_Year as object_view_id). Use when adding observability to Letta server services (ProviderManager, UserManager, etc.) or letta-code agent operations (client, create, model). See references/api.md for endpoint details and references/envelope-list.md for existing envelopes.
---

# Logging to PHP API

## Overview

All log data is stored in the `monitored_objects` MySQL table via REST at:
```
https://americansjewelry.com/libraries/local-php-api/index.php/object/
```

Each class gets one **envelope** — a persistent row keyed by `object_view_id` (`ClassName_Year`).
The `object_data` field holds a JSON array of log entries that is fully replaced on each flush.

## Envelope Naming

```
ProviderManager_2026
UserManager_2026
LettaClient_2026
CreateAgent_2026
```

## Python Logger (`letta_logger.py`)

Canonical location: `/home/adamsl/letta-src/letta/letta_logger.py`
Script copy: `scripts/letta_logger.py`

Usage in a wrapper:
```python
from letta.letta_logger import LettaLogger

class LoggedProviderManager(ProviderManager):
    def __init__(self):
        super().__init__()
        self._log = LettaLogger("ProviderManager_2026")

    async def list_providers_async(self, actor, **kwargs):
        self._log.log(__name__, "list_providers_async", status="yellow")
        try:
            result = await super().list_providers_async(actor, **kwargs)
            self._log.log(__name__, "list_providers_async", {"count": len(result)}, status="green")
            return result
        except Exception as e:
            self._log.log(__name__, "list_providers_async", {"error": str(e)}, status="red")
            raise
```

Wrapper locations:
- `/home/adamsl/letta-src/letta/logged_provider_manager.py`
- `/home/adamsl/letta-src/letta/logged_user_manager.py`

## TypeScript Logger (`LettaLogger.ts`)

Canonical location: `/home/adamsl/letta-code/src/utils/LettaLogger.ts`
Script copy: `scripts/LettaLogger.ts`

Usage in letta-code (already wired in `client.ts` and `create.ts`):
```typescript
import { LettaLogger } from "../utils/LettaLogger";
const _clientLog = new LettaLogger("LettaClient_2026");
_clientLog.log("getClient", "called");
_clientLog.log("getClient", "client created", { baseURL }, "green");
```

## Upsert Logic

Both loggers use insert-first upsert:
1. POST to `/insert` — if **HTTP 2xx** response → done (new row created)
2. Otherwise POST to `/update` (row already exists)

**Important:** The PHP API response body is double-JSON-encoded (the server wraps `json_encode("insert success.")` in a second `json_encode`), so the body never literally contains `"insert success"`. Always detect success via HTTP status code, not body text.

- TypeScript: check `res.ok` (not `text.includes("insert success")`)
- Python: `urlopen` raises on HTTP errors, so reaching the `with` block means 2xx — return `True`

Never throw on log failure — logging must never crash the host object.

## After Hot-Patching the Container

After `docker cp` + `docker restart letta-server`, verify the server is back up:

```bash
curl -s http://100.80.49.10:8283/v1/health/   # confirm {"status":"ok"}
```

## Adding a New Logged Object

1. Choose envelope name: `ClassName_2026`
2. Subclass (Python) or wrap (TypeScript) the target object
3. Instantiate `LettaLogger("ClassName_2026")` in constructor
4. Call `log(method, event, data, status)` at start (yellow) and end (green/red) of key methods
5. Update `references/envelope-list.md`

## Validation

**End-to-end test (2026-04-22):**
```bash
cd /home/adamsl/letta-code
bun scripts/test-log.ts
# Output: Done — check https://americansjewelry.com/.../object?object_view_id=TestLog_2026
```
The test script creates a `TestLog_2026` envelope and flushes one entry. The 3-second wait (`await new Promise(r => setTimeout(r, 3000))`) is intentional — it gives the async flush time to complete before the process exits.

**Note on network requirements:** The TypeScript LettaLogger uses `AbortSignal.timeout(2000)` so it fails gracefully if americansjewelry.com is unreachable. However, on this machine the internet IS reachable from letta-code (the test succeeds). The server-side Python logger has a known event loop saturation issue when internet is blocked — see the letta-admin skill for the hot-patch.

## References

- `references/api.md` — PHP endpoint details and request/response formats
- `references/envelope-list.md` — All active envelopes and what they log
