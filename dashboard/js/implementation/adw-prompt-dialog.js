/**
 * AdwPromptDialog — polls /api/adw-prompt (5s) and raises a Yes/No modal when
 * an agent_blocks ADW is waiting on a decision only a person should make
 * (pc_doctor's "Run WSL Compact?" is the first).
 *
 * The dashboard only carries the answer: Yes/No POSTs /api/adw-prompt-answer
 * and the ADW that asked reads it back and acts. So there is no local-only
 * dismiss — closing the modal without answering would leave the ADW waiting
 * for nothing. A question the ADW withdraws, or that expires, simply stops
 * coming back from the poll and the modal hides itself.
 *
 * Same shape as IntakeHaltAlert (HttpClient/doc/setInterval injected) so it is
 * unit-testable without a browser.
 */
export class AdwPromptDialog {
  constructor({
    http,
    doc = globalThis.document,
    modalId = "adw-prompt-modal",
    titleId = "adw-prompt-title",
    questionId = "adw-prompt-question",
    detailId = "adw-prompt-detail",
    yesId = "adw-prompt-yes",
    noId = "adw-prompt-no",
    intervalMs = 5000,
    setInterval: setIntervalFn = globalThis.setInterval?.bind(globalThis),
  } = {}) {
    if (!http) throw new Error("AdwPromptDialog requires an HttpClient");
    this._http = http;
    this._doc = doc;
    this._ids = { modalId, titleId, questionId, detailId, yesId, noId };
    this._intervalMs = intervalMs;
    this._setInterval = setIntervalFn;
    this._promptId = null;
    this._answering = false;
  }

  _el(id) {
    return this._doc.getElementById(id);
  }

  start() {
    this._el(this._ids.yesId)?.addEventListener("click", () =>
      this.answer("yes"),
    );
    this._el(this._ids.noId)?.addEventListener("click", () =>
      this.answer("no"),
    );
    this.poll();
    if (this._setInterval)
      this._setInterval(() => this.poll(), this._intervalMs);
  }

  _hide() {
    this._promptId = null;
    this._el(this._ids.modalId)?.classList.add("hidden");
  }

  async answer(answer) {
    const id = this._promptId;
    if (!id || this._answering) return;
    this._answering = true;
    try {
      await this._http.postJSON("/api/adw-prompt-answer", { id, answer });
    } catch {
      // Already answered elsewhere, withdrawn, or expired: the next poll shows
      // whatever is really open, so hiding here can't lose a question.
    } finally {
      this._answering = false;
    }
    this._hide();
  }

  async poll() {
    const modal = this._el(this._ids.modalId);
    if (!modal || this._answering) return;
    let payload;
    try {
      payload = await this._http.getJSON("/api/adw-prompt");
    } catch {
      return;
    }
    const prompt = payload?.active ? payload.prompt : null;
    if (!prompt?.id) {
      this._hide();
      return;
    }
    this._promptId = prompt.id;
    const title = this._el(this._ids.titleId);
    if (title) title.textContent = AdwPromptDialog.titleFor(prompt.source);
    const question = this._el(this._ids.questionId);
    if (question) question.textContent = prompt.question || "";
    const detail = this._el(this._ids.detailId);
    if (detail) detail.textContent = prompt.detail || "";
    modal.classList.remove("hidden");
  }

  /** "adw_interface_pc_doctor" -> "PC Doctor": the asking ADW, readably. */
  static titleFor(source) {
    const name = String(source || "")
      .replace(/^adw_interface_/, "")
      .replace(/^adw_/, "")
      .replace(/\.py$/, "");
    if (!name) return "ADW";
    return name
      .split(/[_-]+/)
      .filter(Boolean)
      .map((w) =>
        w.length <= 2 ? w.toUpperCase() : w[0].toUpperCase() + w.slice(1),
      )
      .join(" ");
  }
}
