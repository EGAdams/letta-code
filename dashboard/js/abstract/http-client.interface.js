import { abstractMethod } from "./not-implemented.js";

/**
 * HttpClient — Adapter + Template Method.
 *
 * The original code duplicated an identical `fetchJSON()` inside both AM and SM.
 * That method had two parts:
 *   1. the transport (call fetch, get a Response)  ← varies / needs mocking
 *   2. the error-unwrapping policy (if !ok, read `.detail`, throw a tidy Error)
 *      ← shared, pure, worth testing once
 *
 * We split them: `request()` is the abstract primitive (Adapter over fetch),
 * while `getJSON()` / `postJSON()` are concrete Template Methods that apply the
 * shared unwrap policy. A test double only has to implement `request()`.
 *
 * Implementations must return a Response-like object: { ok, status, json() }.
 */
export class HttpClient {
  /**
   * Abstract transport. Override in js/implementation/.
   * @param {string} _url
   * @param {object} [_opts] fetch-style options
   * @returns {Promise<{ok:boolean,status:number,json:()=>Promise<any>}>}
   */
  async request(_url, _opts) {
    abstractMethod("request");
  }

  /** GET + parse JSON, applying the shared error policy. */
  async getJSON(url) {
    return this._unwrap(await this.request(url));
  }

  /** POST a JSON body + parse JSON, applying the shared error policy. */
  async postJSON(url, body) {
    const res = await this.request(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return this._unwrap(res);
  }

  /** Shared policy: turn a non-OK response into a trimmed Error. */
  async _unwrap(res) {
    if (!res.ok) {
      let detail = "";
      try {
        detail = (await res.json()).detail || "";
      } catch {
        /* body was not JSON — ignore */
      }
      throw new Error(
        `HTTP ${res.status}${detail ? ` — ${detail.slice(0, 120)}` : ""}`,
      );
    }
    return res.json();
  }
}
