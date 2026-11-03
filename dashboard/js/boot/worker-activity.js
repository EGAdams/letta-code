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
  renderWorkerTasks,
  renderWorkerWorkflow,
  workerTabClass,
} from "../abstract/worker-activity-render.js";

const URL = "/api/worker-activity";
const FAST_MS = 5000;
const SLOW_MS = 20000;
const WATCHING_VIEWS = ["worker-activity", "poll-settings"];

/** Signature of what the SVG/table/legend draw: not heartbeat timestamps. */
export function taskSignature(payload) {
  return JSON.stringify({
    a: payload?.tasks_available,
    e: payload?.tasks_error,
    f: payload?.fetch_error,
    t: payload?.tasks,
    w: payload?.worker?.status,
  });
}

export function healthSignature(payload) {
  const w = payload?.worker || {};
  return JSON.stringify([
    payload?.ok,
    payload?.fetch_error,
    w.status,
    w.reason,
    w.service?.active,
  ]);
}

export function createWorkerActivity({ doc = document, win = window, http }) {
  const body = doc.getElementById("worker-activity-body");
  const tab = doc.getElementById("btn-worker-activity");
  const legend = doc.getElementById("worker-legend");
  const listeners = new Set();

  const WKR = {
    payload: null,
    timer: null,
    inflight: null,
    drawn: { health: null, tasks: null, legend: null },
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
        body.innerHTML = renderWorkerActivity(p);
        this.drawn.health = healthSignature(p);
        this.drawn.tasks = tasks;
      } else {
        const health = healthSignature(p);
        if (this.drawn.health !== health) {
          this.part("health").innerHTML = renderWorkerHealth(p);
          this.drawn.health = health;
        }
        if (this.drawn.tasks !== tasks) {
          this.part("workflow").innerHTML = renderWorkerWorkflow(p);
          this.part("tasks").innerHTML = renderWorkerTasks(p);
          this.drawn.tasks = tasks;
        }
      }
      const updated = this.part("updated");
      if (updated && p?.received_at)
        updated.textContent = `Updated ${new Date(p.received_at).toLocaleTimeString()}`;
    },
    schedule() {
      win.clearTimeout(this.timer);
      const hidden = doc.visibilityState === "hidden";
      this.timer = win.setTimeout(
        () => void this.poll(),
        this.isActive() && !hidden ? FAST_MS : SLOW_MS,
      );
    },
    poll() {
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
        this.payload = { ...payload, received_at: Date.now() };
        this.paint();
        for (const fn of listeners) fn(this.payload);
      })().finally(() => {
        this.inflight = null;
        this.schedule();
      });
      return this.inflight;
    },
    open() {
      // Draw the page (SVG included) at once; the answer fills in the data.
      if (body && !this.part("workflow")) this.paint();
      return this.poll();
    },
  };

  body?.addEventListener("click", (event) => {
    if (event.target.closest?.("[data-worker-activity=refresh]"))
      void WKR.poll();
  });
  doc.addEventListener?.("visibilitychange", () => {
    if (doc.visibilityState === "visible" && WKR.isActive()) void WKR.poll();
  });

  void WKR.poll();
  return WKR;
}
