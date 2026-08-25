// rol-finance.js — the RF controller: one tab per report directory under
// ~/rol_finances/readable_documents/bank_statements/<month>/.
//
// Tabs + views are built once from /api/rol-finance-reports, which reports
// whether each report.html exists on disk. Missing reports get a red tab and a
// placeholder view instead of an iframe, so the UI never silently fails.

import { RolFinanceReportsController } from "../implementation/index.js";

export function createRolFinance({ doc = document, http, nav, viewNav }) {
  const RF = new RolFinanceReportsController({
    http,
    nav: nav.rolFinanceReports,
    viewsContainer: doc.getElementById("rol-finance-reports-views"),
    activateView: viewNav.activateView,
    setActiveTab: (tab) =>
      viewNav.setActive(nav.rolFinanceReports, ".tab", tab),
    setInterval: globalThis.setInterval.bind(globalThis),
    clearInterval: globalThis.clearInterval.bind(globalThis),
  });

  // Poll the live month-status + recently-scanned signals, but only while the
  // ROL Finance Reports view is actually on screen (the endpoints hit the
  // finance DB, so there's no point polling when it's hidden).
  // `offsetParent === null` catches every way it can be off screen — its own
  // `hidden` class (Back button) AND a display:none ancestor when the user
  // switches top-level sidebar sections (which does NOT toggle this sub-nav's
  // own class). A human categorizing a row flips the month tab green + drops
  // the item from New Records on the next tick.
  RF.statusPollTimer = setInterval(() => {
    if (nav.rolFinanceReports.offsetParent !== null) RF.refreshStatus();
  }, 10000);

  return RF;
}
