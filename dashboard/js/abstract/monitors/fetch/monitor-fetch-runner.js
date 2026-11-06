import { BackoffFetchRunner } from "./backoff-fetch-runner.js";
import { DedupFetchRunner } from "./dedup-fetch-runner.js";
import { FetchRunner } from "./fetch-runner.js";
import { LastGoodFetchRunner } from "./last-good-fetch-runner.js";

/**
 * The decorator stack every monitor uses, outermost first:
 * last-good cache → backoff → in-flight dedup → plain GET.
 */
export function createMonitorFetchRunner(http, options = {}) {
  return new LastGoodFetchRunner(
    new BackoffFetchRunner(
      new DedupFetchRunner(new FetchRunner(http, options)),
      options,
    ),
  );
}
