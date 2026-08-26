// model-stats.js — Model Stats tab: per-OAuth/CLI session token usage.
//
// Sub-nav tab per source; each shows usage windows as progress bars (red at
// 100% with reset time), plus a Rate of Change bar (burn rate) and a slow-leak
// badge. Tab colours reflect status so an exhausted account is caught at a
// glance. Card HTML comes from js/abstract/model-stats-render.js.

import {
  fmtCountdown,
  renderModelStats,
} from "../abstract/model-stats-render.js";
import { TextUtils } from "../abstract/text-utils.js";
import {
  AgentAssignmentsController,
  ModelStatsHealthMonitor,
} from "../implementation/index.js";

const esc = TextUtils.esc;
const AGENT_ASSIGNMENTS_SOURCE = "agent-assignments";

export function createModelStats({ doc = document, http, nav, viewNav }) {
  const navModelStats = nav.modelStats;

  const agentAssignments = new AgentAssignmentsController({
    http,
    el: (tag, props = {}) => Object.assign(doc.createElement(tag), props),
    container: doc.getElementById("model-stats-agents"),
    onStatus: (msg, isError) =>
      console[isError ? "error" : "log"]("agent-assignments:", msg),
  });

  const modelStatsHealth = new ModelStatsHealthMonitor({
    http,
    onStatus: viewNav.updateSystemStatusTab,
  });

  const MS = {
    pollTimer: null,
    current: null,
    stopPoll() {
      if (this.pollTimer) {
        clearInterval(this.pollTimer);
        this.pollTimer = null;
      }
      agentAssignments.stop();
    },
    open() {
      if (!navModelStats) return;
      this.stopPoll();
      const first = navModelStats.querySelector("[data-source]");
      if (first) {
        viewNav.setActive(
          navModelStats,
          '[data-nav="model-stats"][data-source]',
          first,
        );
        this.show(first.dataset.source);
      }
      this.pollColors();
      this.pollTimer = setInterval(() => {
        if (this.current && this.current !== AGENT_ASSIGNMENTS_SOURCE) {
          this.show(this.current);
        }
        this.pollColors();
      }, 120000);
    },
    async show(key) {
      const body = doc.getElementById("model-stats-body");
      const agentsPanel = doc.getElementById("model-stats-agents");
      if (!body || !agentsPanel) return;
      this.current = key;

      if (key === AGENT_ASSIGNMENTS_SOURCE) {
        body.classList.add("hidden");
        agentsPanel.classList.remove("hidden");
        agentAssignments.start();
        return;
      }
      agentAssignments.stop();
      agentsPanel.classList.add("hidden");
      body.classList.remove("hidden");
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
      await modelStatsHealth.poll();
    },
  };

  // One shared ticker drives every [data-countdown-until] span on the page and
  // re-fetches the card once a deadline passes, so the tab flips back to green
  // on its own without the user reloading.
  setInterval(() => {
    doc.querySelectorAll("[data-countdown-until]").forEach((el) => {
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

  modelStatsHealth.start();

  if (navModelStats) {
    navModelStats.querySelectorAll("[data-source]").forEach((tab) => {
      tab.addEventListener("click", () => {
        viewNav.setActive(
          navModelStats,
          '[data-nav="model-stats"][data-source]',
          tab,
        );
        viewNav.activateView("model-stats");
        MS.show(tab.dataset.source);
      });
    });
    const backMS = doc.getElementById("btn-back-model-stats");
    if (backMS) {
      backMS.addEventListener("click", () => {
        MS.stopPoll();
        navModelStats.classList.add("hidden");
        viewNav.returnToStatus("model-stats");
      });
    }
    const msBody = doc.getElementById("model-stats-body");
    if (msBody) {
      msBody.addEventListener("click", async (e) => {
        const btn = e.target.closest("[data-mute-source]");
        if (!btn) return;
        const source = btn.dataset.muteSource;
        const nextMuted = btn.dataset.muted !== "1";
        btn.disabled = true;
        try {
          await http.postJSON("/api/model-stats-mute", {
            source,
            muted: nextMuted,
          });
        } catch (e2) {
          console.error("model-stats-mute failed", e2);
        }
        if (MS.current === source) await MS.show(source);
        MS.pollColors();
      });
    }
  }

  return MS;
}
