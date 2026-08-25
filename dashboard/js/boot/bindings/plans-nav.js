// plans-nav.js — Project Plans and its Process Flows child nav.
//
// The Voice Communication tab is the one plan that is not a plain iframe swap:
// VoiceCommunicationNavigationController owns its own spec list and frame.

export function bindPlansNav({ doc, nav, viewNav, voiceCommunicationNav }) {
  const openProcessFlows = () => {
    nav.plans.classList.add("hidden");
    nav.processFlows.classList.remove("hidden");
    const reportFlowTab = nav.processFlows.querySelector(
      '[data-nav="process-flows"][data-target="plans-report-flow"]',
    );
    if (reportFlowTab)
      viewNav.setActive(
        nav.processFlows,
        '[data-nav="process-flows"][data-target]',
        reportFlowTab,
      );
    viewNav.activateView("plans-report-flow");
  };

  nav.plans
    .querySelectorAll('[data-nav="plans"][data-target]')
    .forEach((tab) => {
      tab.addEventListener("click", () => {
        if (tab.dataset.target === "plans-process-flows") {
          openProcessFlows();
          return;
        }
        viewNav.setActive(nav.plans, '[data-nav="plans"][data-target]', tab);
        if (tab.dataset.target === "plans-voice-communication") {
          voiceCommunicationNav.open();
          return;
        }
        viewNav.activateView(tab.dataset.target);
      });
    });

  nav.processFlows
    .querySelectorAll('[data-nav="process-flows"][data-target]')
    .forEach((tab) => {
      tab.addEventListener("click", () => {
        viewNav.setActive(
          nav.processFlows,
          '[data-nav="process-flows"][data-target]',
          tab,
        );
        viewNav.activateView(tab.dataset.target);
      });
    });

  doc
    .getElementById("btn-back-plans")
    ?.addEventListener("click", () => viewNav.returnToHome(nav.plans));

  // Process Flows backs out one level, to Project Plans — not to Home.
  doc
    .getElementById("btn-back-process-flows")
    ?.addEventListener("click", () => {
      nav.processFlows.classList.add("hidden");
      nav.plans.classList.remove("hidden");
      const processFlowsTab = nav.plans.querySelector(
        '[data-nav="plans"][data-target="plans-process-flows"]',
      );
      if (processFlowsTab)
        viewNav.setActive(
          nav.plans,
          '[data-nav="plans"][data-target]',
          processFlowsTab,
        );
      viewNav.activateView("plans-process-flows");
    });
}
