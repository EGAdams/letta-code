import { PollingController } from "../abstract/polling-controller.interface.js";
import { TextUtils } from "../abstract/text-utils.js";

/**
 * Classify a /api/server-logs status payload into a stable kind + label,
 * reproducing SM.openServer's status logic. Pure, so it is tested directly.
 *
 * @param {{ok?:boolean,text?:string}|null|undefined} status
 * @returns {{kind:"up"|"starting"|"down"|"none",ok:boolean,text:string,label:string}}
 */
export function classifyServerStatus(status) {
  if (!status)
    return { kind: "none", ok: false, text: "no health check", label: "" };
  const text = status.text || "";
  // Honor the backend's explicit 4-state `kind` when present, so the detail
  // panel agrees with the sidebar tab (e.g. yellow "concern" for a
  // down-but-restartable server instead of a bare red "Down").
  if (status.kind === "concern")
    return {
      kind: "concern",
      ok: !!status.ok,
      text,
      label: "NEEDS ATTENTION — ",
    };
  if (status.ok) return { kind: "up", ok: true, text, label: "UP — " };
  if (status.kind === "starting" || text.includes("STARTING"))
    return { kind: "starting", ok: false, text, label: "" };
  return { kind: "down", ok: false, text, label: "DOWN — " };
}

/**
 * ServerLogController — concrete PollingController for a single server's log
 * tail. Inherits the polling skeleton; binds `poll()`:
 *
 *   fetch `/api/server-logs?server=<key>` → report status via `onStatus`
 *   → on first empty result show a placeholder → else append each unseen row
 *   (deduped by `seq`).
 *
 * `onStatus({kind, ok, text, label})` lets a view drive the LED/start-button
 * without coupling this controller to the DOM.
 */
export class ServerLogController extends PollingController {
  constructor({
    http,
    view,
    serverKey,
    url = "/api/server-logs",
    onStatus = () => {},
    ...opts
  } = {}) {
    super(opts);
    if (!http || !view || !serverKey) {
      throw new Error("ServerLogController requires { http, view, serverKey }");
    }
    this._http = http;
    this._view = view;
    this._serverKey = serverKey;
    this._url = url;
    this._onStatus = onStatus;
  }

  /** @override */
  async poll() {
    let data;
    try {
      data = await this._http.getJSON(
        `${this._url}?server=${encodeURIComponent(this._serverKey)}`,
      );
    } catch (e) {
      this._onStatus({ kind: "down", ok: false, text: e.message, label: "" });
      return;
    }
    this._onStatus(classifyServerStatus(data.status));

    const rows = data.rows || [];
    if (this._view.isFirstRender && !rows.length) {
      this._view.renderEmptyOnce(
        '<div class="msi-entry dim">&mdash; no log lines &mdash;</div>',
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
