/**
 * Build the request payload for a server lifecycle action, reproducing the
 * body SM.openServer's Start button POSTed to `/api/server-action`. Pure, so it
 * is tested directly.
 *
 * @param {string} server  server key (e.g. "executor")
 * @param {string} action  action verb (e.g. "start")
 * @returns {{url:string, body:{server:string, action:string}}}
 */
export function buildServerActionRequest(server, action) {
  if (!server || !action) {
    throw new Error("buildServerActionRequest requires { server, action }");
  }
  return { url: "/api/server-action", body: { server, action } };
}

/**
 * ServerActionController — Command. Wraps a lifecycle action (currently only
 * "start") against `/api/server-action` so a view can trigger it without
 * knowing the transport. Reproduces the inline Start-button handler:
 *
 *   POST /api/server-action { server, action:"start" } → { ok, text }
 *
 * The HttpClient is injected (constructor) and the only browser dependency, so
 * this is unit-testable with a fake http that records postJSON calls.
 */
export class ServerActionController {
  /**
   * @param {{ http: import("../abstract/http-client.interface.js").HttpClient,
   *           url?: string }} deps
   */
  constructor({ http, url = "/api/server-action" } = {}) {
    if (!http || typeof http.postJSON !== "function") {
      throw new Error("ServerActionController requires { http }");
    }
    this._http = http;
    this._url = url;
  }

  /**
   * Start a server. Returns the backend's {ok, text} on success; on transport
   * failure returns {ok:false, text:<error>} so the caller never has to catch.
   * @param {string} [serverKey]
   * @returns {Promise<{ok:boolean, text:string}>}
   */
  async start(serverKey = "executor") {
    const { body } = buildServerActionRequest(serverKey, "start");
    try {
      const res = await this._http.postJSON(this._url, body);
      return { ok: res.ok !== false, text: res.text || "" };
    } catch (e) {
      return { ok: false, text: e.message };
    }
  }

  async restart(serverKey = "dashboard") {
    const { body } = buildServerActionRequest(serverKey, "restart");
    try {
      const res = await this._http.postJSON(this._url, body);
      return { ok: res.ok !== false, text: res.text || "" };
    } catch (e) {
      return { ok: false, text: e.message };
    }
  }
}
