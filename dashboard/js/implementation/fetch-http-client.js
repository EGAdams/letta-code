import { HttpClient } from "../abstract/http-client.interface.js";

/**
 * FetchHttpClient — concrete HttpClient bound to `window.fetch`.
 *
 * Implements only the abstract transport primitive `request()`; the shared
 * error-unwrap policy (getJSON / postJSON / _unwrap) lives in the base class.
 * `fetch` is injected (defaulting to the global) so tests can drive it with a
 * scripted responder instead of touching the network.
 */
export class FetchHttpClient extends HttpClient {
  /** @param {typeof fetch} [fetchFn] */
  constructor(fetchFn = globalThis.fetch?.bind(globalThis)) {
    super();
    if (typeof fetchFn !== "function") {
      throw new Error("FetchHttpClient requires a fetch implementation");
    }
    this._fetch = fetchFn;
    // Guard against hung requests, but leave headroom for slow endpoints —
    // a cold /api/agents can block >10s on the Letta roster fetch.
    this._timeout = 30000;
  }

  /**
   * @override transport: delegate straight to fetch with timeout.
   *
   * `opts.timeout` (ms) overrides the default for a single call - some
   * endpoints (e.g. /api/letta-code-message) have a much larger server-side
   * budget, and aborting at 30s discards an answer the backend still produces.
   */
  async request(url, opts = {}) {
    const { timeout, ...fetchOpts } = opts;
    const budget =
      typeof timeout === "number" && timeout > 0 ? timeout : this._timeout;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => {
      controller.abort(
        new DOMException(
          `Request timed out after ${budget / 1000}s: ${url}`,
          "TimeoutError",
        ),
      );
    }, budget);
    try {
      return await this._fetch(url, {
        ...fetchOpts,
        signal: controller.signal,
      });
    } finally {
      clearTimeout(timeoutId);
    }
  }
}
