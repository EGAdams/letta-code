import { LettaLogger } from "../src/utils/LettaLogger";

const logger = new LettaLogger("TestLog_2026");

logger.log(
  "test-log.ts",
  "quick test entry",
  { message: "hello from letta-code test" },
  "green",
);

// Give the async flush time to complete
await new Promise((r) => setTimeout(r, 3000));
console.log(
  "Done — check https://americansjewelry.com/libraries/local-php-api/index.php/object?object_view_id=TestLog_2026",
);
