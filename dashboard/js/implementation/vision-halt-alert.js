/**
 * VisionHaltAlert — polls /api/server-health (20s) for the 'document-vision'
 * entry (classify_scan.py's Gemini -> ChatGPT-OAuth/Codex-CLI -> OpenAI-key
 * fallback chain). When it reports 'down' (all 3 tiers unavailable, the same
 * condition process_scanned_document() gates on server-side to skip
 * dispatching Mazda), shows a full-screen dimmed modal and marks both scanner
 * nav tabs (Window/Freezer) red — scanning still works mechanically but is
 * pointless with nothing able to read the result. Clears automatically once
 * a tier recovers. "Retry Now" just forces an immediate poll; "Dismiss" hides
 * the modal without altering server state (the red tabs stay until it's
 * actually fixed).
 *
 * Reuses the CodeChangeAlert shape (HttpClient/doc/setInterval injected) so
 * it's unit-testable without a browser.
 */
export class VisionHaltAlert {
  constructor({
    http,
    doc = globalThis.document,
    modalId = "vision-halted-modal",
    detailId = "vision-halted-detail",
    retryId = "vision-halted-retry",
    dismissId = "vision-halted-dismiss",
    scannerTabSelector = '[data-target="scanners-window"], [data-target="scanners-freezer"]',
    intervalMs = 20000,
    setInterval: setIntervalFn = globalThis.setInterval?.bind(globalThis),
  } = {}) {
    if (!http) throw new Error("VisionHaltAlert requires an HttpClient");
    this._http = http;
    this._doc = doc;
    this._modalId = modalId;
    this._detailId = detailId;
    this._retryId = retryId;
    this._dismissId = dismissId;
    this._scannerTabSelector = scannerTabSelector;
    this._intervalMs = intervalMs;
    this._setInterval = setIntervalFn;
    this._dismissed = false;
  }

  _el(id) {
    return this._doc.getElementById(id);
  }

  start() {
    const modal = this._el(this._modalId);
    const retry = this._el(this._retryId);
    const dismiss = this._el(this._dismissId);
    if (!modal) return;

    retry?.addEventListener("click", () => this.poll());
    dismiss?.addEventListener("click", () => {
      this._dismissed = true;
      modal.classList.add("hidden");
    });

    this.poll();
    if (this._setInterval)
      this._setInterval(() => this.poll(), this._intervalMs);
  }

  async poll() {
    const modal = this._el(this._modalId);
    const detail = this._el(this._detailId);
    if (!modal) return;
    let payload;
    try {
      payload = await this._http.getJSON("/api/server-health");
    } catch {
      return;
    }
    const entry = (payload?.servers || []).find(
      (s) => s.key === "document-vision",
    );
    const tabs = this._doc.querySelectorAll(this._scannerTabSelector);
    if (!entry || entry.status !== "down") {
      for (const tab of tabs) tab.classList.remove("server-down");
      modal.classList.add("hidden");
      this._dismissed = false;
      return;
    }
    for (const tab of tabs) tab.classList.add("server-down");
    if (detail) detail.textContent = entry.name || "";
    if (!this._dismissed) modal.classList.remove("hidden");
  }
}
