// agent-manager.js — the AM facade: the agent roster, the per-agent detail
// fanout, and the deep-link entry point.
//
// Rendering is delegated to the Strategy table in agent-detail-renderers.js;
// the scanner-report panels live in scanner-agent-views.js. What is left here
// is navigation state: which agent is open, which tab is showing, and the
// sidebar tabs themselves.

import { TextUtils } from "../abstract/text-utils.js";
import { createAgentDetailRenderers } from "./agent-detail-renderers.js";
import { createScannerAgentViews } from "./scanner-agent-views.js";

const esc = TextUtils.esc;

export function createAgentManager({
  doc = document,
  http,
  poller,
  nav,
  viewNav,
  agentGate,
  tabFactory,
  speech,
  setAgentTabStatus,
}) {
  const scannerViews = createScannerAgentViews({ doc, http });
  const { detailRenderers, renderAgentsRouter } = createAgentDetailRenderers({
    http,
    poller,
    speech,
    setAgentTabStatus,
    getAgentManager: () => AM,
  });

  const AM = {
    current: null, // { id, name }
    agents: null,
    agentsLoadedAt: 0,
    served: location.protocol === "http:" || location.protocol === "https:",

    // Stop whichever agent stream is currently polling (if any).
    stopPoll() {
      poller.stop();
    },

    // Show the agent-list landing in the sidebar and (re)load the agent tabs.
    showAgentsHome() {
      this.stopPoll();
      this.current = null;
      nav.agentDetail.classList.add("hidden");
      nav.agents.classList.remove("hidden");
      const homeTab = nav.agents.querySelector(
        '[data-nav="agents"][data-target="agents-home"]',
      );
      if (homeTab) viewNav.setActive(nav.agents, ".tab", homeTab);
      viewNav.activateView("agents-home");
      this.loadAgentTabs();
    },

    // Fetch agents and inject one sidebar tab per agent.
    async loadAgentTabs() {
      if (this._tabsLoading) return;
      this._tabsLoading = true;
      try {
        const status = doc.getElementById("agents-home-status");
        // Drop any previously-injected agent tabs.
        nav.agents.querySelectorAll(".agent-tab").forEach((t) => {
          t.remove();
        });

        if (!this.served) {
          if (status)
            status.innerHTML =
              '<span class="am-warn" style="display:block">' +
              "This page is open as a <code>file://</code> document, which can't reach the Letta API. " +
              "Open the served version instead: <strong>http://100.80.49.10:8765/</strong> " +
              "(over Tailscale) or <strong>http://localhost:8765/</strong> on this machine.<br>" +
              "Start it with: <code>python3 ~/dashboard_server.py</code></span>";
          return;
        }

        const alreadyCached = !!this.agents;
        if (!alreadyCached) {
          agentGate.start();
          agentGate.writeLine("Fetching agent roster...");
          if (status) status.textContent = "Loading agents…";
          try {
            this.agents = await http.getJSON("/api/agents");
            this.agentsLoadedAt = Date.now();
          } catch (e) {
            agentGate.fail("agents", e);
            if (status)
              status.innerHTML =
                '<span class="am-warn" style="display:block">Failed to load agents: ' +
                esc(e.message) +
                "</span>";
            return;
          }
        }

        if (!this.agents.length) {
          if (!alreadyCached) {
            agentGate.writeLine("No agents found.");
            agentGate.complete("agents", "Loaded 0 agents.");
          }
          if (status) status.textContent = "No agents found.";
          return;
        }

        for (const a of this.agents) {
          if (!alreadyCached) agentGate.writeLine(`Agent ${a.name}`);
          nav.agents.appendChild(tabFactory.buildAgentTab(a));
        }
        if (!alreadyCached)
          agentGate.complete("agents", `Loaded ${this.agents.length} agents.`);
        // Replaces the old static "Loaded N agents…" message with the
        // voice/text router (see AgentsRouterRenderer).
        renderAgentsRouter("agents-home-status");
      } finally {
        this._tabsLoading = false;
      }
    },

    // Switch the sidebar to the per-agent detail fanout, Thoughts first.
    openAgent(id, name) {
      this.current = { id, name };
      this.stopPoll();
      viewNav.setAgentDetailContent(name);

      nav.agents.classList.add("hidden");
      nav.agentDetail.classList.remove("hidden");

      const thoughtsTab = nav.agentDetail.querySelector(
        '[data-nav="agent-detail"][data-target="agent-detail-thoughts"]',
      );
      if (thoughtsTab)
        viewNav.setActive(
          nav.agentDetail,
          '[data-nav="agent-detail"][data-target]',
          thoughtsTab,
        );
      viewNav.activateView("agent-detail-thoughts");
      this.renderDetail("agent-detail-thoughts");
    },

    // Render content for whichever agent-detail tab is active. Returns whatever
    // the renderer's render() returns (e.g. InputOptionsRenderer's {send,
    // setText, appendText, ...} api), so deep-link callers like the Agents-home
    // router can reach the freshly-rendered panel without touching DOM globals.
    renderDetail(target) {
      this.stopPoll();
      if (!this.current) return undefined;
      if (target === "agent-detail-home") {
        viewNav.setAgentDetailContent(this.current.name);
        return undefined;
      }
      const fn = detailRenderers[target];
      return fn ? fn(this, target) : undefined;
    },

    // Deep-link helper: open an agent (and optional detail tab) by id. Returns
    // the render() result for the requested view (see renderDetail above).
    async openById(id, view) {
      nav.main.classList.add("hidden");
      nav.agents.classList.remove("hidden");
      if (!this.agents) {
        try {
          this.agents = await http.getJSON("/api/agents");
        } catch (_e) {}
      }
      const a = (this.agents || []).find((x) => x.id === id);
      this.openAgent(id, a ? a.name : id);
      const target = `agent-detail-${view || "thoughts"}`;
      const tab = nav.agentDetail.querySelector(
        `[data-nav="agent-detail"][data-target="${target}"]`,
      );
      if (tab) {
        viewNav.setActive(
          nav.agentDetail,
          '[data-nav="agent-detail"][data-target]',
          tab,
        );
        viewNav.activateView(target);
        return this.renderDetail(target);
      }
      return undefined;
    },

    renderMazdaThoughtsInto: scannerViews.renderMazdaThoughtsInto,
    showArchiveTerminalForScanner: scannerViews.showArchiveTerminalForScanner,
  };

  return AM;
}
