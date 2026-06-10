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
  }

  /** @override transport: delegate straight to fetch. */
  async request(url, opts) {
    return this._fetch(url, opts);
  }
}
