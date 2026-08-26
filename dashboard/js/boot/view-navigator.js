// view-navigator.js — the single choke point every tab switch runs through.
//
// activateView() is where the statement-review dialog is told its visibility
// may need to change: without it the modal (statement-review-overlay in
// dashboard.css) stays parked over whichever tab the user switches to next,
// silently swallowing every click there (e.g. Agents tab's Start Listening).

export function createViewNavigator({ doc = document, nav }) {
  // Assigned once the statement-review dialog is constructed (it is built far
  // later than this navigator, and needs the navigator itself).
  let statementReviewDialog = null;

  // The src each marked frame was authored with, captured before we ever
  // append a cache-buster, so repeated shows rebuild from the original URL
  // instead of stacking _t= params onto each other.
  const authoredSrc = new WeakMap();

  function clearActive(navEl, selector) {
    if (!navEl) return;
    navEl.querySelectorAll(selector).forEach((el) => {
      el.classList.remove("active");
    });
  }

  // A plan iframe is fetched once, when the dashboard page loads, and a tab
  // switch only toggles a CSS class -- so a dashboard left open all day keeps
  // showing whichever revision of a plan it pulled at load time, long after an
  // agent has rewritten and redeployed that plan. This is not hypothetical: it
  // is how the Dashboard Refactor plan appeared unchanged after a verified
  // deploy. Frames marked data-refresh-on-show re-fetch each time their tab is
  // opened, including the first time (by then the page load may be hours old).
  //
  // The _t= param is for the proxy sitting in front of the live box; the
  // dashboard's own server already sends no-store.
  function refreshFramesOnShow(view) {
    if (!view) return;
    for (const frame of view.querySelectorAll(
      ".plan-frame[data-refresh-on-show]",
    )) {
      if (!authoredSrc.has(frame)) {
        if (!frame.src) continue;
        authoredSrc.set(frame, frame.src);
      }
      const base = authoredSrc.get(frame);
      frame.src = `${base}${base.includes("?") ? "&" : "?"}_t=${Date.now()}`;
    }
  }

  function activateView(id, fallbackId = "home") {
    const next = doc.getElementById(id) ? id : fallbackId;
    doc.querySelectorAll(".view").forEach((v) => {
      v.classList.remove("active");
    });
    const view = doc.getElementById(next);
    if (view) view.classList.add("active");
    // Iframe-based views (Project Plans, ROL Finance Reports) should fill all
    // available width instead of being capped/padded like text views —
    // otherwise the report column is too skinny, especially on Android. Detect
    // them by the presence of a full-bleed frame.
    const isFullbleed = view && view.querySelector(".plan-frame") !== null;
    if (nav.mainContent)
      nav.mainContent.classList.toggle("fullbleed", !!isFullbleed);
    // New Records panel lives outside the .view hierarchy (sibling of
    // #rol-finance-reports-views); show it only when a ROL Finance view is
    // active.
    const recentScansPanel = doc.getElementById("rol-finance-recent-scans");
    if (recentScansPanel)
      recentScansPanel.hidden = !next.startsWith("rol-finance");
    refreshFramesOnShow(view);
    statementReviewDialog?.syncVisibility?.();
  }

  function setActive(navEl, selector, target) {
    if (!navEl || !target) return;
    clearActive(navEl, selector);
    target.classList.add("active");
  }

  // Server Management / SSH Connections / Model Stats / PC Monitor are all
  // nested one level under the System Status tab, so their own "Back" buttons
  // land one level up in nav.status (not all the way out to nav.main/home).
  function returnToStatus(statusTarget) {
    nav.status.classList.remove("hidden");
    const tab = nav.status.querySelector(
      `[data-nav="status"][data-target="${statusTarget}"]`,
    );
    if (tab) setActive(nav.status, '[data-nav="status"][data-target]', tab);
    else clearActive(nav.status, '[data-nav="status"][data-target]');
    activateView("status-home");
  }

  // Back out of a sub-nav to the top-level main nav, landing on Home.
  function returnToHome(subNavEl) {
    subNavEl?.classList.add("hidden");
    nav.main.classList.remove("hidden");
    const homeTab = nav.main.querySelector(
      '[data-nav="main"][data-target="home"]',
    );
    if (homeTab) setActive(nav.main, '[data-nav="main"][data-target]', homeTab);
    activateView("home");
  }

  function setAgentDetailContent(agentName) {
    const name = (agentName || "Agent").trim();
    const titleEl = doc.getElementById("agent-detail-title");
    const homeEl = doc.getElementById("agent-detail-home-text");
    if (titleEl) titleEl.textContent = name;
    if (homeEl)
      homeEl.textContent = `Choose a tab above to view ${name}'s data.`;
  }

  // Roll the worst known status subsection up to the top-level System Status
  // tab. A healthy roll-up is solid green; any warning/error blinks so hidden
  // problems remain visible from the dashboard home screen.
  function updateSystemStatusTab() {
    const systemTab = doc.getElementById("btn-system-status");
    if (!systemTab) return;
    const children = [
      "btn-server-mgmt",
      "btn-ssh-connections",
      "btn-model-stats",
      "btn-pc-monitor",
    ]
      .map((id) => doc.getElementById(id))
      .filter(Boolean);
    const down = children.some(
      (tab) =>
        tab.classList.contains("server-down") ||
        tab.classList.contains("tab-alert-red"),
    );
    const concern = children.some(
      (tab) =>
        tab.classList.contains("server-concern") ||
        tab.classList.contains("server-starting") ||
        tab.classList.contains("tab-alert"),
    );
    const allKnown =
      children.length === 4 &&
      children.every((tab) =>
        ["server-up", "server-concern", "server-down", "server-starting"].some(
          (name) => tab.classList.contains(name),
        ),
      );
    systemTab.classList.remove("server-up", "server-concern", "server-down");
    systemTab.classList.toggle("tab-alert-red", down);
    systemTab.classList.toggle("tab-alert", !down && concern);
    if (down) systemTab.classList.add("server-down");
    else if (concern) systemTab.classList.add("server-concern");
    else if (allKnown) systemTab.classList.add("server-up");
  }

  return {
    clearActive,
    activateView,
    setActive,
    returnToStatus,
    returnToHome,
    setAgentDetailContent,
    updateSystemStatusTab,
    setStatementReviewDialog(dialog) {
      statementReviewDialog = dialog;
    },
  };
}
