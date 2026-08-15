/**
 * IntakeHaltAlert — polls /api/intake-halt (15s) and raises a full-screen
 * "cannot continue" modal when the receipt/statement intake pipeline has HALTED
 * on an unexpected fault (rol_finances' fail-loud boundary — a crashed
 * counterpart lookup that would otherwise have silently inserted a duplicate
 * expense).
 *
 * Unlike VisionHaltAlert (whose condition self-clears when a provider tier
 * recovers), an intake halt is a discrete code fault that does NOT recover on
 * its own. So "Acknowledge" POSTs /api/intake-halt-ack to clear it server-side,
 * rather than a local-only dismiss — the alert must keep reappearing until a
 * human actually sees it. Reuses the VisionHaltAlert shape (HttpClient/doc/
 * setInterval injected) so it's unit-testable without a browser.
 */
export class IntakeHaltAlert {
  constructor({
    http,
    doc = globalThis.document,
    modalId = "intake-halted-modal",
    detailId = "intake-halted-detail",
    ackId = "intake-halted-ack",
    intervalMs = 15000,
    setInterval: setIntervalFn = globalThis.setInterval?.bind(globalThis),
  } = {}) {
    if (!http) throw new Error("IntakeHaltAlert requires an HttpClient");
    this._http = http;
    this._doc = doc;
    this._modalId = modalId;
    this._detailId = detailId;
    this._ackId = ackId;
    this._intervalMs = intervalMs;
    this._setInterval = setIntervalFn;
  }

  _el(id) {
    return this._doc.getElementById(id);
  }

  start() {
    const ack = this._el(this._ackId);
    ack?.addEventListener("click", () => this.acknowledge());
    this.poll();
    if (this._setInterval)
      this._setInterval(() => this.poll(), this._intervalMs);
  }

  async acknowledge() {
    try {
      await this._http.postJSON("/api/intake-halt-ack", {});
    } catch {
      // Best-effort — hide locally regardless so a down backend can't trap
      // the operator behind the modal; the next poll re-checks real state.
    }
    this._el(this._modalId)?.classList.add("hidden");
  }

  async poll() {
    const modal = this._el(this._modalId);
    const detail = this._el(this._detailId);
    if (!modal) return;
    let payload;
    try {
      payload = await this._http.getJSON("/api/intake-halt");
    } catch {
      return;
    }
    if (!payload?.active) {
      modal.classList.add("hidden");
      return;
    }
    const event = payload.event || {};
    if (detail) {
      const step = event.step || "unknown step";
      const type = event.exception_type ? `${event.exception_type}: ` : "";
      const doc = event.document_path
        ? `\nDocument: ${event.document_path}`
        : "";
      detail.textContent = `Step: ${step}\n${type}${event.cause || ""}${doc}`;
    }
    modal.classList.remove("hidden");
  }
}
