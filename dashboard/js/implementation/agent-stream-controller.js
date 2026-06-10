import { PollingController } from "../abstract/polling-controller.interface.js";
import { AgentStreamFormatter } from "../abstract/stream-formatter.interface.js";
import { TextUtils } from "../abstract/text-utils.js";

/**
 * AgentStreamController — concrete PollingController for an agent stream
 * (thoughts / messages / tool-calls). The start/stop/interval skeleton is
 * inherited; this binds the `poll()` work:
 *
 *   fetch `<url>?agent=<id>` → on first empty result show a "nothing yet"
 *   placeholder → otherwise append each unseen row via the StreamFormatter.
 *
 * Reproduces AM.renderStream's dedup + first-render behavior, but the transport
 * (HttpClient) and rendering (ConsoleView) are injected ports.
 */
export class AgentStreamController extends PollingController {
  constructor({
    http,
    view,
    url,
    agentId,
    label = "entries",
    formatter = new AgentStreamFormatter(),
    ...opts
  } = {}) {
    super(opts);
    if (!http || !view || !url || !agentId) {
      throw new Error(
        "AgentStreamController requires { http, view, url, agentId }",
      );
    }
    this._http = http;
    this._view = view;
    this._url = url;
    this._agentId = agentId;
    this._label = label;
    this._formatter = formatter;
  }

  /** @override */
  async poll() {
    let rows;
    try {
      rows = await this._http.getJSON(
        `${this._url}?agent=${encodeURIComponent(this._agentId)}`,
      );
    } catch (e) {
      this._view.writeHtml(
        `<div class="msi-line err">! ${TextUtils.esc(e.message)}</div>`,
      );
      return;
    }
    if (this._view.isFirstRender && !rows.length) {
      this._view.renderEmptyOnce(
        `<div class="msi-entry dim">&mdash; no ${this._label} recorded yet &mdash;</div>`,
      );
      return;
    }
    for (const row of rows) {
      this._view.appendUnique(
        this._formatter.keyFor(row),
        this._formatter.formatRow(row),
      );
    }
  }
}
