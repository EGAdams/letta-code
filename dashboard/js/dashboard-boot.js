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
  AgentsRouterRenderer,
  BrowserSpeechRecognitionListener,
  ChatDetailRenderer,
  CodeChangeAlert,
  ConnectionLogController,
  ConnectionTestController,
  DocumentPipelineController,
  DomConsoleView,
  DomDocumentPipelineView,
  DomTabFactory,
  DomVendorReviewView,
  EdgeTtsSpeechSynthesizer,
  FetchHttpClient,
  InputOptionsRenderer,
  PrinterRepairController,
  RolFinanceReportsController,
  ServerActionController,
  ServerHealthMonitor,
  ServerLogController,
  StreamDetailRenderer,
  VendorReviewController,
  VisionHaltAlert,
} from "./implementation/index.js";
import { StatementReviewDialog } from "./implementation/statement-review-dialog.js";

// One shared HttpClient (Adapter over fetch) used by AM / SM / SSHM / RF.
const http = new FetchHttpClient();
const printerRepair = new PrinterRepairController({ http });

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
const navScanners = document.getElementById("nav-scanners");
const navModelStats = document.getElementById("nav-model-stats");
const navPcMonitor = document.getElementById("nav-pc-monitor");
const startupOverlay = document.getElementById("startup-overlay");
const startupStatusText = document.getElementById("startup-status-text");
const startupProgressBar = document.getElementById("startup-progress-bar");
const startupConsole = document.getElementById("startup-console");

const startupGate = (() => {
  const FILL_PHASE_MS = 2500;
  const GREEN_PHASE_MS = 3000;
  const FINISH_DELAY_MS = FILL_PHASE_MS + GREEN_PHASE_MS;
  const LOG_SPACING_MS = 75;
  const tasks = [
    {
      key: "server-registry",
      label: "Loading server registry",
      detail: "Fetching server definitions for Server Management tabs",
    },
    {
      key: "server-health",
      label: "Checking server health",
      detail: "Running initial Server Management health check",
    },
    {
      key: "ssh-registry",
      label: "Loading SSH connections",
      detail: "Fetching SSH connection definitions",
    },
    {
      key: "ssh-health",
      label: "Checking SSH connectivity",
      detail: "Running initial SSH connection health check",
    },
  ];
  const completed = new Set();
  let released = false;
  let finishTimer = null;
  let greenTimer = null;
  let logChain = Promise.resolve();
  let hasLogged = false;

  function resetBar() {
    if (!startupProgressBar) return;
    startupProgressBar.style.transition = "none";
    startupProgressBar.style.width = "0%";
    startupProgressBar.offsetHeight;
    startupProgressBar.style.transition = "";
  }

  function animateCompletionBar() {
    if (!startupProgressBar) return;
    startupProgressBar.style.transition = "none";
    startupProgressBar.style.width = "0%";
    startupProgressBar.offsetHeight;
    startupProgressBar.style.transition = `width ${FILL_PHASE_MS}ms linear`;
    startupProgressBar.style.width = "100%";
  }

  function renderProgress(currentLabel) {
    if (startupStatusText) {
      startupStatusText.textContent = currentLabel;
    }
  }

  function log(text, className = "") {
    if (!startupConsole) return;
    const line = document.createElement("div");
    if (className) line.className = className;
    line.textContent = `[${new Date().toLocaleTimeString()}] ${text}`;
    startupConsole.appendChild(line);
    startupConsole.scrollTop = startupConsole.scrollHeight;
    return line;
  }

  function writeLine(text, className = "") {
    const waitMs = hasLogged ? LOG_SPACING_MS : 0;
    hasLogged = true;
    logChain = logChain
      .then(
        () =>
          new Promise((resolve) => {
            window.setTimeout(resolve, waitMs);
          }),
      )
      .then(() => log(text, className));
    return logChain;
  }

  return {
    start() {
      document.body.classList.add("startup-loading");
      startupOverlay?.classList.remove("startup-complete");
      if (finishTimer) window.clearTimeout(finishTimer);
      if (greenTimer) window.clearTimeout(greenTimer);
      finishTimer = null;
      greenTimer = null;
      logChain = Promise.resolve();
      hasLogged = false;
      resetBar();
      renderProgress("Running Dashboard checks...");
      writeLine("Checking server and SSH connections...");
    },
    complete(key, text) {
      if (released || completed.has(key)) return;
      const task = tasks.find((entry) => entry.key === key);
      completed.add(key);
      log(text || `${task?.label || key} complete.`);
      renderProgress(task?.detail || "Advancing startup checks");
      if (completed.size === tasks.length) {
        this.finish();
      }
    },
    fail(key, error) {
      if (released || completed.has(key)) return;
      completed.add(key);
      const task = tasks.find((entry) => entry.key === key);
      log(
        `${task?.label || key} failed: ${error?.message || error || "Unknown error"}`,
      );
      renderProgress(task?.detail || "Advancing startup checks");
      if (completed.size === tasks.length) {
        this.finish();
      }
    },
    writeLine(text, className = "") {
      return writeLine(text, className);
    },
    async finish() {
      if (released) return;
      released = true;
      renderProgress("Running Dashboard checks...");
      animateCompletionBar();
      greenTimer = window.setTimeout(() => {
        startupOverlay?.classList.add("startup-complete");
        if (startupStatusText) {
          startupStatusText.textContent = "Finished system check.";
        }
        const finalLine = log("finished system check.", "startup-final-line");
        finalLine?.classList.add("startup-blink");
      }, FILL_PHASE_MS);
      await new Promise((resolve) => {
        finishTimer = window.setTimeout(resolve, FINISH_DELAY_MS);
      });
      await logChain;
      document.body.classList.remove("startup-loading");
      startupOverlay?.classList.add("hidden");
    },
  };
})();

const agentGate = (() => {
  const FILL_PHASE_MS = 2500;
  const GREEN_PHASE_MS = 3000;
  const FINISH_DELAY_MS = FILL_PHASE_MS + GREEN_PHASE_MS;
  const LOG_SPACING_MS = 75;
  const tasks = [
    {
      key: "agents",
      label: "Loading agents",
      detail: "Fetching agent definitions",
    },
  ];
  const completed = new Set();
  let released = false;
  let finishTimer = null;
  let greenTimer = null;
  let logChain = Promise.resolve();
  let hasLogged = false;

  function resetBar() {
    if (!startupProgressBar) return;
    startupProgressBar.style.transition = "none";
    startupProgressBar.style.width = "0%";
    startupProgressBar.offsetHeight;
    startupProgressBar.style.transition = "";
  }

  function animateCompletionBar() {
    if (!startupProgressBar) return;
    startupProgressBar.style.transition = "none";
    startupProgressBar.style.width = "0%";
    startupProgressBar.offsetHeight;
    startupProgressBar.style.transition = `width ${FILL_PHASE_MS}ms linear`;
    startupProgressBar.style.width = "100%";
  }

  function renderProgress(currentLabel) {
    if (startupStatusText) {
      startupStatusText.textContent = currentLabel;
    }
  }

  function log(text, className = "") {
    if (!startupConsole) return;
    const line = document.createElement("div");
    if (className) line.className = className;
    line.textContent = `[${new Date().toLocaleTimeString()}] ${text}`;
    startupConsole.appendChild(line);
    startupConsole.scrollTop = startupConsole.scrollHeight;
    return line;
  }

  function writeLine(text, className = "") {
    const waitMs = hasLogged ? LOG_SPACING_MS : 0;
    hasLogged = true;
    logChain = logChain
      .then(
        () =>
          new Promise((resolve) => {
            window.setTimeout(resolve, waitMs);
          }),
      )
      .then(() => log(text, className));
    return logChain;
  }

  return {
    start() {
      document.body.classList.add("startup-loading");
      startupOverlay?.classList.remove("hidden");
      startupOverlay?.classList.remove("startup-complete");
      if (finishTimer) window.clearTimeout(finishTimer);
      if (greenTimer) window.clearTimeout(greenTimer);
      finishTimer = null;
      greenTimer = null;
      logChain = Promise.resolve();
      hasLogged = false;
      completed.clear();
      released = false;
      if (startupConsole) startupConsole.innerHTML = "";
      resetBar();
      renderProgress("Running Agent Management checks...");
      writeLine("Checking agent roster...");
    },
    complete(key, text) {
      if (released || completed.has(key)) return;
      const task = tasks.find((entry) => entry.key === key);
      completed.add(key);
      log(text || `${task?.label || key} complete.`);
      renderProgress(task?.detail || "Advancing agent checks");
      if (completed.size === tasks.length) {
        this.finish();
      }
    },
    fail(key, error) {
      if (released || completed.has(key)) return;
      completed.add(key);
      const task = tasks.find((entry) => entry.key === key);
      log(
        `${task?.label || key} failed: ${error?.message || error || "Unknown error"}`,
      );
      renderProgress(task?.detail || "Advancing agent checks");
      if (completed.size === tasks.length) {
        this.finish();
      }
    },
    writeLine(text, className = "") {
      return writeLine(text, className);
    },
    async finish() {
      if (released) return;
      released = true;
      renderProgress("Running Agent Management checks...");
      animateCompletionBar();
      greenTimer = window.setTimeout(() => {
        startupOverlay?.classList.add("startup-complete");
        if (startupStatusText) {
          startupStatusText.textContent = "Finished loading agents.";
        }
        const finalLine = log("finished loading agents.", "startup-final-line");
        finalLine?.classList.add("startup-blink");
      }, FILL_PHASE_MS);
      await new Promise((resolve) => {
        finishTimer = window.setTimeout(resolve, FINISH_DELAY_MS);
      });
      await logChain;
      document.body.classList.remove("startup-loading");
      startupOverlay?.classList.add("hidden");
    },
  };
})();

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
  // New Records panel lives outside the .view hierarchy (sibling of
  // #rol-finance-reports-views); show it only when a ROL Finance view is active.
  const recentScansPanel = document.getElementById("rol-finance-recent-scans");
  if (recentScansPanel)
    recentScansPanel.hidden = !next.startsWith("rol-finance");
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

      if (target === "model-stats" && navModelStats) {
        navMain.classList.add("hidden");
        navModelStats.classList.remove("hidden");
        safeActivateView("model-stats");
        MS.open();
        return;
      }

      if (target === "pc-monitor" && navPcMonitor) {
        navMain.classList.add("hidden");
        navPcMonitor.classList.remove("hidden");
        safeActivateView("pc-monitor");
        PCM.open();
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
          RF.openReports().then(() => RF.refreshStatus());
          return;
        }
        if (tab.dataset.target === "rol-finance-scanners") {
          safeSetActive(
            navRolFinance,
            '[data-nav="rol-finance"][data-target]',
            tab,
          );
          navRolFinance.classList.add("hidden");
          navScanners.classList.remove("hidden");
          const freezerTab = navScanners.querySelector(
            '[data-nav="scanners"][data-target="scanners-freezer"]',
          );
          if (freezerTab)
            safeSetActive(
              navScanners,
              '[data-nav="scanners"][data-target]',
              freezerTab,
            );
          safeActivateView("scanners-freezer");
          scannerControllers.freezer?.startMonitor();
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
    if (tab.dataset.recentReport) {
      RF.openRecentReport();
      return;
    }
    if (tab.dataset.scanner) {
      RF.openScannerReport(tab.dataset.scanner);
      return;
    }
    if (tab.dataset.monthKey) {
      RF.openMonth(tab.dataset.monthKey).then(() => RF.refreshStatus());
      return;
    }
    if (tab.dataset.reportKey) {
      RF.selectReport(tab.dataset.reportKey);
    }
  });

  // ROL Finance Scanners sub-nav (Freezer Scanner / Window Scanner).
  navScanners
    .querySelectorAll('[data-nav="scanners"][data-target]')
    .forEach((tab) => {
      tab.addEventListener("click", () => {
        safeSetActive(navScanners, '[data-nav="scanners"][data-target]', tab);
        safeActivateView(tab.dataset.target);
        // Only poll the scanner whose tab is showing.
        stopAllScannerMonitors();
        if (tab.dataset.target === "scanners-freezer") {
          scannerControllers.freezer?.startMonitor();
        }
        if (tab.dataset.target === "scanners-vendor-review") {
          vendorReviewController?.refresh();
        }
      });
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

  // Back from the ROL Finance Scanners sub-nav -> ROL Finance sub-nav.
  const backScanners = document.getElementById("btn-back-scanners");
  if (backScanners) {
    backScanners.addEventListener("click", () => {
      stopAllScannerMonitors();
      navScanners.classList.add("hidden");
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

/* =====================  Model Stats  =====================
       Per-OAuth/CLI session token usage. Sub-nav tab per source; each shows
       usage windows as progress bars (red at 100% with reset time), plus a
       Rate of Change bar (burn rate) and a slow-leak badge. Tab colors
       reflect status so an exhausted account is caught at a glance. */

/* The Rate of Change row. `rate` comes straight from /api/model-stats:
   pct_per_hour (raw %-points/hour), burn_multiple (vs the window's replenish
   pace — 1.0× is sustainable forever), bar_percent (pre-scaled so 50% width
   = 1.0×), warn (burn ≥ server threshold → blink). While history is still
   too short the server sends {available:false, reason} and we show that
   instead of a misleading empty bar. */
function renderRateOfChange(rate) {
  if (!rate) return "";
  const tip =
    `Consumed ${rate.pct_per_hour ?? "?"}% of the ${rate.window_label || "quota"} limit per hour ` +
    `over the last ${rate.window_minutes || 30} min. 1.0× pace means the window refills as fast as ` +
    `you spend; sustained use above 1.0× eventually maxes out. Blinks yellow at ${rate.warn_at_multiple}×.`;
  let h = `<div class="ms-window" title="${esc(tip)}"><div class="ms-window-head"><span>Rate of change</span>`;
  if (!rate.available) {
    h += `<span class="am-dim">${esc(rate.reason || "gathering data…")}</span></div>`;
    h +=
      '<div class="ms-bar"><div class="ms-bar-fill" style="width:0%"></div></div></div>';
    return h;
  }
  const rp = Math.max(0, Math.min(100, rate.bar_percent || 0));
  const fill = rate.warn ? "#f9a825" : "#43a047";
  const blink = rate.warn ? " ms-blink-warn" : "";
  h += `<span>${rate.pct_per_hour}%/hr · ${rate.burn_multiple}× pace${rate.warn ? " ⚠" : ""}</span></div>`;
  h += `<div class="ms-bar"><div class="ms-bar-fill${blink}" style="width:${rp}%;background:${fill}"></div></div></div>`;
  return h;
}

/* Live reset countdown. renderModelStats stamps spans with
   data-countdown-until (unix seconds); one shared ticker keeps them counting
   down each second and re-fetches the card once a deadline passes so the tab
   flips back to green on its own. */
function resetEpoch(when) {
  if (!when) return null;
  if (typeof when === "number") return when;
  const t = Date.parse(when);
  return Number.isNaN(t) ? null : t / 1000;
}

function fmtCountdown(secs) {
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = secs % 60;
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  return h ? `${h}:${mm}:${ss}` : `${m}:${ss}`;
}

setInterval(() => {
  document.querySelectorAll("[data-countdown-until]").forEach((el) => {
    const secs = Math.round(
      Number(el.dataset.countdownUntil) - Date.now() / 1000,
    );
    if (secs > 0) {
      el.textContent = `${fmtCountdown(secs)} until reset`;
    } else if (!el.dataset.countdownDone) {
      el.dataset.countdownDone = "1";
      el.textContent = "resetting now…";
      if (MS.current) {
        MS.show(MS.current);
        MS.pollColors();
      }
    }
  });
}, 1000);

function renderModelStats(d) {
  if (!d || d.ok === false) {
    return `<p class="am-warn">${esc(d?.error || "no data")}</p>`;
  }
  const dot =
    d.status === "down"
      ? "#e53935"
      : d.status === "concern"
        ? "#f9a825"
        : "#43a047";
  let h = '<div class="ms-card">';
  h += `<h3>${esc(d.label)} <span style="color:${dot}">●</span></h3>`;
  if (d.rate_limited) {
    // Provider-side 429: say so loudly, with the local reset time and a live
    // countdown — the whole point is never having to diagnose this from a
    // terminal again.
    const until = Number(d.rate_limited_until) || null;
    const at = until
      ? new Date(until * 1000).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        })
      : null;
    h += `<p class="am-warn ms-rate-limited">⛔ RATE LIMITED (HTTP 429)${
      at
        ? ` — resets at ${at} · <span data-countdown-until="${until}">…</span>`
        : " — reset time not reported"
    }</p>`;
  }
  if (d.model) h += `<p><b>Model:</b> <code>${esc(d.model)}</code></p>`;
  if (d.detail) h += `<p class="am-dim">${esc(d.detail)}</p>`;
  for (const w of d.windows || []) {
    if (w.unavailable) {
      h += `<div class="ms-window"><div class="ms-window-head"><span>${esc(w.label)}</span><span class="am-dim">${esc(w.note || "not reported")}</span></div></div>`;
      continue;
    }
    const pct = Math.max(0, Math.min(100, w.used_percent || 0));
    const bar = pct >= 100 ? "#e53935" : pct >= 80 ? "#f9a825" : "#43a047";
    const resets = w.resets_in ? ` · resets ${esc(w.resets_in)}` : "";
    h += `<div class="ms-window"><div class="ms-window-head"><span>${esc(w.label)}</span><span>${pct}%${resets}</span></div>`;
    h += `<div class="ms-bar"><div class="ms-bar-fill" style="width:${pct}%;background:${bar}"></div></div></div>`;
  }
  /* Rate of Change — server-computed burn rate of the primary quota window
     (%-points/hour vs the window's replenish pace; see server.py's
     "Model usage" section for the math). Half a bar = sustainable 1.0× pace;
     the fill blinks yellow when burn ≥ the server's warn threshold
     (MODEL_RATE_WARN_BURN_MULTIPLE). */
  h += renderRateOfChange(d.rate);
  if (d.leak?.suspected) {
    h += `<p class="ms-leak" title="Usage kept climbing across several consecutive time buckets even though the short-term rate looks calm — the signature of a background drip (leaked poller, stuck loop) rather than a normal work burst.">⚠ ${esc(d.leak.text || "Slow token drain")}</p>`;
  }
  if (d.status === "down" && !d.rate_limited) {
    // Show the reset of the window that's actually maxed (highest used %), not
    // just the first one — e.g. weekly at 100% while the 5-hour just reset.
    const maxed = (d.windows || [])
      .filter((w) => w.resets_in)
      .sort((a, b) => (b.used_percent || 0) - (a.used_percent || 0))[0];
    const maxedEpoch = resetEpoch(maxed?.resets_at);
    h += `<p class="am-warn">MAXED OUT${maxed ? ` — ${esc(maxed.label)} resets ${esc(maxed.resets_in)}` : ""}${maxedEpoch ? ` · <span data-countdown-until="${maxedEpoch}">…</span>` : ""}</p>`;
  }
  if (typeof d.tokens_used === "number") {
    h += `<p><b>Tokens used:</b> ${d.tokens_used.toLocaleString()}${d.cost_usd ? ` · $${d.cost_usd}` : ""}</p>`;
  }
  if (d.as_of) {
    h += `<p class="am-dim">as of ${new Date(d.as_of * 1000).toLocaleString()}</p>`;
  }
  h += "</div>";
  return h;
}

const MS = {
  pollTimer: null,
  stopPoll() {
    if (this.pollTimer) {
      clearInterval(this.pollTimer);
      this.pollTimer = null;
    }
  },
  open() {
    if (!navModelStats) return;
    this.stopPoll();
    const first = navModelStats.querySelector("[data-source]");
    if (first) {
      safeSetActive(
        navModelStats,
        '[data-nav="model-stats"][data-source]',
        first,
      );
      this.show(first.dataset.source);
    }
    this.pollColors();
    this.pollTimer = setInterval(() => {
      if (this.current) this.show(this.current);
      this.pollColors();
    }, 120000);
  },
  async show(key) {
    const body = document.getElementById("model-stats-body");
    if (!body) return;
    this.current = key;
    body.innerHTML = '<p class="am-dim">Loading…</p>';
    try {
      const d = await http.getJSON(
        `/api/model-stats?source=${encodeURIComponent(key)}`,
      );
      if (this.current !== key) return; // a newer selection won the race
      body.innerHTML = renderModelStats(d);
    } catch (e) {
      if (this.current !== key) return;
      body.innerHTML = `<p class="am-warn">Failed to load: ${esc(e.message)}</p>`;
    }
  },
  async pollColors() {
    if (!navModelStats) return;
    const tabs = [...navModelStats.querySelectorAll("[data-source]")];
    await Promise.all(
      tabs.map(async (t) => {
        try {
          const d = await http.getJSON(
            `/api/model-stats?source=${encodeURIComponent(t.dataset.source)}`,
          );
          t.classList.remove("server-up", "server-concern", "server-down");
          if (d.status === "down") t.classList.add("server-down");
          else if (d.status === "concern") t.classList.add("server-concern");
          else t.classList.add("server-up");
        } catch {
          /* leave tab uncolored on transient error */
        }
      }),
    );
  },
};

if (navModelStats) {
  navModelStats.querySelectorAll("[data-source]").forEach((tab) => {
    tab.addEventListener("click", () => {
      safeSetActive(
        navModelStats,
        '[data-nav="model-stats"][data-source]',
        tab,
      );
      safeActivateView("model-stats");
      MS.show(tab.dataset.source);
    });
  });
  const backMS = document.getElementById("btn-back-model-stats");
  if (backMS) {
    backMS.addEventListener("click", () => {
      MS.stopPoll();
      navModelStats.classList.add("hidden");
      navMain.classList.remove("hidden");
      const homeTab = navMain.querySelector(
        '[data-nav="main"][data-target="home"]',
      );
      if (homeTab) {
        safeSetActive(navMain, '[data-nav="main"][data-target]', homeTab);
      }
      safeActivateView("home");
    });
  }
}

/* =====================  PC Monitor  =====================
       One sub-nav tab per machine (Windows 11 / Windows 10 / Moms 46), each
       showing RAM / Hard Drive / Network progress bars from /api/pc-metrics.
       Issue detection: each metric carries level ok|warn|crit — warn blinks
       the PC's tab yellow (the existing .tab-alert animation), crit blinks it
       red (.tab-alert-red). Disk levels come from GB free on the Windows C:
       drive (yellow under 5 GB, red at 2 GB or less). Thresholds live in
       server.py (PC_ALERT_THRESHOLDS, env-tunable) — no frontend change. */
function renderPcMetrics(d) {
  if (!d || d.ok === false) {
    return `<p class="am-warn">${esc(d?.error || "no data")}</p>`;
  }
  let h = '<div class="ms-card">';
  const flag =
    d.level === "crit"
      ? ' <span class="pcm-crit-flag">⚠ critical</span>'
      : d.alert
        ? ' <span class="pcm-alert-flag">⚠ needs attention</span>'
        : "";
  h += `<h3>${esc(d.label)}${flag}</h3>`;
  if (d.note) h += `<p class="am-dim">${esc(d.note)}</p>`;
  if (d.stale) {
    h += `<p class="am-warn">⚠ live sample failed — showing last good reading (${esc(d.stale_error || "")})</p>`;
  }
  for (const m of d.metrics || []) {
    const pct = Math.max(0, Math.min(100, m.percent || 0));
    const fill =
      m.level === "crit"
        ? "#e53935"
        : m.alert
          ? "#f9a825"
          : pct >= 75
            ? "#fb8c00"
            : "#43a047";
    const blink = m.alert ? " ms-blink-warn" : "";
    h += `<div class="ms-window" title="${esc(m.tip || "")}"><div class="ms-window-head"><span>${esc(m.label)}</span><span>${esc(m.text || "")} · ${pct}%${m.alert ? " ⚠" : ""}</span></div>`;
    h += `<div class="ms-bar"><div class="ms-bar-fill${blink}" style="width:${pct}%;background:${fill}"></div></div></div>`;
  }
  if (d.as_of) {
    h += `<p class="am-dim">as of ${new Date(d.as_of * 1000).toLocaleTimeString()}</p>`;
  }
  h += "</div>";
  return h;
}

const PCM = {
  pollTimer: null,
  current: null,
  stopPoll() {
    if (this.pollTimer) {
      clearInterval(this.pollTimer);
      this.pollTimer = null;
    }
  },
  open() {
    if (!navPcMonitor) return;
    this.stopPoll();
    // Windows 11 is the default tab on open.
    const first =
      navPcMonitor.querySelector('[data-pc="win11"]') ||
      navPcMonitor.querySelector("[data-pc]");
    if (first) {
      safeSetActive(navPcMonitor, '[data-nav="pc-monitor"][data-pc]', first);
      this.show(first.dataset.pc);
    }
    this.pollTabs();
    this.pollTimer = setInterval(() => {
      if (this.current) this.show(this.current);
      this.pollTabs();
    }, 15000);
  },
  async show(key) {
    const body = document.getElementById("pc-monitor-body");
    if (!body) return;
    this.current = key;
    // Only show the placeholder on first paint — refreshes swap in place so
    // the bars don't flash every poll tick.
    if (!body.querySelector(".ms-card")) {
      body.innerHTML = '<p class="am-dim">Loading…</p>';
    }
    try {
      const d = await http.getJSON(
        `/api/pc-metrics?pc=${encodeURIComponent(key)}`,
      );
      if (this.current !== key) return; // a newer selection won the race
      body.innerHTML = renderPcMetrics(d);
    } catch (e) {
      if (this.current !== key) return;
      body.innerHTML = `<p class="am-warn">Failed to load: ${esc(e.message)}</p>`;
    }
  },
  // Issue detection: blink a PC's tab yellow on warn, red on crit.
  async pollTabs() {
    if (!navPcMonitor) return;
    const tabs = [...navPcMonitor.querySelectorAll("[data-pc]")];
    await Promise.all(
      tabs.map(async (t) => {
        try {
          const d = await http.getJSON(
            `/api/pc-metrics?pc=${encodeURIComponent(t.dataset.pc)}`,
          );
          const level = d.level || (d.alert ? "warn" : "ok");
          t.classList.toggle("tab-alert", level === "warn");
          t.classList.toggle("tab-alert-red", level === "crit");
        } catch {
          /* leave the tab unflagged on transient error */
        }
      }),
    );
  },
};

if (navPcMonitor) {
  navPcMonitor.querySelectorAll("[data-pc]").forEach((tab) => {
    tab.addEventListener("click", () => {
      safeSetActive(navPcMonitor, '[data-nav="pc-monitor"][data-pc]', tab);
      safeActivateView("pc-monitor");
      PCM.show(tab.dataset.pc);
    });
  });
  const backPcMonitor = document.getElementById("btn-back-pc-monitor");
  if (backPcMonitor) {
    backPcMonitor.addEventListener("click", () => {
      PCM.stopPoll();
      navPcMonitor.classList.add("hidden");
      navMain.classList.remove("hidden");
      const homeTab = navMain.querySelector(
        '[data-nav="main"][data-target="home"]',
      );
      if (homeTab) {
        safeSetActive(navMain, '[data-nav="main"][data-target]', homeTab);
      }
      safeActivateView("home");
    });
  }
}

/* =====================  Voice output (edge-tts via /api/tts)  ==============
       The agents now speak with the same edge-tts en-GB-SoniaNeural voice the
       pickle_cpp scoreboard uses: EdgeTtsSpeechSynthesizer (Decorator over the
       BrowserSpeechSynthesizer facade) POSTs the reply text to /api/tts and
       plays the returned MP3. When the server voice is unavailable (offline,
       edge-tts missing) it falls back to the old Web Speech path with the
       per-agent AgentVoiceCatalog voices. */
const Speech = new EdgeTtsSpeechSynthesizer(window);
Speech.bindVoiceChanges(); // fallback engine: initial pick + re-pick on change

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
// The Input Options panel auto-starts a background letta-code pty session
// (see attachTerminalPanel), so its previous session must be torn down
// before rebuilding — otherwise every reopen of the tab leaks another
// bash+letta process/websocket.
let activeInputOptionsTerminal = null;
const renderInputOptions = (am, target) => {
  if (activeInputOptionsTerminal) {
    try {
      activeInputOptionsTerminal.dispose();
    } catch {
      /* already gone */
    }
    activeInputOptionsTerminal = null;
  }
  const api = new InputOptionsRenderer({
    http,
    speech: Speech,
    agentName: am.current.name,
    agentId: am.current.id,
    onStatus: setAgentTabStatus,
  }).render(target, am.current.id);
  if (api) activeInputOptionsTerminal = api.terminal;
  return api;
};

// Long-lived across renders/navigation (unlike the renderers above, which are
// rebuilt fresh on every open) so "Start Listening" keeps listening straight
// through the hand-off to a detected agent's Input Options page — only the
// callbacks get re-claimed per render, via setCallbacks() inside
// AgentsRouterRenderer. See continuous-listener.interface.js.
const routerListener = new BrowserSpeechRecognitionListener();

const resolveAgentIdByName = (name) => {
  const match = (AM.agents || []).find(
    (a) => a.name.toLowerCase() === String(name).toLowerCase(),
  );
  return match ? match.id : null;
};

// Opens the detected agent's Input Options page and hands back its render()
// api (setText/appendText) so the router can transfer the remainder text.
const openAgentForRouter = (id) => AM.openById(id, "input-options");

const renderAgentsRouter = (target) =>
  new AgentsRouterRenderer({
    http,
    listener: routerListener,
    resolveAgentId: resolveAgentIdByName,
    openAgent: openAgentForRouter,
    onStatus: setAgentTabStatus,
  }).render(target);

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
        navAgents.appendChild(tabFactory.buildAgentTab(a));
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

  // Render content for whichever agent-detail tab is active. Returns whatever
  // the renderer's render() returns (e.g. InputOptionsRenderer's {send,
  // setText, appendText, ...} api), so deep-link callers like the Agents-home
  // router can reach the freshly-rendered panel without touching DOM globals.
  renderDetail(target) {
    this.stopPoll();
    if (!this.current) return undefined;
    if (target === "agent-detail-home") {
      setAgentDetailContent(this.current.name);
      return undefined;
    }
    const fn = DETAIL_RENDERERS[target];
    return fn ? fn(this, target) : undefined;
  },

  // Deep-link helper: open an agent (and optional detail tab) by id. Returns
  // the render() result for the requested view (see renderDetail above).
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
      return this.renderDetail(target);
    }
    return undefined;
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
  tab.classList.remove(
    "server-up",
    "server-down",
    "server-starting",
    "server-concern",
  );
  const st = ServerHealthMonitor.overallStatus(health);
  if (st === "starting") tab.classList.add("server-starting");
  else if (st === "concern") tab.classList.add("server-concern");
  else if (st === "down") tab.classList.add("server-down");
  else if (st === "up") tab.classList.add("server-up");
});
serverHealth.subscribe((health) => {
  if (!health) return;
  const byKey = {};
  for (const s of health.servers) byKey[s.key] = s;
  navServers.querySelectorAll("[data-server-key]").forEach((tab) => {
    const s = byKey[tab.dataset.serverKey] || {};
    const status = s.status || "unknown";
    tab.classList.remove(
      "server-up",
      "server-down",
      "server-starting",
      "server-concern",
      "server-stale",
    );
    if (status === "up") tab.classList.add("server-up");
    else if (status === "starting") tab.classList.add("server-starting");
    else if (status === "concern") tab.classList.add("server-concern");
    else if (status === "down") tab.classList.add("server-down");
    // Indicator #3: stale outages blink to draw the eye; tooltip shows how long
    // it's been down and whether it's just a symptom of a down dependency (#1).
    if (s.stale) tab.classList.add("server-stale");
    const bits = [];
    if (s.blocked_by) bits.push(`blocked by ${s.blocked_by}`);
    if (s.down_for_seconds)
      bits.push(`down for ${fmtDownFor(s.down_for_seconds)}`);
    if (s.container_status) bits.push(s.container_status);
    tab.title = bits.join(" · ");
  });
});

// Compact "down for" duration: 45s / 12m / 3h 4m.
function fmtDownFor(sec) {
  if (sec < 60) return `${sec}s`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m`;
  return `${Math.floor(sec / 3600)}h ${Math.floor((sec % 3600) / 60)}m`;
}

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
    // Every server gets a Restart button, always enabled, so the user never has
    // to drop to the command line. The backend (/api/server-action action:restart)
    // dispatches to a per-server handler (systemd --user, SSH, or redeploy).
    body.innerHTML =
      (meta.note ? `<p class="srv-note">${esc(meta.note)}</p>` : "") +
      '<div class="srv-status starting" id="srv-status"><span class="srv-led"></span><span id="srv-status-text">checking…</span></div>' +
      '<input class="srv-filter" id="srv-filter" placeholder="Filter log lines (e.g. error)…" />' +
      `<button class="srv-start-btn" id="srv-restart-btn">Restart ${esc(name)}</button>` +
      '<div id="srv-console-host"></div>';
    safeActivateView("servers-detail");

    const statusEl = body.querySelector("#srv-status");
    const statusText = body.querySelector("#srv-status-text");
    const filterEl = body.querySelector("#srv-filter");
    const restartBtn = body.querySelector("#srv-restart-btn");
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

    restartBtn.addEventListener("click", async () => {
      restartBtn.disabled = true;
      statusEl.className = "srv-status starting";
      statusText.textContent = `RESTARTING... — ${name.toLowerCase()}`;
      const res = await serverAction.restart(key);
      if (res.ok) {
        view.writeHtml(
          '<div class="msi-entry"><span class="hdr">restart action</span> ' +
            esc(res.text || "OK") +
            "</div>",
        );
        view.scrollToBottom();
      } else {
        statusText.textContent = `RESTART FAILED — ${esc(res.text)}`;
        statusEl.className = "srv-status down";
      }
      restartBtn.disabled = false;
    });

    // The ServerLogController polls /api/server-logs (3s, dedup by seq) and
    // reports health via onStatus → the detail-panel LED. The Restart button
    // stays enabled regardless of status (the user can always restart).
    const onStatus = (st) => {
      let cls = "srv-status";
      if (st.kind === "up") cls += " up";
      else if (st.kind === "starting") cls += " starting";
      else if (st.kind === "concern") cls += " concern";
      else if (st.kind === "down") cls += " down";
      statusEl.className = cls;
      statusText.textContent = st.label + st.text;
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

async function preloadStartupChecks() {
  startupGate.start();

  const runTask = async (key, work, formatSuccess, onError = null) => {
    const TASK_TIMEOUT = 10000; // 10-second timeout per task
    try {
      const result = await Promise.race([
        work(),
        new Promise((_, reject) =>
          setTimeout(
            () => reject(new Error(`Task timeout after ${TASK_TIMEOUT}ms`)),
            TASK_TIMEOUT,
          ),
        ),
      ]);
      startupGate.complete(key, formatSuccess(result));
      return result;
    } catch (error) {
      if (typeof onError === "function") onError(error);
      startupGate.fail(key, error);
      return null;
    }
  };

  const serverRegistryPromise = runTask(
    "server-registry",
    async () => {
      if (SM.servers) return SM.servers;
      SM.servers = await http.getJSON("/api/servers");
      return SM.servers;
    },
    (servers) =>
      `Loaded ${servers?.length || 0} server definition${servers?.length === 1 ? "" : "s"}.`,
  );

  const sshRegistryPromise = runTask(
    "ssh-registry",
    async () => {
      if (SSHM.connections) return SSHM.connections;
      SSHM.connections = await http.getJSON("/api/ssh-connections");
      return SSHM.connections;
    },
    (connections) =>
      `Loaded ${connections?.length || 0} SSH connection${connections?.length === 1 ? "" : "s"}.`,
  );

  const serverHealthPromise = runTask(
    "server-health",
    async () => {
      startupGate.writeLine("Calling /api/server-health...");
      serverHealth.health = await serverHealth.fetchHealth();
      startupGate.writeLine("Got response from /api/server-health");
      serverHealth.notify();
      return serverHealth.health;
    },
    (health) => {
      const count = health?.servers?.length || 0;
      const rows = health?.servers || [];
      const nameByKey = new Map(
        (SM.servers || []).map((server) => [server.key, server.name]),
      );
      for (const server of rows) {
        startupGate.writeLine(
          `Server ${nameByKey.get(server.key) || server.key}: ${server.status || "unknown"}`,
        );
      }
      const down = rows.filter((server) => server.status !== "up").length || 0;
      return `Server health check finished: ${count - down}/${count} up.`;
    },
    () => {
      const tab = document.getElementById("btn-server-mgmt");
      tab?.classList.remove("server-up", "server-starting");
      tab?.classList.add("server-down");
    },
  );

  const sshHealthPromise = runTask(
    "ssh-health",
    async () => {
      startupGate.writeLine("Calling /api/ssh-connection-health...");
      connHealth.health = await connHealth.fetchHealth();
      startupGate.writeLine("Got response from /api/ssh-connection-health");
      connHealth.notify();
      return connHealth.health;
    },
    (health) => {
      const count = health?.connections?.length || 0;
      const rows = health?.connections || [];
      const nameByKey = new Map(
        (SSHM.connections || []).map((conn) => [conn.key, conn.name]),
      );
      for (const conn of rows) {
        startupGate.writeLine(
          `SSH ${nameByKey.get(conn.key) || conn.key}: ${conn.status || "unknown"}`,
        );
      }
      const down =
        rows.filter((connection) => connection.status !== "up").length || 0;
      return `SSH health check finished: ${count - down}/${count} reachable.`;
    },
    () => {
      const tab = document.getElementById("btn-ssh-connections");
      tab?.classList.remove("server-up", "server-starting");
      tab?.classList.add("server-down");
    },
  );

  await Promise.all([
    serverRegistryPromise,
    sshRegistryPromise,
    serverHealthPromise,
    sshHealthPromise,
  ]);

  if (SM.servers) {
    for (const server of SM.servers) {
      startupGate.writeLine(`Queueing server check: ${server.name}`);
    }
    navServers.querySelectorAll("[data-server-key]").forEach((tab) => {
      tab.remove();
    });
    for (const server of SM.servers) {
      navServers.appendChild(tabFactory.buildServerTab(server));
    }
    serverHealth.notify();
  }

  if (SSHM.connections) {
    for (const conn of SSHM.connections) {
      startupGate.writeLine(`Queueing SSH check: ${conn.name}`);
    }
    navSSH.querySelectorAll("[data-conn-key]").forEach((tab) => {
      tab.remove();
    });
    for (const connection of SSHM.connections) {
      navSSH.appendChild(tabFactory.buildConnectionTab(connection));
    }
    connHealth.notify();
  }

  SM.healthPollTimer = setInterval(() => SM.pollHealth(), 10000);
  SSHM.healthPollTimer = setInterval(() => SSHM.pollHealth(), 15000);
}

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
  setInterval: globalThis.setInterval.bind(globalThis),
  clearInterval: globalThis.clearInterval.bind(globalThis),
});

// Poll the live month-status + recently-scanned signals, but only while the
// ROL Finance Reports view is actually on screen (the endpoints hit the finance
// DB, so there's no point polling when it's hidden). `offsetParent === null`
// catches every way it can be off screen — its own `hidden` class (Back button)
// AND a display:none ancestor when the user switches top-level sidebar sections
// (which does NOT toggle this sub-nav's own class). A human categorizing a row
// flips the month tab green + drops the item from New Records on the next tick.
RF.statusPollTimer = setInterval(() => {
  if (navRolFinanceReports.offsetParent !== null) RF.refreshStatus();
}, 10000);

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
// Unhealthy agents also bubble up to the parent "Agent Management" sidebar
// button (mirrors how Server Management goes red when any server is down) — so
// a Claude-SDK 404 lights up both Frita's tab AND her parent.
const _unhealthyAgents = new Set();
const agentMgmtBtn = document.getElementById("btn-agent-mgmt");
function setAgentTabHealth(agentId, ok) {
  const tab = navAgents.querySelector(`.agent-tab[data-agent-id="${agentId}"]`);
  if (tab) tab.classList.toggle("agent-health-error", !ok);
  if (ok) _unhealthyAgents.delete(agentId);
  else _unhealthyAgents.add(agentId);
  if (agentMgmtBtn) {
    agentMgmtBtn.classList.toggle(
      "agent-health-error",
      _unhealthyAgents.size > 0,
    );
  }
}
new AgentHealthPoller({ http, setHealth: setAgentTabHealth }).start();

/* =====================  Code-change restart alert  ===================== */
// Blink the Agents tab + prompt to restart when the dashboard's own source
// changes on disk (polls /api/code-status every 15s).
new CodeChangeAlert({ http }).start();

/* =====================  Document-vision halt alert  ===================== */
// Full-screen modal + red Window/Freezer scanner tabs when classify_scan.py's
// 3-tier vision fallback (Gemini -> ChatGPT-OAuth/Codex CLI -> OpenAI key) is
// ALL down (polls /api/server-health's 'document-vision' entry every 20s).
// Mirrors the server-side halt in process_scanned_document().
new VisionHaltAlert({ http }).start();

/* =====================  Scanners  =====================
   ROL Finance > Scanners > {Window,Freezer} Scanner. Each `.scanner-dialog`
   reuses the startup-panel look inline (no overlay). Start Scan kicks off the
   backend scan AND a ~10s yellow progress fill; when the scan returns the bar
   snaps green + "Scan Finished" and the image opens automatically. The image
   is dismissable (× / re-opened with "Show Image"). */
// Scanner status is strictly observation-only. A WIA transfer is started only
// by the explicit Start Scan POST; background GET polling must never create or
// dispatch another document.
const SCANNER_POLL_MS = 15000;
const MONITORED_SCANNERS = new Set();
const SCANNER_IMAGE_MIN_ZOOM = 0.25;
const SCANNER_IMAGE_MAX_ZOOM = 6;
const SCANNER_IMAGE_ZOOM_STEP = 1.12;

function clampScannerImageZoom(value) {
  return Math.min(
    SCANNER_IMAGE_MAX_ZOOM,
    Math.max(SCANNER_IMAGE_MIN_ZOOM, value),
  );
}

// A statement Mazda could not store waits in bank_statements/_needs_review/.
// The dialog polls for those and asks EG for the one missing piece — a workbook
// row, or an unreadable amount — then re-runs the store. Module-scope so it
// survives navigation between tabs, like the router's listener.
const statementReviewDialog = new StatementReviewDialog({ http });

function setupScanners() {
  statementReviewDialog.start();
  const controllers = {};
  document.querySelectorAll(".scanner-dialog").forEach((dialog) => {
    const scanner = dialog.dataset.scanner;
    const panel = dialog.querySelector(".scanner-panel");
    const bar = dialog.querySelector(".scanner-bar");
    const state = dialog.querySelector(".scanner-state");
    const startBtn = dialog.querySelector(".scanner-start");
    const showBtn = dialog.querySelector(".scanner-show");
    const fixPrinterBtn = dialog.querySelector(".scanner-fix-printer");
    const processBtn = dialog.querySelector(".scanner-process");
    const resultBox = dialog.querySelector(".scanner-result");
    const imageBox = dialog.querySelector(".scanner-image-box");
    const img = dialog.querySelector(".scanner-image");
    const closeBtn = dialog.querySelector(".scanner-image-close");
    const monitored = MONITORED_SCANNERS.has(scanner);
    let lastImageUrl = null;
    let scanning = false;
    let progressTimer = null;
    let pollTimer = null;
    let monitorActive = false;
    let inFlight = false;
    let imageZoom = 1;
    let imageBaseWidth = 0;
    let imageBaseHeight = 0;
    let imageDragging = false;
    let imageDragPointerId = null;
    let imageDragStartX = 0;
    let imageDragStartY = 0;
    let imageDragStartScrollLeft = 0;
    let imageDragStartScrollTop = 0;

    const setBar = (pct) => {
      bar.style.width = `${pct}%`;
    };
    const clearBlink = () => state.classList.remove("scanner-blink");
    const imageCanZoom = () =>
      !imageBox.classList.contains("hidden") &&
      !imageBox.classList.contains("scanner-image-loading") &&
      !imageBox.classList.contains("scanner-image-error") &&
      img.complete &&
      img.naturalWidth > 0 &&
      img.naturalHeight > 0;
    const imageCanPan = () =>
      imageCanZoom() &&
      (imageBox.scrollWidth > imageBox.clientWidth ||
        imageBox.scrollHeight > imageBox.clientHeight);
    const calculateImageBaseSize = () => {
      if (!img.naturalWidth || !img.naturalHeight) return;
      const availableWidth = Math.max(
        1,
        Math.min(imageBox.clientWidth * 0.92, 1100),
      );
      const availableHeight = Math.max(1, imageBox.clientHeight * 0.9);
      const fitScale = Math.min(
        availableWidth / img.naturalWidth,
        availableHeight / img.naturalHeight,
        1,
      );
      imageBaseWidth = Math.max(1, Math.round(img.naturalWidth * fitScale));
      imageBaseHeight = Math.max(1, Math.round(img.naturalHeight * fitScale));
    };
    const updateImageScrollMode = () => {
      const renderedWidth = imageBaseWidth * imageZoom;
      const renderedHeight = imageBaseHeight * imageZoom;
      const needsScroll =
        renderedWidth > imageBox.clientWidth - 80 ||
        renderedHeight > imageBox.clientHeight - 80;
      imageBox.classList.toggle("scanner-image-scrollable", needsScroll);
    };
    const setImageZoom = (nextZoom, anchorEvent = null) => {
      if (!imageCanZoom()) return;
      if (!imageBaseWidth || !imageBaseHeight) calculateImageBaseSize();

      const boxRect = imageBox.getBoundingClientRect();
      const previousRect = img.getBoundingClientRect();
      const anchorClientX =
        anchorEvent?.clientX ?? boxRect.left + imageBox.clientWidth / 2;
      const anchorClientY =
        anchorEvent?.clientY ?? boxRect.top + imageBox.clientHeight / 2;
      const relativeX =
        previousRect.width > 0
          ? Math.min(
              1,
              Math.max(
                0,
                (anchorClientX - previousRect.left) / previousRect.width,
              ),
            )
          : 0.5;
      const relativeY =
        previousRect.height > 0
          ? Math.min(
              1,
              Math.max(
                0,
                (anchorClientY - previousRect.top) / previousRect.height,
              ),
            )
          : 0.5;

      imageZoom = clampScannerImageZoom(nextZoom);
      img.style.width = `${Math.round(imageBaseWidth * imageZoom)}px`;
      img.style.height = `${Math.round(imageBaseHeight * imageZoom)}px`;
      updateImageScrollMode();

      requestAnimationFrame(() => {
        const nextRect = img.getBoundingClientRect();
        const imageContentLeft =
          nextRect.left - boxRect.left + imageBox.scrollLeft;
        const imageContentTop = nextRect.top - boxRect.top + imageBox.scrollTop;
        imageBox.scrollLeft =
          imageContentLeft +
          relativeX * nextRect.width -
          (anchorClientX - boxRect.left);
        imageBox.scrollTop =
          imageContentTop +
          relativeY * nextRect.height -
          (anchorClientY - boxRect.top);
      });
    };
    const resetImageZoom = () => {
      imageZoom = 1;
      imageBaseWidth = 0;
      imageBaseHeight = 0;
      imageBox.classList.remove(
        "scanner-image-ready",
        "scanner-image-scrollable",
        "scanner-image-dragging",
      );
      img.style.width = "";
      img.style.height = "";
      imageBox.scrollLeft = 0;
      imageBox.scrollTop = 0;
    };
    const stopImageDrag = (e) => {
      if (
        !imageDragging ||
        (imageDragPointerId !== null &&
          e?.pointerId !== undefined &&
          e.pointerId !== imageDragPointerId)
      ) {
        return;
      }
      imageDragging = false;
      imageDragPointerId = null;
      imageBox.classList.remove("scanner-image-dragging");
      if (e?.pointerId !== undefined && img.hasPointerCapture?.(e.pointerId)) {
        try {
          img.releasePointerCapture(e.pointerId);
        } catch {
          // Pointer capture may already be gone after cancel/lostcapture.
        }
      }
    };
    const showImage = () => {
      if (!lastImageUrl) return;
      // Repeated scans reuse the same filename, so cache-bust to avoid the
      // browser serving a stale/blank copy (the "shows sometimes, blank
      // sometimes" symptom). Reset src first so onload always refires.
      const bust = `${lastImageUrl}${lastImageUrl.includes("?") ? "&" : "?"}t=${Date.now()}`;
      resetImageZoom();
      imageBox.classList.remove("scanner-image-error");
      imageBox.classList.add("scanner-image-loading");
      img.src = "";
      img.src = bust;
      imageBox.classList.remove("hidden");
    };
    const hideImage = () => {
      stopImageDrag();
      imageBox.classList.add("hidden");
    };
    img.addEventListener("load", () => {
      imageBox.classList.remove("scanner-image-loading", "scanner-image-error");
      imageBox.classList.add("scanner-image-ready");
      calculateImageBaseSize();
      setImageZoom(1);
    });
    img.addEventListener("error", () => {
      imageBox.classList.remove("scanner-image-loading");
      imageBox.classList.add("scanner-image-error");
      imageBox.classList.remove(
        "scanner-image-ready",
        "scanner-image-scrollable",
        "scanner-image-dragging",
      );
    });

    // Process Document — the intake pipeline (classify → parse inline, then
    // investigate → categorize → store dispatched to Mazda). Built from the GoF
    // controller + DOM view so the wiring here stays a thin binding.
    const pipelineView =
      processBtn && resultBox ? new DomDocumentPipelineView(resultBox) : null;
    const pipeline = pipelineView
      ? new DocumentPipelineController({ http, view: pipelineView })
      : null;
    const runPipeline = () => {
      if (!pipeline) return;
      // Fire-and-forget: the controller drives the inline view itself; no
      // polling, and a scan never waits on the pipeline.
      void pipeline.process(scanner);
    };

    const runPrinterRepair = async () => {
      if (!fixPrinterBtn || !resultBox) return;
      const repairButtons = document.querySelectorAll(".scanner-fix-printer");
      repairButtons.forEach((button) => {
        button.disabled = true;
      });
      resultBox.classList.remove("hidden");
      resultBox.innerHTML =
        '<div class="pipeline-title">Printer repair</div>' +
        '<div class="pipeline-busy">Checking the HP DeskJet and repairing its Windows queue…</div>';
      const result = await printerRepair.repair();
      const message = TextUtils.esc(
        result.text ||
          (result.ok ? "Printer fixed." : "Printer repair failed."),
      );
      resultBox.innerHTML =
        '<div class="pipeline-title">Printer repair</div>' +
        `<div class="${result.ok ? "printer-repair-success" : "pipeline-error"}">${message}</div>`;
      repairButtons.forEach((button) => {
        button.disabled = false;
      });
    };

    const setBusy = (msg) => {
      if (progressTimer) {
        clearInterval(progressTimer);
        progressTimer = null;
      }
      setBar(100);
      panel.classList.remove("scan-complete", "scan-error");
      panel.classList.add("scan-busy");
      state.textContent = msg;
      state.classList.add("scanner-blink");
    };
    const setReady = (imageUrl) => {
      if (progressTimer) {
        clearInterval(progressTimer);
        progressTimer = null;
      }
      clearBlink();
      setBar(100);
      panel.classList.remove("scan-busy", "scan-error");
      panel.classList.add("scan-complete");
      state.textContent = "Scan Finished";
      if (imageUrl) {
        lastImageUrl = imageUrl;
        showBtn.disabled = false;
        showImage();
      }
      // Auto-run the intake pipeline the instant the scan finishes and the image
      // is ready for the first step — exactly the moment the document is ready.
      if (processBtn) processBtn.disabled = false;
      runPipeline();
    };
    const setFailed = (msg) => {
      if (progressTimer) {
        clearInterval(progressTimer);
        progressTimer = null;
      }
      clearBlink();
      setBar(100);
      panel.classList.remove("scan-busy", "scan-complete");
      panel.classList.add("scan-error");
      state.textContent = msg;
    };

    const setIdle = () => {
      if (progressTimer) {
        clearInterval(progressTimer);
        progressTimer = null;
      }
      clearBlink();
      setBar(0);
      panel.classList.remove("scan-busy", "scan-complete", "scan-error");
      state.textContent = "Idle — ready to scan.";
    };

    // Map a /api/scanner-status or /api/scanner-scan result onto the dialog.
    const applyResult = (data) => {
      const status = data.status || (data.ok ? "ready" : "error");
      if (status === "ready") {
        setReady(data.image_url);
      } else if (status === "idle") {
        setIdle();
      } else if (status === "intake_busy") {
        setBusy(data.error || "Previous scan is still being verified.");
      } else if (status === "busy" || status === "offline") {
        setBusy("Restart the Scanner Please");
      } else {
        setFailed(`Scan failed: ${data.error || "unknown error"}`);
      }
      return status;
    };

    const stopMonitor = () => {
      monitorActive = false;
      if (pollTimer) {
        clearTimeout(pollTimer);
        pollTimer = null;
      }
      if (progressTimer) {
        clearInterval(progressTimer);
        progressTimer = null;
      }
    };

    const pollOnce = async () => {
      if (!monitorActive || inFlight) return;
      inFlight = true;
      // Animate a yellow fill while the probe runs so its timing is visible.
      // applyResult()/stopMonitor() clear progressTimer when the probe returns.
      clearBlink();
      panel.classList.remove("scan-busy", "scan-complete", "scan-error");
      state.textContent = "Checking scanner…";
      setBar(4);
      const probeStart = Date.now();
      if (progressTimer) clearInterval(progressTimer);
      progressTimer = setInterval(() => {
        const t = Math.min((Date.now() - probeStart) / 30000, 1);
        setBar(4 + t * 88);
      }, 150);
      try {
        const res = await fetch(`/api/scanner-status?scanner=${scanner}`);
        const data = await res.json();
        inFlight = false;
        if (!monitorActive) {
          if (progressTimer) {
            clearInterval(progressTimer);
            progressTimer = null;
          }
          return;
        }
        // On recovery the status probe's transfer succeeds -> stop polling.
        if (applyResult(data) === "ready") {
          stopMonitor();
          return;
        }
      } catch {
        inFlight = false;
        if (monitorActive) setBusy("Restart the Scanner Please");
      }
      if (monitorActive) pollTimer = setTimeout(pollOnce, SCANNER_POLL_MS);
    };

    const startMonitor = () => {
      if (!monitored || monitorActive) return;
      monitorActive = true;
      void pollOnce();
    };

    // One-shot manual scan with the yellow ~10s fill (used by the Start button).
    const runManualScan = async () => {
      if (scanning) return;
      scanning = true;
      stopMonitor();
      startBtn.disabled = true;
      showBtn.disabled = true;
      if (processBtn) processBtn.disabled = true;
      if (pipelineView) pipelineView.clear();
      hideImage();
      clearBlink();
      panel.classList.remove("scan-complete", "scan-error", "scan-busy");
      state.textContent = "Scanning…";
      setBar(4);
      const startedAt = Date.now();
      // A real flatbed scan takes ~30s; fill over that until the actual result
      // snaps the bar green. The Window Scanner fills ~30% faster (~23s) and runs
      // all the way to 100% yellow, then sits there until the scan-complete event
      // turns it green.
      const fillMs = scanner === "window" ? 23000 : 30000;
      const fillTo = scanner === "window" ? 96 : 88;
      progressTimer = setInterval(() => {
        const t = Math.min((Date.now() - startedAt) / fillMs, 1);
        setBar(4 + t * fillTo);
      }, 150);
      try {
        const res = await fetch("/api/scanner-scan", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ scanner }),
        });
        const data = await res.json();
        const status = applyResult(data);
        // A monitored scanner that came back busy/offline: resume polling so it
        // auto-recovers once power-cycled.
        if (monitored && (status === "busy" || status === "offline")) {
          startMonitor();
        }
      } catch (err) {
        setFailed(`Scan failed: ${err.message}`);
      } finally {
        scanning = false;
        startBtn.disabled = false;
      }
    };

    closeBtn.addEventListener("click", hideImage);
    showBtn.addEventListener("click", showImage);
    startBtn.addEventListener("click", runManualScan);
    if (fixPrinterBtn)
      fixPrinterBtn.addEventListener("click", runPrinterRepair);
    if (processBtn) processBtn.addEventListener("click", runPipeline);
    // Click the dark backdrop (outside the image frame) to close the modal.
    imageBox.addEventListener("click", (e) => {
      if (e.target === imageBox) hideImage();
    });
    img.addEventListener("pointerdown", (e) => {
      if (e.button !== 0 || !imageCanPan()) return;
      e.preventDefault();
      imageDragging = true;
      imageDragPointerId = e.pointerId;
      imageDragStartX = e.clientX;
      imageDragStartY = e.clientY;
      imageDragStartScrollLeft = imageBox.scrollLeft;
      imageDragStartScrollTop = imageBox.scrollTop;
      imageBox.classList.add("scanner-image-dragging");
      try {
        img.setPointerCapture?.(e.pointerId);
      } catch {
        // Synthetic pointer events may not be eligible for capture.
      }
    });
    img.addEventListener("pointermove", (e) => {
      if (!imageDragging || e.pointerId !== imageDragPointerId) return;
      e.preventDefault();
      imageBox.scrollLeft =
        imageDragStartScrollLeft - (e.clientX - imageDragStartX);
      imageBox.scrollTop =
        imageDragStartScrollTop - (e.clientY - imageDragStartY);
    });
    img.addEventListener("pointerup", stopImageDrag);
    img.addEventListener("pointercancel", stopImageDrag);
    img.addEventListener("lostpointercapture", stopImageDrag);
    imageBox.addEventListener(
      "wheel",
      (e) => {
        if (!imageCanZoom()) return;
        e.preventDefault();
        const factor =
          e.deltaY < 0 ? SCANNER_IMAGE_ZOOM_STEP : 1 / SCANNER_IMAGE_ZOOM_STEP;
        setImageZoom(imageZoom * factor, e);
      },
      { passive: false },
    );
    window.addEventListener("resize", () => {
      if (!imageCanZoom()) return;
      calculateImageBaseSize();
      setImageZoom(imageZoom);
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !imageBox.classList.contains("hidden"))
        hideImage();
    });

    controllers[scanner] = { startMonitor, stopMonitor };
  });
  return controllers;
}
const scannerControllers = setupScanners();
function stopAllScannerMonitors() {
  for (const c of Object.values(scannerControllers)) c.stopMonitor();
}

/* Needs Vendor Review — ROL Finance > Scanners > Needs Vendor Review.
   Lists receipts saved with expense_status=NEEDS_VENDOR_KEY (vendor/category
   couldn't be auto-resolved, so the image + a placeholder row were saved
   anyway — see save_receipt_pending_vendor_review() in rol_finances) and lets
   a human finish the save by picking an existing vendor_key. */
const vendorReviewPanelEl = document.getElementById("vendor-review-panel");
const vendorReviewController = vendorReviewPanelEl
  ? new VendorReviewController({
      http,
      view: new DomVendorReviewView(vendorReviewPanelEl, {
        getVendorKeys: () => vendorReviewController.listVendorKeys(),
        onPickVendor: (expenseId, vendorKey) =>
          vendorReviewController.pickVendor(expenseId, vendorKey),
      }),
    })
  : null;

/* Process PDF — ROL Finance > Scanners > Process PDF.
   Runs the intake pipeline (classify → parse inline, Mazda dispatched for
   investigate → categorize → store) on an existing PDF file on the server. */
(function setupPdfProcessor() {
  const section = document.getElementById("scanners-pdf");
  if (!section) return;
  const pathInput = section.querySelector("#pdf-file-path");
  const labelInput = section.querySelector("#pdf-doc-label");
  const processBtn = section.querySelector(".pdf-process-btn");
  const resultBox = section.querySelector(".scanner-result");
  if (!pathInput || !processBtn || !resultBox) return;

  const pipelineView = new DomDocumentPipelineView(resultBox);
  const pipeline = new DocumentPipelineController({ http, view: pipelineView });

  processBtn.addEventListener("click", () => {
    const filePath = pathInput.value.trim();
    if (!filePath) return;
    const label = labelInput ? labelInput.value.trim() : "";
    void pipeline.processFile(filePath, label || undefined);
  });
})();

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
    RF.openReports().then(() => RF.refreshStatus());
  }
})();

void preloadStartupChecks();
