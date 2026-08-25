// main-nav.js — the top-level sidebar and the System Status sub-nav.
//
// Most main-nav targets are a plain view switch; the five that open a sub-nav
// (Status, Agent Management, Project Plans, Process Flows, ROL Finance) hide
// the main nav and hand off to that section's own landing.

export function bindMainNav({ doc, nav, viewNav, AM, SM, SSHM, MS, PCM }) {
  // Open a sub-nav: hide the parent nav, show the child, select `target`.
  const openSubNav = (parentNav, childNav, selector, target) => {
    parentNav.classList.add("hidden");
    childNav.classList.remove("hidden");
    const tab = childNav.querySelector(`${selector}[data-target="${target}"]`);
    if (tab) viewNav.setActive(childNav, `${selector}[data-target]`, tab);
    viewNav.activateView(target);
  };

  nav.main.querySelectorAll('[data-nav="main"][data-target]').forEach((tab) => {
    tab.addEventListener("click", () => {
      const target = tab.dataset.target;
      if (!target) return;

      if (target === "status") {
        nav.main.classList.add("hidden");
        nav.status.classList.remove("hidden");
        viewNav.clearActive(nav.status, '[data-nav="status"][data-target]');
        viewNav.activateView("status-home");
        return;
      }

      if (target === "agent-management") {
        nav.main.classList.add("hidden");
        nav.agents.classList.remove("hidden");
        AM.showAgentsHome();
        return;
      }

      if (target === "project-plans") {
        openSubNav(
          nav.main,
          nav.plans,
          '[data-nav="plans"]',
          "plans-self-evolving",
        );
        return;
      }

      if (target === "plans-process-flows") {
        openSubNav(
          nav.plans,
          nav.processFlows,
          '[data-nav="process-flows"]',
          "plans-report-flow",
        );
        return;
      }

      if (target === "rol-finance") {
        openSubNav(
          nav.main,
          nav.rolFinance,
          '[data-nav="rol-finance"]',
          "rol-finance-plan",
        );
        return;
      }

      viewNav.setActive(nav.main, '[data-nav="main"][data-target]', tab);
      viewNav.activateView(target);
    });
  });

  nav.status
    .querySelectorAll('[data-nav="status"][data-target]')
    .forEach((tab) => {
      tab.addEventListener("click", () => {
        const target = tab.dataset.target;
        viewNav.setActive(nav.status, '[data-nav="status"][data-target]', tab);

        if (target === "server-management") {
          nav.status.classList.add("hidden");
          nav.servers.classList.remove("hidden");
          SM.showServersHome();
          return;
        }

        if (target === "ssh-connections") {
          nav.status.classList.add("hidden");
          nav.ssh.classList.remove("hidden");
          SSHM.showConnectionsHome();
          return;
        }

        if (target === "model-stats" && nav.modelStats) {
          nav.status.classList.add("hidden");
          nav.modelStats.classList.remove("hidden");
          viewNav.activateView("model-stats");
          MS.open();
          return;
        }

        if (target === "pc-monitor" && nav.pcMonitor) {
          nav.status.classList.add("hidden");
          nav.pcMonitor.classList.remove("hidden");
          viewNav.activateView("pc-monitor");
          PCM.open();
        }
      });
    });

  const backStatus = doc.getElementById("btn-back");
  backStatus?.addEventListener("click", () => viewNav.returnToHome(nav.status));
}
