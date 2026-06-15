import { TextUtils } from "../abstract/text-utils.js";

/**
 * RolFinanceReportsController — builds the Project Plans → ROL Finance →
 * Reports tabs. It fetches /api/rol-finance-reports, injects one sidebar tab
 * and one <section><iframe class="plan-frame"> per report, and on each iframe's
 * load reaches into the (same-origin) report document to hide every <section>
 * except the "Verified Transactions" card — the report.html files are
 * static/regenerated, so we never edit them, just collapse the view.
 *
 * Same-origin assumption: the iframe reach only works because reports are
 * served from this origin. If a report ever moves cross-origin,
 * `iframe.contentDocument` throws/returns null and the hide step silently
 * no-ops (preserved behaviour — it must not throw).
 *
 * The nav/views elements and the activate/select-tab actions are injected so
 * the page-specific navigation glue stays in the boot file and the controller
 * is unit-testable with a DOM double.
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
    this.reports = null;
  }

  /** Fetch the report list (once) and build its tabs/views; open the first. */
  async openReports() {
    if (!this.reports) {
      try {
        this.reports = await this._http.getJSON(this._endpoint);
        this.buildTabsAndViews(this.reports);
      } catch (e) {
        this._nav.querySelectorAll(".tab[data-report-key]").forEach((t) => {
          t.remove();
        });
        this._viewsContainer.innerHTML = `<section id="rol-finance-reports-error" class="view active"><p class="am-warn">Failed to load reports: ${TextUtils.esc(e.message)}</p></section>`;
        return;
      }
    }
    const first = this.reports[0];
    if (!first) return;
    const firstTab = this._nav.querySelector(
      `[data-report-key="${first.key}"]`,
    );
    if (firstTab) this._setActiveTab(firstTab);
    this.openReport(first.key);
  }

  /** Inject one tab + one view per report (red tab + placeholder if missing). */
  buildTabsAndViews(reports) {
    for (const r of reports) {
      const tab = this._doc.createElement("button");
      tab.type = "button";
      tab.className = `tab${r.exists ? "" : " report-missing"}`;
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

  openReport(key) {
    this._activateView(`rol-finance-report-${key}`);
  }
}
