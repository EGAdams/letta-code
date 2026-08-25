// agent-tab-status.js — the colours on the agent sidebar tabs.
//
// Two independent signals, deliberately kept on separate CSS classes so one
// cannot wipe the other:
//   • activity  (/api/agent-activity, 5s)  → agent-active / agent-error
//   • structural health (/api/agent-health, 30s) → agent-health-error
// Unhealthy agents also bubble up to the parent "Agent Management" sidebar
// button (mirrors how Server Management goes red when any server is down) — so
// a Claude-SDK 404 lights up both Frita's tab AND her parent.

import {
  AgentActivityPoller,
  AgentHealthPoller,
} from "../implementation/index.js";

export function createAgentTabStatus({ doc = document, http, nav }) {
  const unhealthyAgents = new Set();
  const agentMgmtBtn = doc.getElementById("btn-agent-mgmt");

  const setAgentTabStatus = (agentId, status) => {
    const tab = nav.agents.querySelector(
      `.agent-tab[data-agent-id="${agentId}"]`,
    );
    if (!tab) return;
    tab.classList.remove("agent-active", "agent-error");
    if (status === "active") tab.classList.add("agent-active");
    else if (status === "error") tab.classList.add("agent-error");
  };

  const setAgentTabHealth = (agentId, ok) => {
    const tab = nav.agents.querySelector(
      `.agent-tab[data-agent-id="${agentId}"]`,
    );
    if (tab) tab.classList.toggle("agent-health-error", !ok);
    if (ok) unhealthyAgents.delete(agentId);
    else unhealthyAgents.add(agentId);
    if (agentMgmtBtn) {
      agentMgmtBtn.classList.toggle(
        "agent-health-error",
        unhealthyAgents.size > 0,
      );
    }
  };

  return {
    setAgentTabStatus,
    setAgentTabHealth,
    start() {
      new AgentActivityPoller({ http, setStatus: setAgentTabStatus }).start();
      new AgentHealthPoller({ http, setHealth: setAgentTabHealth }).start();
    },
  };
}
