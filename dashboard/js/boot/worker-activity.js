import { renderWorkerEscalation } from "../abstract/worker-escalation-render.js";
// worker-activity.js — System Status > Worker Activity, and the sole reader of
// /api/worker-activity.
//
// One setTimeout chain (Printer-panel convention): every 5 s while Worker
// Activity or Poll Settings is on screen, every 20 s otherwise (the ledger
// snapshot itself is rewritten every 20 s). It never overlaps requests: a poll
// started while one is in flight joins that one. Each answer updates the
// sidebar Worker legend, this page and any subscriber (Poll Settings), and
// each part of the page is redrawn only when its own data changed.

import { renderWorkerLegend } from "../abstract/bridge-workflow-render.js";
import {
  renderWorkerActivity,
  renderWorkerHealth,
  renderWorkerProviderSelection,
  renderWorkerTasks,
  renderWorkerTerminal,
  renderWorkerTerminalContent,
  renderWorkerWorkflow,
  workerTabClass,
} from "../abstract/worker-activity-render.js";

import {
  healthSignature,
  taskSignature,
  terminalSignature,
} from "../abstract/worker-activity-signatures.js";

export {
  healthSignature,
  taskSignature,
} from "../abstract/worker-activity-signatures.js";

const URL = "/api/worker-activity";
const FAST_MS = 5000;
const SLOW_MS = 20000;
const TERMINAL_BOTTOM_TOLERANCE_PX = 8;
const WATCHING_VIEWS = ["worker-activity", "poll-settings"];

export function createWorkerActivity({ doc = document, win = window, http }) {
  const body = doc.getElementById("worker-activity-body");
  const tab = doc.getElementById("btn-worker-activity");
  const legend = doc.getElementById("worker-legend");
  const listeners = new Set();

  const WKR = {
    payload: null,
    restarting: false,
    restartMessage: "",
    timer: null,
    inflight: null,
    terminalFollow: true,
    terminalResizeObserver: null,
    started: true,
    observedTasks: new Map(),
    activityEvents: [],
    changedTaskIds: new Set(),
    drawn: {
      health: null,
      tasks: null,
      terminal: null,
      legend: null,
      escalation: null,
    },
    isActive() {
      return WATCHING_VIEWS.some((id) =>
        doc.getElementById(id)?.classList.contains("active"),
      );
    },
    subscribe(fn) {
      listeners.add(fn);
      if (this.payload) fn(this.payload);
      return () => listeners.delete(fn);
    },
    part(name) {
      return body?.querySelector(`[data-worker-part="${name}"]`) || null;
    },
    terminal() {
      return (
        this.part("terminal")?.querySelector?.(".worker-activity-terminal") ||
        null
      );
    },
    isTerminalAtBottom(terminal) {
      return (
        terminal.scrollHeight - terminal.scrollTop - terminal.clientHeight <=
        TERMINAL_BOTTOM_TOLERANCE_PX
      );
    },
    bindTerminal(terminal) {
      if (!terminal || terminal._workerActivityAutoScrollBound) return;
      terminal._workerActivityAutoScrollBound = true;
      terminal.addEventListener?.("scroll", () => {
        this.terminalFollow = this.isTerminalAtBottom(terminal);
      });
      if (typeof win.ResizeObserver === "function") {
        this.terminalResizeObserver?.disconnect?.();
        this.terminalResizeObserver = new win.ResizeObserver(() => {
          if (this.terminalFollow) terminal.scrollTop = terminal.scrollHeight;
        });
        this.terminalResizeObserver.observe(terminal);
      }
    },
    resetTerminal(terminal) {
      this.terminalFollow = true;
      if (terminal) terminal.scrollTop = terminal.scrollHeight;
    },
    updateTerminal(payload) {
      const terminalPart = this.part("terminal");
      let terminal = this.terminal();
      if (!terminal && terminalPart) {
        terminalPart.innerHTML = renderWorkerTerminal(payload);
        terminal = this.terminal();
      }
      if (!terminal) return;
      this.bindTerminal(terminal);
      const wasFollowing = this.terminalFollow;
      const previousScrollTop = terminal.scrollTop;
      terminal.innerHTML = renderWorkerTerminalContent(payload);
      if (payload?.tasks_available && !(payload.tasks || []).length) {
        this.resetTerminal(terminal);
      } else if (wasFollowing) {
        terminal.scrollTop = terminal.scrollHeight;
      } else {
        terminal.scrollTop = previousScrollTop;
      }
    },
    paint() {
      const p = this.payload;
      const tasks = taskSignature(p);
      if (legend && this.drawn.legend !== tasks) {
        legend.innerHTML = renderWorkerLegend(p);
        this.drawn.legend = tasks;
      }
      if (tab) {
        tab.classList.remove("server-up", "server-concern", "poll-disabled");
        tab.classList.add(workerTabClass(p));
      }
      if (!body) return;
      if (!this.part("workflow")) {
        body.innerHTML = renderWorkerActivity(p, {
          changedIds: this.changedTaskIds,
        });
        const terminal = this.terminal();
        this.bindTerminal(terminal);
        this.resetTerminal(terminal);
        this.drawn.health = healthSignature(p);
        this.drawn.tasks = tasks;
        this.drawn.terminal = terminalSignature(p);
      } else {
        const health = healthSignature(p);
        if (
          this.drawn.health !== health ||
          this.restartMessage ||
          this.restarting
        ) {
          this.part("health").innerHTML =
            renderWorkerHealth(p) +
            (this.restartMessage
              ? `<p role="status">${this.restartMessage}</p>`
              : "");
          if (!this.restartMessage && !this.restarting)
            this.drawn.health = health;
        }
        if (this.drawn.tasks !== tasks) {
          this.part("workflow").innerHTML = renderWorkerWorkflow(p, {
            changedIds: this.changedTaskIds,
          });
          this.part("provider").innerHTML = renderWorkerProviderSelection(p);
          this.part("tasks").innerHTML = renderWorkerTasks(p);
          this.drawn.tasks = tasks;
        }
        if (this.drawn.terminal !== terminalSignature(p)) {
          this.updateTerminal(p);
          this.drawn.terminal = terminalSignature(p);
        }
      }
      const escalationSignature = JSON.stringify(p?.escalation);
      const escalation = this.part("escalation");
      if (escalation && this.drawn.escalation !== escalationSignature) {
        escalation.innerHTML = renderWorkerEscalation(p);
        this.drawn.escalation = escalationSignature;
      }
      const updated = this.part("updated");
      if (updated) {
        updated.textContent = p?.received_at
          ? `Last refresh ${new Date(p.received_at).toLocaleTimeString()}${p.snapshot_stale ? " (ledger stale)" : ""}`
          : "Waiting for a worker ledger";
      }
    },
    schedule() {
      win.clearTimeout(this.timer);
      if (!this.started) return;
      const hidden = doc.visibilityState === "hidden";
      this.timer = win.setTimeout(
        () => void this.poll(),
        this.isActive() && !hidden ? FAST_MS : SLOW_MS,
      );
    },
    poll() {
      if (!this.started) return Promise.resolve(null);
      if (this.inflight) return this.inflight;
      this.inflight = (async () => {
        let payload;
        try {
          payload = await http.getJSON(URL);
        } catch (error) {
          payload = {
            ok: false,
            tasks_available: false,
            tasks: [],
            fetch_error: error.message,
            tasks_error: `Worker telemetry request failed: ${error.message}`,
          };
        }
        if (!this.started) return;
        const now = new Date().toISOString();
        const next = new Map(
          (payload?.tasks || []).map((task) => [task.id, task.status]),
        );
        const observations = [];
        const transitioned = [];
        for (const task of payload?.tasks || []) {
          const before = this.observedTasks.get(task.id);
          if (before !== task.status) {
            observations.push({
              time: now,
              taskId: task.id,
              agent: task.agent,
              message: `Dashboard observed task status: ${task.status || "unknown"}`,
              source: "dashboard",
            });
            // A real transition, not a task's first-ever appearance: that is
            // the signal worth a one-shot visual flash on its row.
            if (before !== undefined) transitioned.push(task.id);
          }
        }
        this.observedTasks = next;
        this.changedTaskIds = new Set(transitioned.map(String));
        if (observations.length)
          this.activityEvents = [...this.activityEvents, ...observations].slice(
            -100,
          );
        this.payload = {
          ...payload,
          activity_events: this.activityEvents,
          received_at: Date.now(),
        };
        this.paint();
        for (const fn of listeners) fn(this.payload);
      })().finally(() => {
        this.inflight = null;
        this.schedule();
      });
      return this.inflight;
    },
    open() {
      this.started = true;
      // Draw the page (SVG included) at once; the answer fills in the data.
      if (body && !this.part("workflow")) this.paint();
      return this.poll();
    },
    stop() {
      this.started = false;
      win.clearTimeout(this.timer);
      this.timer = null;
      this.terminalResizeObserver?.disconnect?.();
      this.terminalResizeObserver = null;
    },
  };

  body?.addEventListener("click", (event) => {
    if (event.target.closest?.("[data-worker-activity=refresh]"))
      void WKR.poll();
    if (
      event.target.closest?.("[data-worker-activity=restart]") &&
      !WKR.restarting
    ) {
      if (
        !win.confirm("Restart only the supervised agent-bridge-worker.service?")
      )
        return;
      const token = win.prompt("Enter the worker restart authorization token:");
      if (!token) return;
      WKR.restarting = true;
      WKR.restartMessage = "Restarting…";
      WKR.paint();
      void http
        .postJSON(
          "/api/worker-activity/restart",
          {},
          { headers: { Authorization: `Bearer ${token}` } },
        )
        .then((result) => {
          WKR.restartMessage = result.ok
            ? result.text
            : `Restart failed: ${result.text || "unknown error"}`;
        })
        .catch((error) => {
          WKR.restartMessage = `Restart failed: ${error.message}`;
        })
        .finally(() => {
          WKR.restarting = false;
          WKR.paint();
          void WKR.poll();
        });
    }
  });
  doc.addEventListener?.("visibilitychange", () => {
    if (doc.visibilityState === "visible" && WKR.isActive()) void WKR.poll();
  });

  void WKR.poll();
  return WKR;
}
