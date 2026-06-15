import { PollingController } from "../abstract/polling-controller.interface.js";
import { TextUtils } from "../abstract/text-utils.js";

/**
 * Map an SSH connection-test status `{ ok, text }` to a render-friendly shape.
 * SSH connections are only UP/DOWN (no "starting"); a missing status means the
 * check hasn't run yet ("checking…"). Mirrors SSHM.applyStatus's labels.
 *
 * @returns {{kind:"up"|"down"|"checking", ok:boolean, text:string, label:string}}
 */
export function classifyConnectionStatus(status) {
  if (!status) {
    return { kind: "checking", ok: false, text: "checking…", label: "" };
  }
  if (status.ok) {
    return {
      kind: "up",
      ok: true,
      text: status.text || "",
      label: "CONNECTED — ",
    };
  }
  return { kind: "down", ok: false, text: status.text || "", label: "DOWN — " };
}

/**
 * ConnectionLogController — concrete PollingController for an SSH connection's
 * test log. Like ServerLogController but targets /api/ssh-connection-logs?conn=
 * (5s), reports status via onStatus(classifyConnectionStatus(...)), and shows a
 * connection-specific empty placeholder. Reproduces SSHM.openConnection's pull.
 */
export class ConnectionLogController extends PollingController {
  constructor({
    http,
    view,
    connKey,
    url = "/api/ssh-connection-logs",
    onStatus = () => {},
    ...opts
  } = {}) {
    super({ intervalMs: 5000, ...opts });
    if (!http || !view || !connKey) {
      throw new Error(
        "ConnectionLogController requires { http, view, connKey }",
      );
    }
    this._http = http;
    this._view = view;
    this._connKey = connKey;
    this._url = url;
    this._onStatus = onStatus;
  }

  /** @override */
  async poll() {
    let data;
    try {
      data = await this._http.getJSON(
        `${this._url}?conn=${encodeURIComponent(this._connKey)}`,
      );
    } catch (e) {
      this._onStatus({ kind: "down", ok: false, text: e.message, label: "" });
      return;
    }
    this._onStatus(classifyConnectionStatus(data.status));
    const rows = data.rows || [];
    if (this._view.isFirstRender && !rows.length) {
      this._view.renderEmptyOnce(
        '<div class="msi-entry dim">&mdash; no connection tests recorded yet &mdash;</div>',
      );
      return;
    }
    for (const r of rows) {
      this._view.appendUnique(
        `seq:${r.seq}`,
        `<div class="msi-entry">${TextUtils.esc(String(r.text || ""))}</div>`,
      );
    }
  }
}

/**
 * ConnectionTestController — Command that runs one SSH connection test
 * (GET /api/ssh-connection-test?conn=<key>). Returns the status shape on
 * success, or { failed:true, text } when the request itself errors (so the
 * caller can show "TEST FAILED — …"). Mirrors SSHM's Test Connection button.
 */
export class ConnectionTestController {
  constructor({ http, url = "/api/ssh-connection-test" } = {}) {
    if (!http || typeof http.getJSON !== "function") {
      throw new Error("ConnectionTestController requires an HttpClient");
    }
    this._http = http;
    this._url = url;
  }

  async test(connKey) {
    try {
      const res = await this._http.getJSON(
        `${this._url}?conn=${encodeURIComponent(connKey)}`,
      );
      return { ok: res.ok !== false, text: res.text || "", failed: false };
    } catch (e) {
      return { ok: false, text: e.message, failed: true };
    }
  }
}
