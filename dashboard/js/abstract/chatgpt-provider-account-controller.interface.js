import {
  assertChatGptProviderAccountStatus,
  renderChatGptProviderAccountPanel,
} from "./chatgpt-provider-account-status.js";
import { abstractMethod } from "./not-implemented.js";

/**
 * ChatGptProviderAccountController — Template Method.
 *
 * Controls which ChatGPT Plus account's token is installed as the LIVE
 * chatgpt-plus-pro provider row (what Mazda's whole agent fleet actually
 * spends against), as distinct from CodexSyncController (js/abstract/
 * codex-sync-controller.interface.js), which only refills a local
 * vision-fallback cache file. Splits on `_getElement` exactly like that
 * controller so refresh/set sequencing can be exercised in plain Node.
 */
export class ChatGptProviderAccountController {
  /**
   * @param {{ http: import("./http-client.interface.js").HttpClient }} deps
   */
  constructor({
    http,
    setInterval = globalThis.setInterval?.bind(globalThis),
  } = {}) {
    if (!http || typeof http.getJSON !== "function") {
      throw new Error("ChatGptProviderAccountController requires { http }");
    }
    this._http = http;
    this._status = null;
    this._containerId = null;
    this._setInterval = setInterval;
    this._pollTimer = null;
    this._dismissedIncident = null;
  }

  /**
   * Abstract primitive: resolve an element id to a DOM node (or null).
   * Override in js/implementation/.
   * @param {string} _id
   */
  _getElement(_id) {
    return abstractMethod("_getElement");
  }

  /** Mount into a container id. */
  mount(containerId) {
    this._containerId = containerId;
    this._wireSyncDialog();
    void this.refresh();
    if (!this._pollTimer && this._setInterval) {
      this._pollTimer = this._setInterval(() => void this.refresh(), 60000);
    }
  }

  /** Re-fetch status from the server and re-render. */
  async refresh() {
    try {
      const raw = await this._http.getJSON(
        "/api/chatgpt-provider-account-status",
      );
      this._status = assertChatGptProviderAccountStatus(raw);
    } catch (e) {
      this._status = { error: e.message };
    }
    this._render();
    this._updateSyncDialog();
  }

  /**
   * Install `source`'s account as the live provider row.
   * @param {string} source
   */
  async setAccount(source) {
    this._setButtonsBusy(true);
    try {
      const raw = await this._http.postJSON("/api/chatgpt-provider-account", {
        source,
      });
      this._status = assertChatGptProviderAccountStatus(raw);
    } catch (e) {
      this._status = {
        ...this._status,
        ran: true,
        ok: false,
        text: e.message,
        source,
      };
    }
    this._render(); // replaces the button markup, clearing the busy state
    this._updateSyncDialog();
  }

  _wireSyncDialog() {
    this._getElement("provider-token-sync-yes")?.addEventListener(
      "click",
      () => {
        this._hideSyncDialog();
        void this.setAccount("w11");
      },
    );
    this._getElement("provider-token-sync-no")?.addEventListener(
      "click",
      () => {
        this._dismissedIncident = this._status?.incident_id ?? "unknown";
        this._hideSyncDialog();
      },
    );
  }

  _updateSyncDialog() {
    const modal = this._getElement("provider-token-sync-modal");
    if (!modal?.classList) return;
    const incident = this._status?.incident_id ?? "unknown";
    const shouldShow =
      this._status?.sync_recommended && incident !== this._dismissedIncident;
    modal.classList.toggle("hidden", !shouldShow);
  }

  _hideSyncDialog() {
    this._getElement("provider-token-sync-modal")?.classList?.add("hidden");
  }

  _setButtonsBusy(busy) {
    for (const opt of this._status?.sources ?? []) {
      const btn = this._getElement(`cgpa-set-${opt.key}-btn`);
      if (!btn) continue;
      btn.disabled = busy;
      if (busy) btn.textContent = "Working…";
    }
  }

  /** Re-render the panel HTML and rewire each account-button click handler. */
  _render() {
    const container = this._getElement(this._containerId);
    if (!container) return;
    container.innerHTML = renderChatGptProviderAccountPanel(this._status);
    for (const opt of this._status?.sources ?? []) {
      const btn = this._getElement(`cgpa-set-${opt.key}-btn`);
      if (btn)
        btn.addEventListener("click", () => void this.setAccount(opt.key));
    }
  }
}
