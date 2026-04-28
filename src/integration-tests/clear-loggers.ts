import { ALL_LOGGER_IDS, resetLogger } from "./logger-helpers";

console.log(`Clearing ${ALL_LOGGER_IDS.length} loggers at http://localhost:8080...`);
for (const id of ALL_LOGGER_IDS) {
  await resetLogger(id);
  console.log(`  cleared: ${id}`);
}
console.log("Done.");
