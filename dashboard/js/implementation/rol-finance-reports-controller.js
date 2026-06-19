import { TextUtils } from "../abstract/text-utils.js";

/**
 * RolFinanceReportsController — builds the Project Plans → ROL Finance →
 * Reports tabs. The reports are grouped by month/year: a row of "month tabs"
 * (January 2025, February 2025, …) is injected once, and selecting a month
 * fetches that month's report list (cached per month) and (re)builds one
 * report tab + one <section><iframe class="plan-frame"> per document below it.
 *
 * Each document's existence is resolved by the backend against that month's
 * own directory, so the same document key (e.g. "platinum-year") can already
 * have a real report.html for one month while still being missing for
 * another — there is no month-wide on/off switch, just per-document
 * `exists`: existing reports get a normal tab + iframe view (collapsed to the
 * Verified Transactions card), missing ones get a red tab + placeholder.
 *
 * On each iframe's load we reach into the (same-origin) report document to hide
 * every <section> except the "Verified Transactions" card — the report.html
 * files are static/regenerated, so we never edit them, just collapse the view.
 *
 * Same-origin assumption: the iframe reach only works because reports are
 * served from this origin. If a report ever moves cross-origin,
 * `iframe.contentDocument` throws/returns null and the hide step silently
 * no-ops (preserved behaviour — it must not throw).
 *
 * The nav/views elements and the activate action are injected so the
 * page-specific navigation glue stays in the boot file and the controller is
 * unit-testable with a DOM double.
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
    months = [
      { key: "jan-2025", label: "January 2025" },
      { key: "feb-2025", label: "February 2025" },
    ],
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
    this._months = months;
    this._monthsBuilt = false;
    this._activeMonthKey = null;
    this._reportsByMonth = new Map();
    this.reports = null;
  }

  /** Inject the month tabs (once) and open the first month. */
  async openReports() {
    if (!this._monthsBuilt) {
      this.buildMonthTabs();
      this._monthsBuilt = true;
    }
    const first = this._months[0];
    if (first) await this.openMonth(first.key);
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

    // Highlight the active month tab (kept independent of the report-tab
    // active state so both the month and the open document stay highlighted).
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

    // Drop the previous month's document tabs + views, then rebuild.
    this._nav.querySelectorAll(".tab[data-report-key]").forEach((t) => {
      t.remove();
    });
    this._viewsContainer.innerHTML = "";
    this.buildTabsAndViews(reports);

    const first = reports[0];
    if (!first) return;
    this.selectReport(first.key);
  }

  /**
   * Inject one tab + one view per report: existing → iframe view; missing →
   * red tab + "Missing report.html" placeholder.
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
        view.innerHTML = `<iframe class="plan-frame" src="${TextUtils.esc(r.url)}"></iframe>`;
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
   * Reach into a same-origin report iframe and hide every <section> except the
   * one containing #verified-transactions (the category picker stays intact).
   */
  showOnlyVerifiedTransactions(iframe) {
    let doc;
    try {
      doc = iframe.contentDocument;
    } catch {
      return; // cross-origin — silently no-op
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
}
