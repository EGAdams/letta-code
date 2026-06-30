import { TextUtils } from "../abstract/text-utils.js";
import { describePipelineStage } from "./document-pipeline-controller.js";

/**
 * RolFinanceReportsController — builds the Project Plans → ROL Finance →
 * Reports tabs. The reports are grouped by month/year: a row of "month tabs"
 * (January 2025, February 2025, …) is injected once, and selecting a month
 * fetches that month's report list (cached per month) and (re)builds one
 * report tab + one <section> per document below it.
 *
 * Each document section contains:
 *   1. A reprocess bar (button + inline status) so the user can re-run the
 *      full Mazda intake pipeline on the underlying source document at any time.
 *   2. An iframe loading the report.html, collapsed to the Verified Transactions
 *      card via showOnlyVerifiedTransactions on load.
 *
 * The controller polls GET /api/expense-stored-events every 15 s (when polling
 * is enabled by injecting setInterval / clearInterval). When Mazda stores a new
 * expense after a scan, she POSTs /api/expense-stored (STEP 8 in the scan
 * message); any open report iframe is reloaded so receipt markers auto-refresh.
 *
 * Programs to interfaces, not implementations:
 *   - HttpClient (http) — all network calls go through http.getJSON / postJSON.
 *   - Timer strategy (setInterval / clearInterval) — injected; null disables polling.
 *   - Document factory (doc) — all DOM creation goes through doc.createElement.
 *   - View callbacks (activateView, setActiveTab) — injected by the boot file.
 */
export class RolFinanceReportsController {
  constructor({
    http,
    nav,
    viewsContainer,
    doc = globalThis.document,
    activateView = () => {},
    setActiveTab = () => {},
    endpoint = "/api/rol-finance-reports",
    reprocessEndpoint = "/api/reprocess-report",
    expenseEventsEndpoint = "/api/expense-stored-events",
    months = [
      { key: "jan-2025", label: "January 2025" },
      { key: "feb-2025", label: "February 2025" },
    ],
    setInterval: _setInterval = null,
    clearInterval: _clearInterval = null,
  }) {
    if (!http || !nav || !viewsContainer) {
      throw new Error(
        "RolFinanceReportsController requires { http, nav, viewsContainer }",
      );
    }
    this._http = http;
    this._nav = nav;
    this._viewsContainer = viewsContainer;
    this._doc = doc;
    this._activateView = activateView;
    this._setActiveTab = setActiveTab;
    this._endpoint = endpoint;
    this._reprocessEndpoint = reprocessEndpoint;
    this._expenseEventsEndpoint = expenseEventsEndpoint;
    this._months = months;
    this._setInterval = _setInterval;
    this._clearInterval = _clearInterval;
    this._monthsBuilt = false;
    this._activeMonthKey = null;
    this._reportsByMonth = new Map();
    this.reports = null;
    this._pollTimer = null;
    this._lastEventTs = 0;
  }

  /** Inject the month tabs (once) and open the first month. */
  async openReports() {
    if (!this._monthsBuilt) {
      this.buildMonthTabs();
      this._monthsBuilt = true;
    }
    const first = this._months[0];
    if (first) await this.openMonth(first.key);
    this.startPolling();
  }

  /** Inject one month tab per configured month (once). */
  buildMonthTabs() {
    for (const m of this._months) {
      const tab = this._doc.createElement("button");
      tab.type = "button";
      tab.className = "tab month-tab";
      tab.dataset.monthKey = m.key;
      tab.textContent = m.label;
      this._nav.appendChild(tab);
    }
  }

  /**
   * Select a month: highlight its tab, fetch its report list (cached per
   * month key), and (re)build its document tabs/views.
   */
  async openMonth(monthKey) {
    const month = this._months.find((m) => m.key === monthKey);
    if (!month) return;
    this._activeMonthKey = monthKey;

    this._nav.querySelectorAll(".tab[data-month-key]").forEach((t) => {
      t.classList.toggle("active", t.dataset.monthKey === monthKey);
    });

    let reports = this._reportsByMonth.get(monthKey);
    if (!reports) {
      try {
        reports = await this._http.getJSON(
          `${this._endpoint}?month=${encodeURIComponent(monthKey)}`,
        );
        this._reportsByMonth.set(monthKey, reports);
      } catch (e) {
        this._nav.querySelectorAll(".tab[data-report-key]").forEach((t) => {
          t.remove();
        });
        this._viewsContainer.innerHTML = `<section id="rol-finance-reports-error" class="view active"><p class="am-warn">Failed to load reports: ${TextUtils.esc(e.message)}</p></section>`;
        return;
      }
    }
    this.reports = reports;

    this._nav.querySelectorAll(".tab[data-report-key]").forEach((t) => {
      t.remove();
    });
    this._viewsContainer.innerHTML = "";
    this.buildOverview(reports, month);
    this.buildTabsAndViews(reports);
    this.openOverview();
  }

  /** Map a report's status to a CSS class + human label for the overview row. */
  static statusInfo(status) {
    switch (status) {
      case "pass":
        return { cls: "rol-status-pass", label: "Finished" };
      case "review":
        return { cls: "rol-status-review", label: "In progress" };
      case "missing":
        return { cls: "rol-status-fail", label: "Not started" };
      case "fail":
        return { cls: "rol-status-fail", label: "Failed" };
      default:
        return null;
    }
  }

  /**
   * Build the month-level landing view: one color-coded row per document.
   * Skips reports with no `status` (e.g. the synthetic Receipt Only tab).
   */
  buildOverview(reports, month) {
    const view = this._doc.createElement("section");
    view.id = "rol-finance-reports-overview";
    view.className = "view";

    const rows = reports
      .map((r) => ({
        r,
        info: RolFinanceReportsController.statusInfo(r.status),
      }))
      .filter(({ info }) => info)
      .map(
        ({ r, info }) =>
          `<tr class="${info.cls}" data-report-key="${TextUtils.esc(r.key)}"><td>${TextUtils.esc(r.label)}</td><td>${TextUtils.esc(info.label)}</td></tr>`,
      )
      .join("");

    view.innerHTML = `
      <h2>${TextUtils.esc(month.label)} — Document Status</h2>
      <table class="rol-overview-table">
        <thead><tr><th>Document</th><th>Status</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>`;

    view.querySelectorAll("tr[data-report-key]").forEach((row) => {
      row.addEventListener("click", () =>
        this.selectReport(row.dataset.reportKey),
      );
    });

    this._viewsContainer.appendChild(view);
  }

  openOverview() {
    this._activateView("rol-finance-reports-overview");
  }

  /**
   * Inject one tab + one view per report.
   * Existing reports get a reprocess bar above the iframe.
   * Missing reports get a red tab + placeholder.
   */
  buildTabsAndViews(reports) {
    for (const r of reports) {
      const missing = !r.exists;
      const tab = this._doc.createElement("button");
      tab.type = "button";
      tab.className = `tab${missing ? " report-missing" : ""}`;
      tab.dataset.reportKey = r.key;
      tab.textContent = r.label;
      this._nav.appendChild(tab);

      const view = this._doc.createElement("section");
      view.id = `rol-finance-report-${r.key}`;
      view.className = "view";
      if (r.exists) {
        const bar = this.buildReprocessBar(r);
        view.appendChild(bar);
        // Keep the iframe in innerHTML so querySelectorAll on the view
        // can find it in the real DOM while the bar stays queryable via
        // the children tree (the FakeElement pattern this codebase uses).
        view.insertAdjacentHTML(
          "beforeend",
          `<iframe class="plan-frame" src="${TextUtils.esc(r.url)}"></iframe>`,
        );
        const iframe = view.querySelector("iframe");
        if (iframe) {
          iframe.addEventListener("load", () =>
            this.showOnlyVerifiedTransactions(iframe),
          );
        }
      } else {
        view.innerHTML = "<p>Missing report.html for this report.</p>";
      }
      this._viewsContainer.appendChild(view);
    }
  }

  /**
   * Build the reprocess action bar for one report. Returns a <div> containing
   * a "Reprocess Document" button and an inline status span. The button click
   * delegates to reprocessDocument (Command pattern over HttpClient).
   */
  buildReprocessBar(r) {
    const bar = this._doc.createElement("div");
    bar.className = "reprocess-bar";

    const btn = this._doc.createElement("button");
    btn.type = "button";
    btn.className = "reprocess-btn";
    btn.textContent = "Reprocess Document";

    const status = this._doc.createElement("span");
    status.className = "reprocess-status";

    bar.appendChild(btn);
    bar.appendChild(status);

    btn.addEventListener("click", () =>
      this.reprocessDocument(r.key, r.url, btn, status),
    );

    return bar;
  }

  /**
   * Re-run the full intake pipeline (facade + Mazda) for this report's source
   * document. Programs to HttpClient (postJSON) and renders the inline result
   * via renderReprocessResult (a pure view method).
   */
  async reprocessDocument(_key, url, buttonEl, statusEl) {
    if (buttonEl) buttonEl.disabled = true;
    if (statusEl) statusEl.textContent = "Reprocessing…";
    try {
      const result = await this._http.postJSON(this._reprocessEndpoint, {
        report_url: url,
      });
      this.renderReprocessResult(statusEl, result);
    } catch (e) {
      if (statusEl) statusEl.textContent = `Error: ${TextUtils.esc(e.message)}`;
    } finally {
      if (buttonEl) buttonEl.disabled = false;
    }
  }

  /**
   * Pure view update: render a pipeline result into the status span.
   * Reuses describePipelineStage from DocumentPipelineController so the
   * stage-formatting logic is not duplicated.
   */
  renderReprocessResult(statusEl, result) {
    if (!statusEl) return;
    if (!result.ok && result.error) {
      statusEl.textContent = `Failed: ${result.error}`;
      return;
    }
    const stages = (result.stages || []).map(describePipelineStage);
    const parts = stages.map((s) =>
      s.summary
        ? `${s.name}: ${s.status} (${s.summary})`
        : `${s.name}: ${s.status}`,
    );
    statusEl.textContent =
      parts.join(" · ") || (result.ok ? "Dispatched to Mazda" : "Error");
  }

  /**
   * Reach into a same-origin report iframe and hide every <section> except
   * the one containing #verified-transactions.
   */
  showOnlyVerifiedTransactions(iframe) {
    let doc;
    try {
      doc = iframe.contentDocument;
    } catch {
      return;
    }
    if (!doc) return;
    const vt = doc.getElementById("verified-transactions");
    if (!vt) return;
    const keep = vt.closest("section");
    if (!keep || !keep.parentElement) return;
    for (const child of keep.parentElement.children) {
      if (child !== keep && child.tagName === "SECTION") {
        child.style.display = "none";
      }
    }
  }

  /** Highlight a document tab (within the current month) and open its view. */
  selectReport(key) {
    const tab = this._nav.querySelector(`[data-report-key="${key}"]`);
    if (tab) {
      this._nav.querySelectorAll(".tab[data-report-key]").forEach((t) => {
        t.classList.toggle("active", t === tab);
      });
    }
    this.openReport(key);
  }

  openReport(key) {
    this._activateView(`rol-finance-report-${key}`);
  }

  // ── Expense-stored polling ─────────────────────────────────────────────────

  /**
   * Start polling /api/expense-stored-events every 15 s. No-op if setInterval
   * was not injected (polling is disabled by default in tests).
   * Idempotent: calling more than once does not start additional timers.
   */
  startPolling() {
    if (!this._setInterval || this._pollTimer != null) return;
    this._pollTimer = this._setInterval(
      () => this._pollStoredExpenses(),
      15_000,
    );
  }

  /** Stop the expense-stored poll (e.g. on teardown). */
  stopPolling() {
    if (this._pollTimer == null) return;
    this._clearInterval(this._pollTimer);
    this._pollTimer = null;
  }

  async _pollStoredExpenses() {
    try {
      const events = await this._http.getJSON(
        `${this._expenseEventsEndpoint}?since=${this._lastEventTs}`,
      );
      if (Array.isArray(events) && events.length > 0) {
        this._lastEventTs = Math.max(...events.map((e) => e.stored_at));
        this._reloadOpenIframes();
      }
    } catch {
      // Network error — silently ignore; retry on the next tick.
    }
  }

  /**
   * Reload any open (accessible) report iframes so the receipt-present markers
   * re-run after Mazda stores a new expense + receipt.
   */
  _reloadOpenIframes() {
    this._viewsContainer
      .querySelectorAll("iframe.plan-frame")
      .forEach((iframe) => {
        let accessible = false;
        try {
          accessible = iframe.contentDocument != null;
        } catch {
          /* cross-origin — skip */
        }
        if (accessible) {
          // biome-ignore lint/correctness/noSelfAssign: triggers iframe reload
          iframe.src = iframe.src;
        }
      });
  }
}
