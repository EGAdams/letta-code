import { ALL_LOGGER_IDS, resetLogger } from "./logger-helpers";

console.log(
  `Clearing ${ALL_LOGGER_IDS.length} loggers at https://americansjewelry.com...`,
);
for (const id of ALL_LOGGER_IDS) {
  await resetLogger(id);
  console.log(`  cleared: ${id}`);
}
console.log("Done.");
