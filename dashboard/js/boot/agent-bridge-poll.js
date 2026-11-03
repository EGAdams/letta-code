// agent-bridge-poll.js — the Poll Settings tab under System Status.
//
// Asks /api/agent-bridge-poll every 5 s from boot, so the tab's colour is right
// before anyone opens it: green while the ChatGPT bridge worker is polling,
// grey with white letters when it is stopped, disabled or paused outside its
// active hours. That endpoint only reads two local files and asks systemd --
// it never reaches HostGator, so this cadence costs the gateway nothing.
//
// While the page is open a 250 ms tick redraws the Windows 2000 progress bar
// from the worker's next-check time. The sequence diagram is rendered once,
// through the shared MermaidView (wheel zoom, drag pan), with Mermaid and
// svg-pan-zoom loaded from the CDN only the first time the page opens.

import {
  formValues,
  readForm,
  withTyped,
} from "../abstract/agent-bridge-poll-form.js";
import {
  countdown,
  pollSequenceDiagram,
  progressLabel,
  renderPollPage,
} from "../abstract/agent-bridge-poll-render.js";
import { renderBridgeWorkflow } from "../abstract/bridge-workflow-render.js";
import { TextUtils } from "../abstract/text-utils.js";
import { MermaidView } from "../plans/mermaid-view.js";
import { taskSignature } from "./worker-activity.js";

const esc = TextUtils.esc;

const POLL_MS = 5000;
const SAVE_URL = "/api/agent-bridge-poll/settings";
const SAVE_TIMEOUT_MS = 120000; // the ADW waits for the restarted worker's first check
const TICK_MS = 250;
const MERMAID_SRC =
  "https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js";
const PANZOOM_SRC =
  "https://cdn.jsdelivr.net/npm/svg-pan-zoom@3.6.1/dist/svg-pan-zoom.min.js";

/** Tab colour from the payload: only 'active' is green. */
export function tabClassFor(payload) {
  return payload && payload.polling === "active"
    ? "server-up"
    : "poll-disabled";
}

function loadScript(doc, src) {
  return new Promise((resolve, reject) => {
    const existing = doc.querySelector(`script[data-src="${src}"]`);
    if (existing) {
      if (existing.dataset.loaded === "1") resolve();
      else existing.addEventListener("load", () => resolve());
      return;
    }
    const s = doc.createElement("script");
    s.src = src;
    s.dataset.src = src;
    s.onload = () => {
      s.dataset.loaded = "1";
      resolve();
    };
    s.onerror = () => reject(new Error(`could not load ${src}`));
    doc.head.append(s);
  });
}

// `workerFeed` is the Worker Activity controller: the one reader of
// /api/worker-activity. This page only draws what it publishes.
export function createAgentBridgePoll({
  doc = document,
  win = window,
  http,
  workerFeed = null,
}) {
  const tab = doc.getElementById("btn-poll-settings");
  const body = doc.getElementById("poll-settings-body");

  const ABP = {
    last: null,
    offsetMs: 0,
    diagramFor: "",
    workflowPayload: null,
    workflowSignature: "",
    edit: {}, // {editing, saving, ok, message, problems}; see renderPollPage
    paintTab(payload) {
      if (!tab) return;
      tab.classList.remove("server-up", "poll-disabled");
      tab.classList.add(tabClassFor(payload));
      tab.title = payload
        ? `Bridge polling: ${payload.reason}`
        : "Bridge polling: no answer";
    },
    isOpen() {
      return !!body && body.dataset.open === "1";
    },
    async poll() {
      try {
        const d = await http.getJSON("/api/agent-bridge-poll");
        this.offsetMs = d.now * 1000 - Date.now();
        const firstOrChanged =
          !this.last ||
          JSON.stringify(this.last.settings) !== JSON.stringify(d.settings) ||
          this.last.polling !== d.polling;
        this.last = d;
        this.paintTab(d);
        // Never redraw over a form someone is typing into.
        if (this.isOpen() && firstOrChanged && !this.edit.editing)
          this.render();
        else if (this.isOpen()) this.refreshStatus();
      } catch (e) {
        this.paintTab(null);
        if (this.isOpen() && !this.last)
          body.innerHTML = `<p class="am-warn">Failed to load: ${esc(e.message)}</p>`;
      }
    },
    showWorkflow(payload) {
      // Redraw the SVG only when task telemetry changed, not on every tick.
      const signature = taskSignature(payload);
      this.workflowPayload = payload;
      const host = doc.getElementById("abp-workflow");
      if (host && signature !== this.workflowSignature) {
        host.innerHTML = renderBridgeWorkflow(payload, { idPrefix: "abp" });
        this.workflowSignature = signature;
      }
    },
    render(shown = this.last) {
      if (!shown) return;
      const c = countdown(shown.state, Date.now(), this.offsetMs);
      // Keep the rendered diagram across re-renders: only the text around it changes.
      const keep = doc.getElementById("abp-diagram")?.firstElementChild || null;
      body.innerHTML = renderPollPage(shown, c, this.edit);
      const workflow = doc.createElement("div");
      workflow.id = "abp-workflow";
      workflow.innerHTML = renderBridgeWorkflow(this.workflowPayload, {
        idPrefix: "abp",
      });
      this.workflowSignature = taskSignature(this.workflowPayload);
      const workflowAnchor = body.querySelector("#abp-diagram");
      if (workflowAnchor) workflowAnchor.before(workflow);
      const host = doc.getElementById("abp-diagram");
      const code = pollSequenceDiagram(this.last);
      if (keep && this.diagramFor === code) host.append(keep);
      else void this.mountDiagram(host, code);
    },
    refreshStatus() {
      // The status line carries the check count; the rest only changes with settings.
      const fresh = doc.createElement("div");
      fresh.innerHTML = renderPollPage(
        this.last,
        countdown(this.last.state, Date.now(), this.offsetMs),
        this.edit,
      );
      const now = body.querySelector(".abp-status");
      const next = fresh.querySelector(".abp-status");
      if (now && next) now.replaceWith(next);
    },
    async mountDiagram(host, code) {
      this.diagramFor = code;
      try {
        await loadScript(doc, MERMAID_SRC);
        await loadScript(doc, PANZOOM_SRC);
        if (!this.view)
          this.view = new MermaidView({
            mermaid: win.mermaid,
            svgPanZoom: win.svgPanZoom,
            doc,
            win,
          });
        host.innerHTML = "";
        await this.view.render(host, {
          title: "Where polling fits: ChatGPT to this computer and back",
          caption:
            "Scroll to zoom, drag to pan. Numbers are the live settings above.",
          code,
        });
      } catch (e) {
        host.innerHTML = `<p class="am-warn">Diagram unavailable (${esc(e.message)}). The source is:</p><pre>${esc(code)}</pre>`;
      }
    },
    tick() {
      if (!this.isOpen() || !this.last || body.offsetParent === null) return;
      const c = countdown(this.last.state, Date.now(), this.offsetMs);
      const fill = body.querySelector(".w2k-progress-fill");
      const label = body.querySelector(".w2k-progress-label");
      const bar = body.querySelector(".w2k-progress");
      if (fill) fill.style.width = `${(c.fraction * 100).toFixed(1)}%`;
      if (label) label.textContent = progressLabel(c);
      if (bar)
        bar.setAttribute("aria-valuenow", String(Math.round(c.fraction * 100)));
      // Once the check is due, ask straight away instead of sitting at 100% for up to 5 s.
      // One extra ask per due time, so a slow check never turns into a 4-per-second loop.
      const dueAt = this.last.state?.next_check_at;
      if (c.mode === "due" && this._dueFor !== dueAt) {
        this._dueFor = dueAt;
        win.setTimeout(() => void this.poll(), 1500);
      }
    },
    startEdit() {
      this.edit = { editing: true };
      this.render();
    },
    cancelEdit() {
      this.edit = {};
      this.render();
    },
    async save(form) {
      const values = formValues(form);
      const typed = withTyped(this.last, values);
      const read = readForm(values);
      if (read.problems) {
        this.edit = {
          editing: true,
          ok: false,
          message: "Those settings were not saved.",
          problems: read.problems,
        };
        return this.render(typed);
      }
      this.edit = { editing: true, saving: true };
      this.render(typed);
      let answer;
      try {
        answer = await http.postJSON(SAVE_URL, read.payload, {
          timeout: SAVE_TIMEOUT_MS,
        });
      } catch (e) {
        answer = {
          ok: false,
          message: `Save failed: ${e.message}`,
          problems: [],
        };
      }
      if (answer.ok) {
        this.edit = { ok: true, message: answer.message };
        this.last = null; // the next answer redraws the table with the saved numbers
        await this.poll();
        if (!this.last) this.render(typed);
      } else {
        this.edit = {
          editing: true,
          ok: false,
          message: answer.message,
          problems: answer.problems || [],
        };
        this.render(typed);
      }
    },
    open() {
      if (!body) return;
      body.dataset.open = "1";
      void workerFeed?.poll();
      if (this.last) this.render();
      else body.innerHTML = '<p class="am-dim">Checking&hellip;</p>';
      void this.poll();
    },
  };

  body?.addEventListener("click", (event) => {
    const action = event.target.closest?.("[data-abp]")?.dataset.abp;
    if (action === "edit") ABP.startEdit();
    if (action === "cancel") ABP.cancelEdit();
  });
  body?.addEventListener("submit", (event) => {
    if (event.target.dataset?.abp !== "form") return;
    event.preventDefault();
    if (!ABP.edit.saving) void ABP.save(event.target);
  });
  body?.addEventListener("change", (event) => {
    if (event.target.name !== "around_clock") return;
    const form = event.target.form;
    for (const name of ["start_hour", "end_hour"])
      form.elements[name].disabled = event.target.checked;
  });

  workerFeed?.subscribe((payload) => ABP.showWorkflow(payload));
  void ABP.poll();
  win.setInterval(() => void ABP.poll(), POLL_MS);
  win.setInterval(() => ABP.tick(), TICK_MS);
  return ABP;
}
