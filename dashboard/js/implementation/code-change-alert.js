/**
 * CodeChangeAlert — polls /api/code-status (15s) and, when the dashboard's
 * own source has changed, blinks the Agents tab and shows a restart modal.
 * "Yes" POSTs a dashboard restart; "No" remembers the dismissed change
 * signature so the same change doesn't keep re-prompting. When the change
 * clears, the blink/modal are cleared and the dismissal is forgotten.
 *
 * Reproduces the inline codeChangeAlert IIFE. The element ids, HttpClient and
 * interval scheduler are injected so the loop is unit-testable. Fetch errors
 * are swallowed (a transient blip never tears down the loop).
 */
export class CodeChangeAlert {
  constructor({
    http,
    doc = globalThis.document,
    tabId = "btn-agents-home",
    modalId = "code-change-modal",
    yesId = "code-change-yes",
    noId = "code-change-no",
    intervalMs = 15000,
    setInterval: setIntervalFn = globalThis.setInterval?.bind(globalThis),
  } = {}) {
    if (!http) throw new Error("CodeChangeAlert requires an HttpClient");
    this._http = http;
    this._doc = doc;
    this._tabId = tabId;
    this._modalId = modalId;
    this._yesId = yesId;
    this._noId = noId;
    this._intervalMs = intervalMs;
    this._setInterval = setIntervalFn;
    this._dismissedSignature = "";
    this._lastSignature = "";
  }

  _el(id) {
    return this._doc.getElementById(id);
  }

  /** Wire the modal buttons, run one immediate poll, then arm the interval. */
  start() {
    const tab = this._el(this._tabId);
    const modal = this._el(this._modalId);
    const yes = this._el(this._yesId);
    const no = this._el(this._noId);
    if (!tab || !modal || !yes || !no) return;

    yes.addEventListener("click", async () => {
      modal.classList.add("hidden");
      tab.classList.remove("tab-alert");
      try {
        await this._http.postJSON("/api/server-action", {
          server: "dashboard",
          action: "restart",
        });
      } catch {
        /* the server is restarting — the response may never arrive */
      }
    });

    no.addEventListener("click", () => {
      modal.classList.add("hidden");
      tab.classList.remove("tab-alert");
      this._dismissedSignature = this._lastSignature;
    });

    this.poll();
    if (this._setInterval)
      this._setInterval(() => this.poll(), this._intervalMs);
  }

  async poll() {
    const tab = this._el(this._tabId);
    const modal = this._el(this._modalId);
    if (!tab || !modal) return;
    let status;
    try {
      status = await this._http.getJSON("/api/code-status");
    } catch {
      return;
    }
    this._lastSignature = (status.changed_files || []).join(",");
    if (
      status.changed &&
      this._lastSignature &&
      this._lastSignature !== this._dismissedSignature
    ) {
      tab.classList.add("tab-alert");
      modal.classList.remove("hidden");
    } else if (!status.changed) {
      tab.classList.remove("tab-alert");
      modal.classList.add("hidden");
      this._dismissedSignature = "";
    }
  }
}
