// deep-link.js — URL entry points into a specific tab.
//
//   ?agent=<id>&view=thoughts|messages|tool-calls|chat-interface
//   ?view=rol-finance-reports  -> Project Plans > ROL Finance > Reports
//   ?view=terminal             -> Terminal tab
//
// Must run AFTER viewNav.resetForPageLoad(), or the reset sends the page
// straight back to Home.

// Views opened by clicking their own main-nav tab, so a deep link takes the
// exact path a user click does.
const MAIN_TAB_VIEWS = new Set(["terminal"]);

export function applyDeepLink({
  doc = document,
  nav,
  AM,
  RF,
  search = location.search,
}) {
  const q = new URLSearchParams(search);
  const agent = q.get("agent");
  const view = q.get("view");
  if (agent) {
    AM.openById(agent, view || "thoughts");
    return;
  }
  if (view === "rol-finance-reports") {
    nav.main.classList.add("hidden");
    nav.rolFinanceReports.classList.remove("hidden");
    RF.openReports().then(() => RF.refreshStatus());
    return;
  }
  if (MAIN_TAB_VIEWS.has(view)) {
    doc.querySelector(`[data-nav="main"][data-target="${view}"]`)?.click();
  }
}
