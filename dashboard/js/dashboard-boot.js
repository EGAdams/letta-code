// dashboard-boot.js — the dashboard's entry point.
//
// This is the thin boot layer that wires the GoF library in js/implementation/
// to the live page: it looks up the page's elements, constructs the shared
// ports (HttpClient, ActivePoller, DomTabFactory, SpeechSynthesizer), builds
// the detail-renderer strategies, and keeps the page-specific navigation glue
// (the sidebar tab transitions, AM/SM/SSHM/RF facades, deep-linking). All
// behaviour lives in the unit-tested classes under ./implementation/; this file
// only binds them to the DOM. See clean_up_dashboard_html.md for the cutover.

import { TextUtils } from "./abstract/text-utils.js";
import {
  ActivePoller,
  AgentActivityPoller,
  AgentCardRenderer,
  AgentHealthPoller,
  BrowserSpeechSynthesizer,
  ChatDetailRenderer,
  CodeChangeAlert,
  ConnectionLogController,
  ConnectionTestController,
  DomConsoleView,
  DomTabFactory,
  FetchHttpClient,
  InputOptionsRenderer,
  RolFinanceReportsController,
  ServerActionController,
  ServerHealthMonitor,
  ServerLogController,
  StreamDetailRenderer,
} from "./implementation/index.js";

// One shared HttpClient (Adapter over fetch) used by AM / SM / SSHM / RF.
const http = new FetchHttpClient();

// One shared ActivePoller: only one agent stream polls at a time, so
// switching tabs/agents stops the previous stream before starting a new one.
const poller = new ActivePoller();

// Shared tab factory (builds sidebar agent/server tabs with the right
// dataset + classes).
const tabFactory = new DomTabFactory();

const mainContent = document.getElementById("main-content");
const navMain = document.getElementById("nav-main");
const navStatus = document.getElementById("nav-status");
const navTools = document.getElementById("nav-tools");
const navAgents = document.getElementById("nav-agents");
const navAgentDetail = document.getElementById("nav-agent-detail");
const navServers = document.getElementById("nav-servers");
const navSSH = document.getElementById("nav-ssh-connections");
const navPlans = document.getElementById("nav-plans");
const navRolFinance = document.getElementById("nav-rol-finance");
const navRolFinanceReports = document.getElementById("nav-rol-finance-reports");

// Leave empty to auto-use the current host/origin.
// Set this if you need to pin links to a specific public URL.
const WINDOWS_10_PUBLIC_URL = "";

function getWindows10BaseUrl() {
  const configured =
    typeof WINDOWS_10_PUBLIC_URL === "string"
      ? WINDOWS_10_PUBLIC_URL.trim()
      : "";
  if (configured) return configured.replace(/\/$/, "");
  return window.location.origin.replace(/\/$/, "");
}

function applyInstructionLinks() {
  const base = getWindows10BaseUrl();
  const guide = `${base}/americanjewelry_live_upload_guide.html`;
  const mgmt = `${base}/windows_10_dashboard_management.html`;
  const guideEl = document.getElementById("instructions-guide-link");
  const mgmtEl = document.getElementById("instructions-mgmt-link");
  if (guideEl) {
    guideEl.href = guide;
    guideEl.textContent = guide;
  }
  if (mgmtEl) {
    mgmtEl.href = mgmt;
    mgmtEl.textContent = mgmt;
  }
}

function clearActive(navEl, selector) {
  if (!navEl) return;
  navEl.querySelectorAll(selector).forEach((el) => {
    el.classList.remove("active");
  });
}

function safeActivateView(id, fallbackId = "home") {
  const next = document.getElementById(id) ? id : fallbackId;
  document.querySelectorAll(".view").forEach((v) => {
    v.classList.remove("active");
  });
  const view = document.getElementById(next);
  if (view) view.classList.add("active");
  // Iframe-based views (Project Plans, ROL Finance Reports)
  // should fill all available width instead of being capped/padded like
  // text views — otherwise the report column is too skinny, especially on
  // Android. Detect them by the presence of a full-bleed frame.
  const isFullbleed = view && view.querySelector(".plan-frame") !== null;
  if (mainContent) mainContent.classList.toggle("fullbleed", !!isFullbleed);
}

function safeSetActive(navEl, selector, target) {
  if (!navEl || !target) return;
  clearActive(navEl, selector);
  target.classList.add("active");
}

function setAgentDetailContent(agentName) {
  const name = (agentName || "Agent").trim();
  const titleEl = document.getElementById("agent-detail-title");
  const homeEl = document.getElementById("agent-detail-home-text");
  if (titleEl) titleEl.textContent = name;
  if (homeEl) homeEl.textContent = `Choose a tab above to view ${name}'s data.`;
}

applyInstructionLinks();
setAgentDetailContent("Agent");

if (
  navMain &&
  navStatus &&
  navTools &&
  navAgents &&
  navAgentDetail &&
  navServers &&
  navSSH &&
  navPlans &&
  navRolFinance &&
  navRolFinanceReports
) {
  navMain.querySelectorAll('[data-nav="main"][data-target]').forEach((tab) => {
    tab.addEventListener("click", () => {
      const target = tab.dataset.target;
      if (!target) return;

      if (target === "status") {
        navMain.classList.add("hidden");
        navStatus.classList.remove("hidden");
        const statusHome = navStatus.querySelector(
          '[data-nav="status"][data-target="status-home"]',
        );
        if (statusHome)
          safeSetActive(
            navStatus,
            '[data-nav="status"][data-target]',
            statusHome,
          );
        safeActivateView("status-home");
        return;
      }

      if (target === "tool-management") {
        navMain.classList.add("hidden");
        navTools.classList.remove("hidden");
        const toolsHome = navTools.querySelector(
          '[data-nav="tools"][data-target="tools-home"]',
        );
        if (toolsHome)
          safeSetActive(navTools, '[data-nav="tools"][data-target]', toolsHome);
        safeActivateView("tools-home");
        return;
      }

      if (target === "agent-management") {
        navMain.classList.add("hidden");
        navAgents.classList.remove("hidden");
        AM.showAgentsHome();
        return;
      }

      if (target === "server-management") {
        navMain.classList.add("hidden");
        navServers.classList.remove("hidden");
        SM.showServersHome();
        return;
      }

      if (target === "ssh-connections") {
        navMain.classList.add("hidden");
        navSSH.classList.remove("hidden");
        SSHM.showConnectionsHome();
        return;
      }

      if (target === "project-plans") {
        navMain.classList.add("hidden");
        navPlans.classList.remove("hidden");
        const firstPlan = navPlans.querySelector(
          '[data-nav="plans"][data-target="plans-self-evolving"]',
        );
        if (firstPlan)
          safeSetActive(navPlans, '[data-nav="plans"][data-target]', firstPlan);
        safeActivateView("plans-self-evolving");
        return;
      }

      if (target === "rol-finance") {
        navMain.classList.add("hidden");
        navRolFinance.classList.remove("hidden");
        const planTab = navRolFinance.querySelector(
          '[data-nav="rol-finance"][data-target="rol-finance-plan"]',
        );
        if (planTab)
          safeSetActive(
            navRolFinance,
            '[data-nav="rol-finance"][data-target]',
            planTab,
          );
        safeActivateView("rol-finance-plan");
        return;
      }

      safeSetActive(navMain, '[data-nav="main"][data-target]', tab);
      safeActivateView(target);
    });
  });

  navStatus
    .querySelectorAll('[data-nav="status"][data-target]')
    .forEach((tab) => {
      tab.addEventListener("click", () => {
        safeSetActive(navStatus, '[data-nav="status"][data-target]', tab);
        safeActivateView(tab.dataset.target);
        if (tab.dataset.target === "status-servers") {
          void loadServersSummary();
        }
      });
    });

  navTools
    .querySelectorAll('[data-nav="tools"][data-target]')
    .forEach((tab) => {
      tab.addEventListener("click", () => {
        safeSetActive(navTools, '[data-nav="tools"][data-target]', tab);
        safeActivateView(tab.dataset.target);
      });
    });

  navPlans
    .querySelectorAll('[data-nav="plans"][data-target]')
    .forEach((tab) => {
      tab.addEventListener("click", () => {
        safeSetActive(navPlans, '[data-nav="plans"][data-target]', tab);
        safeActivateView(tab.dataset.target);
      });
    });

  // ROL Finance sub-nav (Current Status / Taxes / Reports)
  navRolFinance
    .querySelectorAll('[data-nav="rol-finance"][data-target]')
    .forEach((tab) => {
      tab.addEventListener("click", () => {
        if (tab.dataset.target === "rol-finance-reports") {
          safeSetActive(
            navRolFinance,
            '[data-nav="rol-finance"][data-target]',
            tab,
          );
          navRolFinance.classList.add("hidden");
          navRolFinanceReports.classList.remove("hidden");
          RF.openReports();
          return;
        }
        safeSetActive(
          navRolFinance,
          '[data-nav="rol-finance"][data-target]',
          tab,
        );
        safeActivateView(tab.dataset.target);
      });
    });

  // ROL Finance month + report tabs are injected dynamically, so use event
  // delegation. Month tabs switch the document list (Jan/Feb 2025); report tabs
  // open a single document. The controller manages the active state of each row
  // independently so the open month and open document stay highlighted.
  navRolFinanceReports.addEventListener("click", (e) => {
    const tab = e.target.closest(".tab");
    if (!tab || tab.id === "btn-back-rol-finance-reports") return;
    if (tab.dataset.monthKey) {
      RF.openMonth(tab.dataset.monthKey);
      return;
    }
    if (tab.dataset.reportKey) {
      RF.selectReport(tab.dataset.reportKey);
    }
  });

  // Agent tabs are injected dynamically, so use event delegation.
  navAgents.addEventListener("click", (e) => {
    const tab = e.target.closest(".tab");
    if (!tab || tab.id === "btn-back-agents") return;

    // "Agents" home tab — show the (re)loaded agent list
    if (tab.dataset.target === "agents-home") {
      AM.showAgentsHome();
      return;
    }

    // A specific agent tab — open its detail fanout
    if (tab.dataset.agentId) {
      safeSetActive(navAgents, ".tab", tab);
      AM.openAgent(
        tab.dataset.agentId,
        tab.dataset.agentName || tab.textContent,
      );
    }
  });

  // Agent-detail tabs (Thoughts / Messages / Tool Calls / Input Options).
  navAgentDetail.addEventListener("click", (e) => {
    const tab = e.target.closest(".tab");
    if (!tab || tab.id === "btn-back-agent-detail") return;
    const target = tab.dataset.target;
    if (!target) return;
    safeSetActive(
      navAgentDetail,
      '[data-nav="agent-detail"][data-target]',
      tab,
    );
    safeActivateView(target);
    AM.renderDetail(target);
  });

  // Server tabs are injected dynamically, so use event delegation.
  navServers.addEventListener("click", (e) => {
    const tab = e.target.closest(".tab");
    if (!tab || tab.id === "btn-back-servers") return;
    if (tab.dataset.serverKey) {
      safeSetActive(navServers, ".tab", tab);
      SM.openServer(
        tab.dataset.serverKey,
        tab.dataset.serverName || tab.textContent,
      );
    }
  });

  const backServers = document.getElementById("btn-back-servers");
  if (backServers) {
    backServers.addEventListener("click", () => {
      SM.stopPoll();
      navServers.classList.add("hidden");
      navMain.classList.remove("hidden");
      const homeTab = navMain.querySelector(
        '[data-nav="main"][data-target="home"]',
      );
      if (homeTab)
        safeSetActive(navMain, '[data-nav="main"][data-target]', homeTab);
      safeActivateView("home");
    });
  }

  // SSH connection tabs are injected dynamically, so use event delegation.
  navSSH.addEventListener("click", (e) => {
    const tab = e.target.closest(".tab");
    if (!tab || tab.id === "btn-back-ssh") return;
    if (tab.dataset.connKey) {
      safeSetActive(navSSH, ".tab", tab);
      SSHM.openConnection(
        tab.dataset.connKey,
        tab.dataset.connName || tab.textContent,
      );
    }
  });

  const backSSH = document.getElementById("btn-back-ssh");
  if (backSSH) {
    backSSH.addEventListener("click", () => {
      SSHM.stopPoll();
      navSSH.classList.add("hidden");
      navMain.classList.remove("hidden");
      const homeTab = navMain.querySelector(
        '[data-nav="main"][data-target="home"]',
      );
      if (homeTab)
        safeSetActive(navMain, '[data-nav="main"][data-target]', homeTab);
      safeActivateView("home");
    });
  }

  const backTools = document.getElementById("btn-back-tools");
  if (backTools) {
    backTools.addEventListener("click", () => {
      navTools.classList.add("hidden");
      navMain.classList.remove("hidden");
      const homeTab = navMain.querySelector(
        '[data-nav="main"][data-target="home"]',
      );
      if (homeTab)
        safeSetActive(navMain, '[data-nav="main"][data-target]', homeTab);
      safeActivateView("home");
    });
  }

  const backStatus = document.getElementById("btn-back");
  if (backStatus) {
    backStatus.addEventListener("click", () => {
      navStatus.classList.add("hidden");
      navMain.classList.remove("hidden");
      const homeTab = navMain.querySelector(
        '[data-nav="main"][data-target="home"]',
      );
      if (homeTab)
        safeSetActive(navMain, '[data-nav="main"][data-target]', homeTab);
      safeActivateView("home");
    });
  }

  const backPlans = document.getElementById("btn-back-plans");
  if (backPlans) {
    backPlans.addEventListener("click", () => {
      navPlans.classList.add("hidden");
      navMain.classList.remove("hidden");
      const homeTab = navMain.querySelector(
        '[data-nav="main"][data-target="home"]',
      );
      if (homeTab)
        safeSetActive(navMain, '[data-nav="main"][data-target]', homeTab);
      safeActivateView("home");
    });
  }

  // Back from the ROL Finance sub-nav -> main nav / Home.
  const backRolFinance = document.getElementById("btn-back-rol-finance");
  if (backRolFinance) {
    backRolFinance.addEventListener("click", () => {
      navRolFinance.classList.add("hidden");
      navMain.classList.remove("hidden");
      const homeTab = navMain.querySelector(
        '[data-nav="main"][data-target="home"]',
      );
      if (homeTab)
        safeSetActive(navMain, '[data-nav="main"][data-target]', homeTab);
      safeActivateView("home");
    });
  }

  // Back from the ROL Finance Reports sub-nav -> ROL Finance sub-nav.
  const backRolFinanceReports = document.getElementById(
    "btn-back-rol-finance-reports",
  );
  if (backRolFinanceReports) {
    backRolFinanceReports.addEventListener("click", () => {
      navRolFinanceReports.classList.add("hidden");
      navRolFinance.classList.remove("hidden");
      const reportsTab = navRolFinance.querySelector(
        '[data-nav="rol-finance"][data-target="rol-finance-reports"]',
      );
      if (reportsTab)
        safeSetActive(
          navRolFinance,
          '[data-nav="rol-finance"][data-target]',
          reportsTab,
        );
      safeActivateView("rol-finance-reports");
    });
  }

  const backAgents = document.getElementById("btn-back-agents");
  if (backAgents) {
    backAgents.addEventListener("click", () => {
      navAgents.classList.add("hidden");
      navMain.classList.remove("hidden");
      const homeTab = navMain.querySelector(
        '[data-nav="main"][data-target="home"]',
      );
      if (homeTab)
        safeSetActive(navMain, '[data-nav="main"][data-target]', homeTab);
      safeActivateView("home");
    });
  }

  const backAgentDetail = document.getElementById("btn-back-agent-detail");
  if (backAgentDetail) {
    backAgentDetail.addEventListener("click", () => {
      AM.stopPoll();
      navAgentDetail.classList.add("hidden");
      navAgents.classList.remove("hidden");
      AM.showAgentsHome();
    });
  }
}

/* =====================  Utilities  ===================== */
const esc = TextUtils.esc; // HTML-escape — now sourced from the library.

/* =====================  Voice output (Web Speech API)  =====================
       Browser-native text-to-speech. No API key, no server round-trip, free.
       Now provided by the library's BrowserSpeechSynthesizer (Facade) +
       AgentVoiceCatalog (Strategy/Registry): each agent gets its own cached
       voice so Scissari, Mazda, Frita, Hailey, Jeri, Cesare and the Mazda
       stages sound distinct, never falling back to a male voice. The per-agent
       voice catalog (FEMALE/MALE patterns, agent preferences, selection +
       male-avoidance fallbacks) lives in
       js/abstract/agent-voice-catalog.interface.js. */
const Speech = new BrowserSpeechSynthesizer(window);
Speech.bindVoiceChanges(); // initial pick + re-pick/clear on onvoiceschanged

/* =====================  Agent Manager  ===================== */
// The three agent-detail streams (Thoughts / Messages / Tool Calls) are
// rendered by the library's StreamDetailRenderer: each mounts a console
// view into its container and drives an AgentStreamController through the
// shared `poller` (3s polling, dedup, "no X yet" placeholder).
const streamRenderers = {
  "agent-detail-thoughts": new StreamDetailRenderer({
    http,
    poller,
    url: "/api/thoughts",
    label: "thoughts",
  }),
  "agent-detail-messages": new StreamDetailRenderer({
    http,
    poller,
    url: "/api/messages",
    label: "messages",
  }),
  "agent-detail-tool-calls": new StreamDetailRenderer({
    http,
    poller,
    url: "/api/toolcalls",
    label: "tool calls",
  }),
};
const agentCardRenderer = new AgentCardRenderer({ http });

// Chat / Input Options are rebuilt per open so they carry the current
// agent's name (heading + per-agent voice). onStatus colours the sidebar tab.
const renderChat = (am, target) =>
  new ChatDetailRenderer({
    http,
    speech: Speech,
    agentName: am.current.name,
    agentId: am.current.id,
    onStatus: setAgentTabStatus,
  }).render(target, am.current.id);
const renderInputOptions = (am, target) =>
  new InputOptionsRenderer({
    http,
    speech: Speech,
    agentName: am.current.name,
    agentId: am.current.id,
    onStatus: setAgentTabStatus,
  }).render(target, am.current.id);

// Maps an agent-detail view id to how its content is rendered.
const DETAIL_RENDERERS = {
  "agent-detail-thoughts": (am, id) =>
    streamRenderers[id].render(id, am.current.id),
  "agent-detail-messages": (am, id) =>
    streamRenderers[id].render(id, am.current.id),
  "agent-detail-tool-calls": (am, id) =>
    streamRenderers[id].render(id, am.current.id),
  "agent-detail-agent-card": (am, id) =>
    agentCardRenderer.render(id, am.current.id),
  "agent-detail-tests": (am, id) => renderChat(am, id),
  "agent-detail-input-options": (am, id) => renderInputOptions(am, id),
};

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
    navAgentDetail.classList.add("hidden");
    navAgents.classList.remove("hidden");
    const homeTab = navAgents.querySelector(
      '[data-nav="agents"][data-target="agents-home"]',
    );
    if (homeTab) safeSetActive(navAgents, ".tab", homeTab);
    safeActivateView("agents-home");
    this.loadAgentTabs();
  },

  // Fetch agents and inject one sidebar tab per agent.
  async loadAgentTabs() {
    if (this._tabsLoading) return;
    this._tabsLoading = true;
    try {
      const status = document.getElementById("agents-home-status");
      // Drop any previously-injected agent tabs.
      navAgents.querySelectorAll(".agent-tab").forEach((t) => {
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

      if (!this.agents) {
        if (status) status.textContent = "Loading agents…";
        try {
          this.agents = await http.getJSON("/api/agents");
          this.agentsLoadedAt = Date.now();
        } catch (e) {
          if (status)
            status.innerHTML =
              '<span class="am-warn" style="display:block">Failed to load agents: ' +
              esc(e.message) +
              "</span>";
          return;
        }
      }

      if (!this.agents.length) {
        if (status) status.textContent = "No agents found.";
        return;
      }

      for (const a of this.agents) {
        navAgents.appendChild(tabFactory.buildAgentTab(a));
      }
      const age = this.agentsLoadedAt
        ? Math.max(0, Math.round((Date.now() - this.agentsLoadedAt) / 1000))
        : 0;
      if (status)
        status.innerHTML =
          "Loaded <strong>" +
          this.agents.length +
          "</strong> agent" +
          (this.agents.length === 1 ? "" : "s") +
          (age ? ` <span class="dim">(cached ${age}s ago)</span>` : "") +
          ". Pick one from the left to view its Thoughts, Messages, Tool Calls, or Input Options.";
    } finally {
      this._tabsLoading = false;
    }
  },

  // Switch the sidebar to the per-agent detail fanout and show Thoughts first.
  openAgent(id, name) {
    this.current = { id, name };
    this.stopPoll();
    setAgentDetailContent(name);

    navAgents.classList.add("hidden");
    navAgentDetail.classList.remove("hidden");

    const thoughtsTab = navAgentDetail.querySelector(
      '[data-nav="agent-detail"][data-target="agent-detail-thoughts"]',
    );
    if (thoughtsTab)
      safeSetActive(
        navAgentDetail,
        '[data-nav="agent-detail"][data-target]',
        thoughtsTab,
      );
    safeActivateView("agent-detail-thoughts");
    this.renderDetail("agent-detail-thoughts");
  },

  // Render content for whichever agent-detail tab is active.
  renderDetail(target) {
    this.stopPoll();
    if (!this.current) return;
    if (target === "agent-detail-home") {
      setAgentDetailContent(this.current.name);
      return;
    }
    const fn = DETAIL_RENDERERS[target];
    if (fn) fn(this, target);
  },

  // Deep-link helper: open an agent (and optional detail tab) by id.
  async openById(id, view) {
    navMain.classList.add("hidden");
    navAgents.classList.remove("hidden");
    if (!this.agents) {
      try {
        this.agents = await http.getJSON("/api/agents");
      } catch (_e) {}
    }
    const a = (this.agents || []).find((x) => x.id === id);
    this.openAgent(id, a ? a.name : id);
    const target = `agent-detail-${view || "thoughts"}`;
    const tab = navAgentDetail.querySelector(
      `[data-nav="agent-detail"][data-target="${target}"]`,
    );
    if (tab) {
      safeSetActive(
        navAgentDetail,
        '[data-nav="agent-detail"][data-target]',
        tab,
      );
      safeActivateView(target);
      this.renderDetail(target);
    }
  },
};

/* =====================  Server Manager  ===================== */
// Server health is polled by the library's ServerHealthMonitor; two
// observers colour the main "Server Management" tab and the per-server tabs.
const serverHealth = new ServerHealthMonitor(http);
const serverAction = new ServerActionController({ http });
serverHealth.subscribe((health) => {
  const tab = document.getElementById("btn-server-mgmt");
  if (!tab) return;
  tab.classList.remove("server-up", "server-down", "server-starting");
  const st = ServerHealthMonitor.overallStatus(health);
  if (st === "starting") tab.classList.add("server-starting");
  else if (st === "down") tab.classList.add("server-down");
  else if (st === "up") tab.classList.add("server-up");
});
serverHealth.subscribe((health) => {
  if (!health) return;
  const map = {};
  for (const s of health.servers) map[s.key] = s.status;
  navServers.querySelectorAll("[data-server-key]").forEach((tab) => {
    const status = map[tab.dataset.serverKey] || "unknown";
    tab.classList.remove("server-up", "server-down", "server-starting");
    if (status === "up") tab.classList.add("server-up");
    else if (status === "starting") tab.classList.add("server-starting");
    else if (status === "down") tab.classList.add("server-down");
  });
});

function renderServerSkills(skills) {
  if (!Array.isArray(skills) || skills.length === 0) {
    return '<span class="srv-summary-stamp">-</span>';
  }
  return (
    '<ul class="srv-skills">' +
    skills.map((skill) => `<li>${esc(skill)}</li>`).join("") +
    "</ul>"
  );
}

async function loadServersSummary() {
  const list = document.getElementById("servers-list");
  const stamp = document.getElementById("servers-last-updated");
  if (!list) return;
  list.innerHTML = '<p class="am-dim">Checking&hellip;</p>';
  try {
    const [servers, health] = await Promise.all([
      http.getJSON("/api/servers"),
      http.getJSON("/api/server-health"),
    ]);
    const healthByKey = new Map(
      (health?.servers || []).map((server) => [server.key, server.status]),
    );
    if (!servers.length) {
      list.innerHTML = '<p class="am-dim">No servers registered.</p>';
      return;
    }
    const rows = servers
      .map((server) => {
        const status = healthByKey.get(server.key) || "unknown";
        const badge = `<span class="srv-badge ${status}">${esc(status.toUpperCase())}</span>`;
        const url = server.url || server.health_url || "";
        const link = url
          ? `<a href="${esc(url)}" target="_blank" rel="noopener">${esc(url)}</a>`
          : '<span class="srv-summary-stamp">-</span>';
        return (
          "<tr>" +
          `<td>${badge}</td>` +
          `<td><strong>${esc(server.name)}</strong><br><span class="srv-summary-stamp">${esc(server.note || "")}</span></td>` +
          `<td>${link}</td>` +
          `<td>${renderServerSkills(server.skills)}</td>` +
          "</tr>"
        );
      })
      .join("");
    list.innerHTML =
      '<table class="srv-table"><thead><tr>' +
      "<th>Status</th><th>Server</th><th>URL</th><th>Skills</th>" +
      `</tr></thead><tbody>${rows}</tbody></table>`;
    if (stamp) {
      stamp.textContent = `Updated ${new Date().toLocaleTimeString()}`;
    }
  } catch (e) {
    list.innerHTML = `<p class="msi-line err">Error: ${esc(e.message)}</p>`;
  }
}

const SM = {
  healthPollTimer: null,
  current: null, // { key, name }
  servers: null,
  logController: null,
  served: location.protocol === "http:" || location.protocol === "https:",

  stopPoll() {
    if (this.logController) {
      this.logController.stop();
      this.logController = null;
    }
  },
  stopHealthPoll() {
    if (this.healthPollTimer) {
      clearInterval(this.healthPollTimer);
      this.healthPollTimer = null;
    }
  },
  pollHealth() {
    return serverHealth.poll();
  },

  showServersHome() {
    this.stopPoll();
    this.current = null;
    navServers.classList.remove("hidden");
    safeActivateView("server-management");
    this.loadServerTabs();
    this.pollHealth();
    this.healthPollTimer = setInterval(() => this.pollHealth(), 5000);
  },

  async loadServerTabs() {
    if (!this.served) return;
    if (!this.servers) {
      try {
        this.servers = await http.getJSON("/api/servers");
      } catch (_e) {
        return;
      }
    }
    navServers.querySelectorAll("[data-server-key]").forEach((t) => {
      t.remove();
    });
    if (!this.servers) return;
    for (const s of this.servers)
      navServers.appendChild(tabFactory.buildServerTab(s));
    this.pollHealth(); // colour the freshly-built tabs
  },

  openServer(key, name) {
    this.stopPoll();
    this.stopHealthPoll();
    this.current = { key, name };
    document.getElementById("servers-detail-title").textContent = name;
    const body = document.getElementById("servers-detail-body");
    const meta = (this.servers || []).find((s) => s.key === key) || {};
    const startLabels = {
      executor: "Start Executor Server",
      "logger-api": "Start Logger API",
      "frita-executor": "Start Frita Executor",
      dashboard: "Re-start Dashboard Server",
    };
    body.innerHTML =
      (meta.note ? `<p class="srv-note">${esc(meta.note)}</p>` : "") +
      '<div class="srv-status starting" id="srv-status"><span class="srv-led"></span><span id="srv-status-text">checking…</span></div>' +
      '<input class="srv-filter" id="srv-filter" placeholder="Filter log lines (e.g. error)…" />' +
      (startLabels[key]
        ? '<button class="srv-start-btn" id="srv-start-btn">' +
          startLabels[key] +
          "</button>"
        : "") +
      '<div id="srv-console-host"></div>';
    safeActivateView("servers-detail");

    const statusEl = body.querySelector("#srv-status");
    const statusText = body.querySelector("#srv-status-text");
    const filterEl = body.querySelector("#srv-filter");
    const startBtn = body.querySelector("#srv-start-btn");
    const view = DomConsoleView.mount(
      body.querySelector("#srv-console-host"),
      "srv",
    );
    const innerEl = body.querySelector(".msi-inner");

    // Log filter: hide non-matching lines; re-apply when new rows arrive.
    const applyFilter = () => {
      const q = filterEl.value.trim().toLowerCase();
      innerEl.querySelectorAll(".msi-entry").forEach((el) => {
        el.style.display =
          !q || el.textContent.toLowerCase().includes(q) ? "" : "none";
      });
    };
    filterEl.addEventListener("input", applyFilter);
    new MutationObserver(applyFilter).observe(innerEl, { childList: true });

    if (startBtn) {
      startBtn.addEventListener("click", async () => {
        startBtn.disabled = true;
        statusEl.className = "srv-status starting";
        statusText.textContent = `STARTING... — launching ${name.toLowerCase()}`;
        const res = await serverAction.start(key);
        if (res.ok) {
          view.writeHtml(
            '<div class="msi-entry"><span class="hdr">start action</span> ' +
              esc(res.text || "OK") +
              "</div>",
          );
          view.scrollToBottom();
        } else {
          statusText.textContent = `START FAILED — ${esc(res.text)}`;
          statusEl.className = "srv-status down";
          startBtn.disabled = false;
        }
      });
    }

    // The ServerLogController polls /api/server-logs (3s, dedup by seq) and
    // reports health via onStatus → the LED + start-button enablement.
    const onStatus = (st) => {
      let cls = "srv-status";
      if (st.kind === "up") cls += " up";
      else if (st.kind === "starting") cls += " starting";
      else if (st.kind === "down") cls += " down";
      statusEl.className = cls;
      statusText.textContent = st.label + st.text;
      if (startBtn) {
        if (st.kind === "up" || st.kind === "starting")
          startBtn.disabled = true;
        else if (st.kind === "down") startBtn.disabled = false;
      }
    };
    this.logController = new ServerLogController({
      http,
      view,
      serverKey: key,
      onStatus,
    });
    this.logController.start();
  },
};

// Initial health poll on page load
SM.pollHealth();
SM.healthPollTimer = setInterval(() => SM.pollHealth(), 10000);

/* =====================  SSH Connections  ===================== */
// SSH health uses the same ServerHealthMonitor (different endpoint); the
// payload has a `connections` array (status only up/down, no "starting").
const connHealth = new ServerHealthMonitor(http, "/api/ssh-connection-health");
const connTest = new ConnectionTestController({ http });
connHealth.subscribe((health) => {
  const tab = document.getElementById("btn-ssh-connections");
  if (!tab) return;
  tab.classList.remove("server-up", "server-down", "server-starting");
  if (!health) return;
  tab.classList.add(health.any_down ? "server-down" : "server-up");
});
connHealth.subscribe((health) => {
  if (!health) return;
  const map = {};
  for (const c of health.connections) map[c.key] = c.status;
  navSSH.querySelectorAll("[data-conn-key]").forEach((tab) => {
    const status = map[tab.dataset.connKey] || "unknown";
    tab.classList.remove("server-up", "server-down", "server-starting");
    if (status === "up") tab.classList.add("server-up");
    else if (status === "down") tab.classList.add("server-down");
  });
});

const SSHM = {
  healthPollTimer: null,
  current: null, // { key, name }
  connections: null,
  logController: null,

  stopPoll() {
    if (this.logController) {
      this.logController.stop();
      this.logController = null;
    }
  },
  stopHealthPoll() {
    if (this.healthPollTimer) {
      clearInterval(this.healthPollTimer);
      this.healthPollTimer = null;
    }
  },
  pollHealth() {
    return connHealth.poll();
  },

  showConnectionsHome() {
    this.stopPoll();
    this.current = null;
    navSSH.classList.remove("hidden");
    safeActivateView("ssh-connections");
    this.loadConnectionTabs();
    this.pollHealth();
  },

  async loadConnectionTabs() {
    if (!this.connections) {
      try {
        this.connections = await http.getJSON("/api/ssh-connections");
      } catch (_e) {
        return;
      }
    }
    navSSH.querySelectorAll("[data-conn-key]").forEach((t) => {
      t.remove();
    });
    if (!this.connections) return;
    for (const c of this.connections)
      navSSH.appendChild(tabFactory.buildConnectionTab(c));
    this.pollHealth(); // colour the freshly-built tabs
  },

  openConnection(key, name) {
    this.stopPoll();
    this.current = { key, name };
    document.getElementById("ssh-connection-detail-title").textContent = name;
    const body = document.getElementById("ssh-connection-detail-body");
    const meta = (this.connections || []).find((c) => c.key === key) || {};
    body.innerHTML =
      (meta.note ? `<p class="srv-note">${esc(meta.note)}</p>` : "") +
      '<div class="srv-status starting" id="ssh-status"><span class="srv-led"></span><span id="ssh-status-text">checking…</span></div>' +
      '<input class="srv-filter" id="ssh-filter" placeholder="Filter log lines (e.g. timed out)…" />' +
      '<button class="srv-start-btn" id="ssh-test-btn">Test Connection</button>' +
      '<div id="ssh-console-host"></div>';
    safeActivateView("ssh-connection-detail");

    const statusEl = body.querySelector("#ssh-status");
    const statusText = body.querySelector("#ssh-status-text");
    const filterEl = body.querySelector("#ssh-filter");
    const testBtn = body.querySelector("#ssh-test-btn");
    const view = DomConsoleView.mount(
      body.querySelector("#ssh-console-host"),
      "ssh",
    );
    const innerEl = body.querySelector(".msi-inner");

    const applyFilter = () => {
      const q = filterEl.value.trim().toLowerCase();
      innerEl.querySelectorAll(".msi-entry").forEach((el) => {
        el.style.display =
          !q || el.textContent.toLowerCase().includes(q) ? "" : "none";
      });
    };
    filterEl.addEventListener("input", applyFilter);
    new MutationObserver(applyFilter).observe(innerEl, { childList: true });

    // onStatus drives the LED from classifyConnectionStatus (CONNECTED/DOWN/checking…).
    const onStatus = (st) => {
      let cls = "srv-status";
      if (st.kind === "up") cls += " up";
      else if (st.kind === "down") cls += " down";
      else cls += " starting";
      statusEl.className = cls;
      statusText.textContent = st.label + st.text;
    };
    this.logController = new ConnectionLogController({
      http,
      view,
      connKey: key,
      onStatus,
    });

    testBtn.addEventListener("click", async () => {
      testBtn.disabled = true;
      statusEl.className = "srv-status starting";
      statusText.textContent = `TESTING… — ssh ${name.toLowerCase()}`;
      const res = await connTest.test(key);
      if (res.failed) {
        statusEl.className = "srv-status down";
        statusText.textContent = `TEST FAILED — ${esc(res.text)}`;
      } else {
        onStatus(
          res.ok
            ? { kind: "up", text: res.text, label: "CONNECTED — " }
            : { kind: "down", text: res.text, label: "DOWN — " },
        );
        this.pollHealth();
      }
      testBtn.disabled = false;
      await this.logController.poll();
    });

    this.logController.start();
  },
};

// Initial health poll on page load
SSHM.pollHealth();
SSHM.healthPollTimer = setInterval(() => SSHM.pollHealth(), 15000);

document
  .getElementById("servers-refresh-btn")
  ?.addEventListener("click", () => void loadServersSummary());

/* =====================  ROL Finance Reports  =====================
       One tab per report directory under ~/rol_finances/readable_documents/
       bank_statements/january/. Tabs + views are built once from
       /api/rol-finance-reports, which reports whether each report.html
       exists on disk. Missing reports get a red tab and a placeholder view
       instead of an iframe, so the UI never silently fails. */
const RF = new RolFinanceReportsController({
  http,
  nav: navRolFinanceReports,
  viewsContainer: document.getElementById("rol-finance-reports-views"),
  activateView: safeActivateView,
  setActiveTab: (tab) => safeSetActive(navRolFinanceReports, ".tab", tab),
});

/* =====================  Agent tab status colors  ===================== */
function setAgentTabStatus(agentId, status) {
  const tab = navAgents.querySelector(`.agent-tab[data-agent-id="${agentId}"]`);
  if (!tab) return;
  tab.classList.remove("agent-active", "agent-error");
  if (status === "active") tab.classList.add("agent-active");
  else if (status === "error") tab.classList.add("agent-error");
}

// Colour agent sidebar tabs from /api/agent-activity every 5s.
new AgentActivityPoller({ http, setStatus: setAgentTabStatus }).start();

// Structural health check — polls /api/agent-health every 30s.
// ok=false adds agent-health-error (red); ok=true clears it.
// Uses a separate class so it doesn't get wiped by the activity poller.
function setAgentTabHealth(agentId, ok) {
  const tab = navAgents.querySelector(`.agent-tab[data-agent-id="${agentId}"]`);
  if (!tab) return;
  tab.classList.toggle("agent-health-error", !ok);
}
new AgentHealthPoller({ http, setHealth: setAgentTabHealth }).start();

/* =====================  Code-change restart alert  ===================== */
// Blink the Agents tab + prompt to restart when the dashboard's own source
// changes on disk (polls /api/code-status every 15s).
new CodeChangeAlert({ http }).start();

/* =====================  Deep-linking  =====================
       ?agent=<id>&view=thoughts|messages|tool-calls|chat-interface
       ?view=rol-finance-reports  -> Project Plans > ROL Finance > Reports  */
(function deepLink() {
  const q = new URLSearchParams(location.search);
  const agent = q.get("agent");
  if (agent) {
    AM.openById(agent, q.get("view") || "thoughts");
    return;
  }
  if (q.get("view") === "rol-finance-reports") {
    navMain.classList.add("hidden");
    navRolFinanceReports.classList.remove("hidden");
    RF.openReports();
  }
})();
