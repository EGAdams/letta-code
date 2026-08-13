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
   * Dispatch one lifecycle action. Returns the backend's {ok, text} on success;
   * on transport failure returns {ok:false, text:<error>} so the caller never
   * has to catch. All public verbs funnel through here.
   * @param {string} verb  e.g. "start" | "restart" | "deploy"
   * @param {string} serverKey
   * @returns {Promise<{ok:boolean, text:string}>}
   */
  async _action(verb, serverKey) {
    const { body } = buildServerActionRequest(serverKey, verb);
    try {
      const res = await this._http.postJSON(this._url, body);
      return { ok: res.ok !== false, text: res.text || "" };
    } catch (e) {
      return { ok: false, text: e.message };
    }
  }

  /** Start a server (default: the executor). */
  async start(serverKey = "executor") {
    return this._action("start", serverKey);
  }

  /** Restart a server (default: this dashboard) — re-runs the SAME code. */
  async restart(serverKey = "dashboard") {
    return this._action("restart", serverKey);
  }

  /**
   * Deploy: pull the latest code for the checked-out branch, then self-restart.
   * The keyboard-free path so the system is never dead in the water — callable by
   * Frita over Tailscale or by a one-tap dashboard button. Only "dashboard" has a
   * backend deploy handler today.
   */
  async deploy(serverKey = "dashboard") {
    return this._action("deploy", serverKey);
  }
}
