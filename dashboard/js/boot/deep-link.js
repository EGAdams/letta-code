// deep-link.js — URL entry points into a specific tab.
//
//   ?agent=<id>&view=thoughts|messages|tool-calls|chat-interface
//   ?view=rol-finance-reports  -> Project Plans > ROL Finance > Reports

export function applyDeepLink({ nav, AM, RF, search = location.search }) {
  const q = new URLSearchParams(search);
  const agent = q.get("agent");
  if (agent) {
    AM.openById(agent, q.get("view") || "thoughts");
    return;
  }
  if (q.get("view") === "rol-finance-reports") {
    nav.main.classList.add("hidden");
    nav.rolFinanceReports.classList.remove("hidden");
    RF.openReports().then(() => RF.refreshStatus());
  }
}
