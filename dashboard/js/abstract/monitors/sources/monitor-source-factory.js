import { createMonitorFetchRunner } from "../fetch/monitor-fetch-runner.js";
import { MonitorSource } from "./monitor-source.js";
import { FunctionProcessor } from "./parsers/function-processor.js";

/**
 * Builds one MonitorSource per catalog row, all sharing one decorated
 * fetch runner (so dedup and backoff see every request).
 */
export function createMonitorSources(catalog, http, options = {}) {
  const runner = createMonitorFetchRunner(http, options);
  return catalog.map(
    ({ parse, ...row }) =>
      new MonitorSource({
        ...row,
        processor: new FunctionProcessor(parse),
        runner,
      }),
  );
}
