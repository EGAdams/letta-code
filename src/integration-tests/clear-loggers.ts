process.env.LETTA_LOGGER_RESET_API =
  process.env.LETTA_LOGGER_RESET_API ??
  "http://100.80.49.10:8284/libraries/local-php-api";

const { ALL_LOGGER_IDS, flushAllLoggers } = await import("./logger-helpers");

console.log(
  `Flushing ${ALL_LOGGER_IDS.length} loggers at ${process.env.LETTA_LOGGER_RESET_API}...`,
);
await flushAllLoggers();
console.log("Done.");
