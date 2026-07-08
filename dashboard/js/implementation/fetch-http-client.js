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

  /** @override transport: delegate straight to fetch with timeout. */
  async request(url, opts = {}) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => {
      controller.abort(
        new DOMException(
          `Request timed out after ${this._timeout / 1000}s: ${url}`,
          "TimeoutError",
        ),
      );
    }, this._timeout);
    try {
      return await this._fetch(url, {
        ...opts,
        signal: controller.signal,
      });
    } finally {
      clearTimeout(timeoutId);
    }
  }
}
