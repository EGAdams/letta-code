// ssh-manager.js — the SSHM facade: SSH Connections' tab list, health
// colouring, and the per-connection detail panel (log stream + Test).
//
// Uses the same ServerHealthMonitor as Server Management against a different
// endpoint; the payload has a `connections` array (status only up/down, no
// "starting").

import { TextUtils } from "../abstract/text-utils.js";
import {
  ConnectionLogController,
  ConnectionTestController,
  DomConsoleView,
  ServerHealthMonitor,
} from "../implementation/index.js";
import { attachLogFilter, createLedReporter } from "./log-panel.js";

const esc = TextUtils.esc;

export function createSshManager({
  doc = document,
  http,
  nav,
  viewNav,
  tabFactory,
}) {
  const connHealth = new ServerHealthMonitor(
    http,
    "/api/ssh-connection-health",
  );
  const connTest = new ConnectionTestController({ http });

  connHealth.subscribe((health) => {
    const tab = doc.getElementById("btn-ssh-connections");
    if (!tab) return;
    tab.classList.remove("server-up", "server-down", "server-starting");
    if (!health) return;
    tab.classList.add(health.any_down ? "server-down" : "server-up");
    viewNav.updateSystemStatusTab();
  });

  connHealth.subscribe((health) => {
    if (!health) return;
    const map = {};
    for (const c of health.connections) map[c.key] = c.status;
    nav.ssh.querySelectorAll("[data-conn-key]").forEach((tab) => {
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
    health: connHealth,

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
      nav.ssh.classList.remove("hidden");
      viewNav.activateView("ssh-connections");
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
      nav.ssh.querySelectorAll("[data-conn-key]").forEach((t) => {
        t.remove();
      });
      if (!this.connections) return;
      for (const c of this.connections)
        nav.ssh.appendChild(tabFactory.buildConnectionTab(c));
      this.pollHealth(); // colour the freshly-built tabs
    },

    openConnection(key, name) {
      this.stopPoll();
      this.current = { key, name };
      doc.getElementById("ssh-connection-detail-title").textContent = name;
      const body = doc.getElementById("ssh-connection-detail-body");
      const meta = (this.connections || []).find((c) => c.key === key) || {};
      body.innerHTML =
        (meta.note ? `<p class="srv-note">${esc(meta.note)}</p>` : "") +
        '<div class="srv-status starting" id="ssh-status"><span class="srv-led"></span><span id="ssh-status-text">checking…</span></div>' +
        '<input class="srv-filter" id="ssh-filter" placeholder="Filter log lines (e.g. timed out)…" />' +
        '<button class="srv-start-btn" id="ssh-test-btn">Test Connection</button>' +
        '<div id="ssh-console-host"></div>';
      viewNav.activateView("ssh-connection-detail");

      const statusEl = body.querySelector("#ssh-status");
      const statusText = body.querySelector("#ssh-status-text");
      const testBtn = body.querySelector("#ssh-test-btn");
      const view = DomConsoleView.mount(
        body.querySelector("#ssh-console-host"),
        "ssh",
      );
      attachLogFilter(
        body.querySelector("#ssh-filter"),
        body.querySelector(".msi-inner"),
      );

      // onStatus drives the LED from classifyConnectionStatus
      // (CONNECTED / DOWN / checking…).
      const onStatus = createLedReporter(
        statusEl,
        statusText,
        ["up", "down"],
        "starting",
      );
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

  return SSHM;
}
