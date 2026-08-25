// server-manager.js — the SM facade: Server Management's tab list, health
// colouring, and the per-server detail panel (log stream + Restart/Deploy).
//
// Health is polled by the library's ServerHealthMonitor; two observers colour
// the main "Server Management" tab and the per-server tabs.

import { TextUtils } from "../abstract/text-utils.js";
import {
  DomConsoleView,
  ServerActionController,
  ServerHealthMonitor,
  ServerLogController,
} from "../implementation/index.js";
import { attachLogFilter, createLedReporter } from "./log-panel.js";

const esc = TextUtils.esc;

// Compact "down for" duration: 45s / 12m / 3h 4m.
export function fmtDownFor(sec) {
  if (sec < 60) return `${sec}s`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m`;
  return `${Math.floor(sec / 3600)}h ${Math.floor((sec % 3600) / 60)}m`;
}

export function createServerManager({
  doc = document,
  http,
  nav,
  viewNav,
  tabFactory,
}) {
  const serverHealth = new ServerHealthMonitor(http);
  const serverAction = new ServerActionController({ http });

  serverHealth.subscribe((health) => {
    const tab = doc.getElementById("btn-server-mgmt");
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
    viewNav.updateSystemStatusTab();
  });

  serverHealth.subscribe((health) => {
    if (!health) return;
    const byKey = {};
    for (const s of health.servers) byKey[s.key] = s;
    nav.servers.querySelectorAll("[data-server-key]").forEach((tab) => {
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
      // Indicator #3: stale outages blink to draw the eye; the tooltip shows
      // how long it's been down and whether it's just a symptom of a down
      // dependency (#1).
      if (s.stale) tab.classList.add("server-stale");
      const bits = [];
      if (s.blocked_by) bits.push(`blocked by ${s.blocked_by}`);
      if (s.down_for_seconds)
        bits.push(`down for ${fmtDownFor(s.down_for_seconds)}`);
      if (s.container_status) bits.push(s.container_status);
      tab.title = bits.join(" · ");
    });
  });

  const SM = {
    healthPollTimer: null,
    current: null, // { key, name }
    servers: null,
    logController: null,
    health: serverHealth,
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
      nav.servers.classList.remove("hidden");
      viewNav.activateView("server-management");
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
      nav.servers.querySelectorAll("[data-server-key]").forEach((t) => {
        t.remove();
      });
      if (!this.servers) return;
      for (const s of this.servers)
        nav.servers.appendChild(tabFactory.buildServerTab(s));
      this.pollHealth(); // colour the freshly-built tabs
    },

    openServer(key, name) {
      this.stopPoll();
      this.stopHealthPoll();
      this.current = { key, name };
      doc.getElementById("servers-detail-title").textContent = name;
      const body = doc.getElementById("servers-detail-body");
      const meta = (this.servers || []).find((s) => s.key === key) || {};
      // Every server gets a Restart button, always enabled, so the user never
      // has to drop to the command line. The backend
      // (/api/server-action action:restart) dispatches to a per-server handler
      // (systemd --user, SSH, or redeploy).
      body.innerHTML =
        (meta.note ? `<p class="srv-note">${esc(meta.note)}</p>` : "") +
        '<div class="srv-status starting" id="srv-status"><span class="srv-led"></span><span id="srv-status-text">checking…</span></div>' +
        '<input class="srv-filter" id="srv-filter" placeholder="Filter log lines (e.g. error)…" />' +
        `<button class="srv-start-btn" id="srv-restart-btn">Restart ${esc(name)}</button>` +
        // The dashboard can deploy ITSELF (git pull the live checkout +
        // restart) — the keyboard-free path so we're never dead in the water.
        // Only this server has a backend deploy handler.
        (key === "dashboard"
          ? '<button class="srv-start-btn" id="srv-deploy-btn">Deploy latest</button>'
          : "") +
        '<div id="srv-console-host"></div>';
      viewNav.activateView("servers-detail");

      const statusEl = body.querySelector("#srv-status");
      const statusText = body.querySelector("#srv-status-text");
      const restartBtn = body.querySelector("#srv-restart-btn");
      const deployBtn = body.querySelector("#srv-deploy-btn");
      const view = DomConsoleView.mount(
        body.querySelector("#srv-console-host"),
        "srv",
      );
      attachLogFilter(
        body.querySelector("#srv-filter"),
        body.querySelector(".msi-inner"),
      );

      // Restart and Deploy share everything but the action and its verb.
      const runAction = async (btn, verb, run) => {
        btn.disabled = true;
        restartBtn.disabled = true;
        statusEl.className = "srv-status starting";
        statusText.textContent = `${verb.toUpperCase()}ING... — ${name.toLowerCase()}`;
        const res = await run();
        if (res.ok) {
          view.writeHtml(
            `<div class="msi-entry"><span class="hdr">${verb} action</span> ` +
              esc(res.text || "OK") +
              "</div>",
          );
          view.scrollToBottom();
        } else {
          // Fail loud: a bad pull did NOT restart the box — show why.
          statusText.textContent = `${verb.toUpperCase()} FAILED — ${esc(res.text)}`;
          statusEl.className = "srv-status down";
        }
        btn.disabled = false;
        restartBtn.disabled = false;
      };

      restartBtn.addEventListener("click", () =>
        runAction(restartBtn, "restart", () => serverAction.restart(key)),
      );
      if (deployBtn) {
        deployBtn.addEventListener("click", () =>
          runAction(deployBtn, "deploy", () => serverAction.deploy(key)),
        );
      }

      // The ServerLogController polls /api/server-logs (3s, dedup by seq) and
      // reports health via onStatus → the detail-panel LED. The Restart button
      // stays enabled regardless of status (the user can always restart).
      this.logController = new ServerLogController({
        http,
        view,
        serverKey: key,
        onStatus: createLedReporter(statusEl, statusText, [
          "up",
          "starting",
          "concern",
          "down",
        ]),
      });
      this.logController.start();
    },
  };

  return SM;
}
