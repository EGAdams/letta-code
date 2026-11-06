import { abstractMethod } from "../../not-implemented.js";

/**
 * IFetchRunner — the-factory's FetchRunner, cut down to its one promise:
 * run(url) resolves to the parsed JSON or rejects. Its old extras (dedup,
 * backoff, last-good cache) are separate Decorators over this.
 */
export class IFetchRunner {
  async run(_url) {
    abstractMethod("run");
  }
}
