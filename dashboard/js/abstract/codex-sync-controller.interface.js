import {
  assertCodexSyncStatus,
  fmtRemaining,
  renderCodexSyncPanel,
} from "./codex-sync-status.js";
import { abstractMethod } from "./not-implemented.js";

const SYNC_SOURCE_BUTTONS = {
  r46: { id: "cs-swap-r46-btn", idle: "Sync from R46 (mom)", busy: "Syncing…" },
  w11: {
    id: "cs-swap-w11-btn",
    idle: "Copy from W11 (mine)",
    busy: "Copying…",
  },
};

/**
 * CodexSyncController — Template Method.
 *
 * Polling/tick/refresh/swap sequencing is identical regardless of runtime;
 * the one varying primitive is "how do I get a DOM element by id" — a real
 * browser Document in production, a fake in tests. Splitting on `_getElement`
 * (rather than passing `document` straight through) lets every other method
 * here run and be asserted against in plain Node, no jsdom required.
 *
 * The HttpClient is injected (constructor), matching every other
 * poller/controller in this codebase (see http-client.interface.js).
 */
export class CodexSyncController {
  /**
   * @param {{ http: import("./http-client.interface.js").HttpClient,
   *           setInterval?: typeof globalThis.setInterval }} deps
   */
  constructor({
    http,
    setInterval: setIntervalFn = globalThis.setInterval?.bind(globalThis),
  } = {}) {
    if (!http || typeof http.getJSON !== "function") {
      throw new Error("CodexSyncController requires { http }");
    }
    this._http = http;
    this._setInterval = setIntervalFn;
    this._status = null;
    this._tickTimer = null;
    this._containerId = null;
  }

  /**
   * Abstract primitive: resolve an element id to a DOM node (or null).
   * Override in js/implementation/.
   * @param {string} _id
   */
  _getElement(_id) {
    return abstractMethod("_getElement");
  }

  /** Mount into a container id; starts the 1s countdown ticker. */
  mount(containerId) {
    this._containerId = containerId;
    void this.refresh();
    if (this._setInterval && !this._tickTimer) {
      this._tickTimer = this._setInterval(() => this._tick(), 1000);
    }
  }

  /** Re-fetch status from the server and re-render. */
  async refresh() {
    try {
      const raw = await this._http.getJSON("/api/codex-sync-status");
      this._status = assertCodexSyncStatus(raw);
    } catch (e) {
      this._status = { error: e.message };
    }
    this._render();
  }

  /**
   * Trigger a manual sync from the given source ("r46" pulls mom's account
   * over SSH, same as the timer; "w11" copies EG's own primary account into
   * the fallback slot — a deliberate, explicit collapse of the dual-account
   * failover). Resets the countdown on success. Works regardless of whether
   * the automatic timer is enabled or disabled.
   * @param {"r46"|"w11"} source
   */
  async swapNow(source) {
    if (!SYNC_SOURCE_BUTTONS[source]) {
      throw new Error(`swapNow: unknown source ${source}`);
    }
    this._setSwapButtonsBusy(true);
    try {
      const raw = await this._http.postJSON("/api/codex-sync-now", { source });
      this._status = assertCodexSyncStatus(raw);
    } catch (e) {
      this._status = {
        ...this._status,
        ran: true,
        ok: false,
        output: e.message,
        source,
      };
    }
    this._render(); // replaces the button markup, clearing the busy state
  }

  /**
   * Flip the automatic 4h pull on/off (systemd timer enable/disable).
   * Toggles the panel body's greyed-out state and the toolbar button's
   * label via the next render, driven entirely by the server's
   * `sync_enabled` in the response — no local guessing.
   */
  async toggleSync() {
    const wantEnabled = !(this._status?.sync_enabled ?? true);
    const btn = this._getElement("cs-toggle-sync-btn");
    if (btn) {
      btn.disabled = true;
      btn.textContent = "Working…";
    }
    try {
      const raw = await this._http.postJSON("/api/codex-sync-toggle", {
        enabled: wantEnabled,
      });
      this._status = assertCodexSyncStatus(raw);
    } catch (e) {
      this._status = { ...this._status, toggle_error: e.message };
    }
    this._render();
  }

  /** One second of local countdown; re-fetches once the deadline passes. */
  _tick() {
    if (!this._status || this._status.seconds_remaining == null) return;
    this._status.seconds_remaining = Math.max(
      0,
      this._status.seconds_remaining - 1,
    );
    const label = this._getElement("cs-countdown-label");
    const bar = this._getElement("cs-swap-bar");
    if (label) label.textContent = fmtRemaining(this._status.seconds_remaining);
    if (bar) {
      const interval = this._status.interval_seconds || 1;
      const pct = Math.max(
        0,
        Math.min(100, (this._status.seconds_remaining / interval) * 100),
      );
      bar.style.width = `${pct}%`;
    }
    if (this._status.seconds_remaining <= 0) void this.refresh();
  }

  _setSwapButtonsBusy(busy) {
    for (const [, spec] of Object.entries(SYNC_SOURCE_BUTTONS)) {
      const btn = this._getElement(spec.id);
      if (!btn) continue;
      btn.disabled = busy;
      btn.textContent = busy ? spec.busy : spec.idle;
    }
  }

  /** Re-render the panel HTML and rewire both source-button click handlers. */
  _render() {
    const container = this._getElement(this._containerId);
    if (!container) return;
    container.innerHTML = renderCodexSyncPanel(this._status);
    const label = this._getElement("cs-countdown-label");
    if (label && this._status?.seconds_remaining != null) {
      label.textContent = fmtRemaining(this._status.seconds_remaining);
    }
    for (const [source, spec] of Object.entries(SYNC_SOURCE_BUTTONS)) {
      const btn = this._getElement(spec.id);
      if (btn) btn.addEventListener("click", () => void this.swapNow(source));
    }
    const toggleBtn = this._getElement("cs-toggle-sync-btn");
    if (toggleBtn)
      toggleBtn.addEventListener("click", () => void this.toggleSync());
  }
}
