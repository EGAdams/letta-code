---
name: creating-remote-loggers
description: Creates persistent remote loggers that write structured log entries to a PHP-backed API at americansjewelry.com. Use when the user wants to log operations, test steps, or workflow events to a persistent remote store for later inspection. Handles insert/update/select/delete against the monitored_objects API. Copy scripts/RemoteLogger.ts into the target project and follow the usage pattern below.
---

# Creating Remote Loggers

Loggers persist named `object_view_id` records to the PHP API. Each record holds an array of `logObjects` (timestamped messages). All API and network errors are caught internally — logger failures never break the calling code.

## Quick start

Copy `scripts/RemoteLogger.ts` into the project (e.g., `src/logger/RemoteLogger.ts`), then:

```typescript
import { RemoteLogger } from "../logger/RemoteLogger";

const logger = new RemoteLogger(`MyFeature_${Math.floor(Date.now() / 1000)}`);
await logger.init();          // loads existing record or inserts fresh one
await logger.log("step 1 started");
await logger.log("step 1 complete");
// optionally clean up:
await logger.destroy();
```

## Naming convention

Use `FeatureName_<unix_timestamp>` for `object_view_id` — unique per run, human-readable, query-friendly:
```
ScissariTest_1716200000
ReceiptScan_1716200123
```

## Usage in tests

Place `init()` at the start of the test body, `log()` around each key operation, and leave the record in place after the test (don't call `destroy()`) so failures can be inspected remotely.

Log the important decision points:
- What is being invoked and with what arguments
- Exit codes / return values
- Pass/fail result for each assertion
- Any thrown errors (catch, log, rethrow)

## Viewing logs

```
GET https://americansjewelry.com/libraries/local-php-api/index.php/object/select/ScissariTest_1716200000
```

See [references/api.md](references/api.md) for the full API reference.
