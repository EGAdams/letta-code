/**
 * Keeps Model Stats source tabs colored even when that view has never been
 * opened, and rolls the worst source status up through its parent tabs.
 */
export class ModelStatsHealthMonitor {
  constructor({
    http,
    doc = globalThis.document,
    onStatus = () => {},
    intervalMs = 120000,
    setInterval: setIntervalFn = globalThis.setInterval?.bind(globalThis),
  } = {}) {
    if (!http)
      throw new Error("ModelStatsHealthMonitor requires an HttpClient");
    this._http = http;
    this._doc = doc;
    this._onStatus = onStatus;
    this._intervalMs = intervalMs;
    this._setInterval = setIntervalFn;
    this._timer = null;
  }

  start() {
    void this.poll();
    if (this._setInterval && !this._timer) {
      this._timer = this._setInterval(() => void this.poll(), this._intervalMs);
    }
  }

  async poll() {
    const nav = this._doc.getElementById("nav-model-stats");
    if (!nav) return;
    const tabs = [...nav.querySelectorAll("[data-source]")];
    const statuses = await Promise.all(
      tabs.map(async (tab) => {
        try {
          const result = await this._http.getJSON(
            `/api/model-stats?source=${encodeURIComponent(tab.dataset.source)}`,
          );
          const status = ["down", "concern"].includes(result.status)
            ? result.status
            : "up";
          this._setSourceState(tab, status, result.muted);
          return status;
        } catch {
          // Preserve the last known state during a transient request failure.
          return null;
        }
      }),
    );

    const known = statuses.filter(Boolean);
    const worst = known.includes("down")
      ? "down"
      : known.includes("concern")
        ? "concern"
        : known.length
          ? "up"
          : null;
    if (worst) this._setAggregateState(worst);
    if (worst) this._onStatus(worst);
  }

  _setSourceState(tab, status, muted = false) {
    tab.classList.remove(
      "server-up",
      "server-concern",
      "server-down",
      "tab-alert",
      "tab-alert-red",
      "muted",
    );
    tab.classList.add(`server-${status}`);
    tab.classList.toggle("tab-alert", status === "concern");
    tab.classList.toggle("tab-alert-red", status === "down");
    tab.classList.toggle("muted", muted);
  }

  _setAggregateState(status) {
    for (const id of ["btn-model-stats", "btn-system-status"]) {
      const tab = this._doc.getElementById(id);
      if (!tab) continue;
      tab.classList.remove("server-up", "server-concern", "server-down");
      tab.classList.add(`server-${status}`);
      tab.classList.toggle("tab-alert", status === "concern");
      tab.classList.toggle("tab-alert-red", status === "down");
    }
  }
}
