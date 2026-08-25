// agent-nav.js — the Agents sidebar and the per-agent detail fanout.
//
// Agent tabs are injected dynamically as the roster loads, so both levels use
// event delegation rather than per-tab listeners.

export function bindAgentNav({ doc, nav, viewNav, AM }) {
  nav.agents.addEventListener("click", (e) => {
    const tab = e.target.closest(".tab");
    if (!tab || tab.id === "btn-back-agents") return;

    // "Agents" home tab — show the (re)loaded agent list.
    if (tab.dataset.target === "agents-home") {
      AM.showAgentsHome();
      return;
    }

    // A specific agent tab — open its detail fanout.
    if (tab.dataset.agentId) {
      viewNav.setActive(nav.agents, ".tab", tab);
      AM.openAgent(
        tab.dataset.agentId,
        tab.dataset.agentName || tab.textContent,
      );
    }
  });

  // Agent-detail tabs (Thoughts / Messages / Tool Calls / Input Options).
  nav.agentDetail.addEventListener("click", (e) => {
    const tab = e.target.closest(".tab");
    if (!tab || tab.id === "btn-back-agent-detail") return;
    const target = tab.dataset.target;
    if (!target) return;
    viewNav.setActive(
      nav.agentDetail,
      '[data-nav="agent-detail"][data-target]',
      tab,
    );
    viewNav.activateView(target);
    AM.renderDetail(target);
  });

  doc
    .getElementById("btn-back-agents")
    ?.addEventListener("click", () => viewNav.returnToHome(nav.agents));

  // Agent detail backs out one level, to the agent list.
  doc.getElementById("btn-back-agent-detail")?.addEventListener("click", () => {
    AM.stopPoll();
    nav.agentDetail.classList.add("hidden");
    nav.agents.classList.remove("hidden");
    AM.showAgentsHome();
  });
}
