// pc-monitor.js — PC Monitor tab: one sub-nav tab per machine
// (Windows 11 / Windows 10 / Moms 46), each showing RAM / Hard Drive /
// Network progress bars from /api/pc-metrics. Card HTML comes from
// js/abstract/pc-metrics-render.js.

import { renderPcMetrics } from "../abstract/pc-metrics-render.js";
import { TextUtils } from "../abstract/text-utils.js";

const esc = TextUtils.esc;

export function createPcMonitor({ doc = document, http, nav, viewNav }) {
  const navPcMonitor = nav.pcMonitor;

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
        viewNav.setActive(
          navPcMonitor,
          '[data-nav="pc-monitor"][data-pc]',
          first,
        );
        this.show(first.dataset.pc);
      }
      this.pollTabs();
      this.pollTimer = setInterval(() => {
        if (this.current) this.show(this.current);
        this.pollTabs();
      }, 15000);
    },
    async show(key) {
      const body = doc.getElementById("pc-monitor-body");
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
      const levels = await Promise.all(
        tabs.map(async (t) => {
          try {
            const d = await http.getJSON(
              `/api/pc-metrics?pc=${encodeURIComponent(t.dataset.pc)}`,
            );
            const level = d.level || (d.alert ? "warn" : "ok");
            t.classList.toggle("tab-alert", level === "warn");
            t.classList.toggle("tab-alert-red", level === "crit");
            return level;
          } catch {
            /* leave the tab unflagged on transient error */
            return null;
          }
        }),
      );
      const parent = doc.getElementById("btn-pc-monitor");
      const known = levels.filter(Boolean);
      const level = known.includes("crit")
        ? "crit"
        : known.includes("warn")
          ? "warn"
          : known.length
            ? "ok"
            : null;
      if (parent && level) {
        parent.classList.remove("server-up", "server-concern", "server-down");
        parent.classList.add(
          level === "crit"
            ? "server-down"
            : level === "warn"
              ? "server-concern"
              : "server-up",
        );
        parent.classList.toggle("tab-alert", level === "warn");
        parent.classList.toggle("tab-alert-red", level === "crit");
        viewNav.updateSystemStatusTab();
      }
    },
  };

  // PC health contributes to the top-level status even if PC Monitor has never
  // been opened during this browser session.
  void PCM.pollTabs();
  setInterval(() => void PCM.pollTabs(), 15000);

  if (navPcMonitor) {
    navPcMonitor.querySelectorAll("[data-pc]").forEach((tab) => {
      tab.addEventListener("click", () => {
        viewNav.setActive(
          navPcMonitor,
          '[data-nav="pc-monitor"][data-pc]',
          tab,
        );
        viewNav.activateView("pc-monitor");
        PCM.show(tab.dataset.pc);
      });
    });
    const backPcMonitor = doc.getElementById("btn-back-pc-monitor");
    if (backPcMonitor) {
      backPcMonitor.addEventListener("click", () => {
        PCM.stopPoll();
        navPcMonitor.classList.add("hidden");
        viewNav.returnToStatus("pc-monitor");
      });
    }
  }

  return PCM;
}
