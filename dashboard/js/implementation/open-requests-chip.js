/**
 * OpenRequestsChip -- a small marker, on every tab, for Star Trek Bridge
 * requests that are still stalled or blocked.
 *
 * "Got it" on an alert card hides the card for good, while the request it was
 * about stays open. This marker has no dismiss: it reads the Gateway's open
 * requests (relayed in /api/worker-activity) and goes away only when none needs
 * attention. Click it for the list and each next action. Silent: the cards do
 * the speaking.
 */

const ATTENTION = new Set(["warning", "escalated"]);
const NAMED = 12;

export function summarizeRequests(payload) {
  const state = payload?.requests;
  if (!state?.available)
    return { label: "Bridge requests: status unknown", items: [] };
  const open = (Array.isArray(state.open) ? state.open : []).filter(
    (r) => r && ATTENTION.has(r.timer),
  );
  if (!open.length) return null;
  const phases = {};
  for (const r of open) phases[r.phase] = (phases[r.phase] || 0) + 1;
  const parts = Object.entries(phases).map(([phase, n]) => `${n} ${phase}`);
  const noun = open.length === 1 ? "request needs" : "requests need";
  return {
    label: `⚠ ${open.length} Bridge ${noun} attention · ${parts.join(" · ")}`,
    items: open.map((r) => ({
      title: String(r.title || r.request_id),
      line: `${r.phase}, ${r.since_progress || "?"} without progress`,
      next: String(r.next_action || r.blocked_on || ""),
    })),
  };
}

export class OpenRequestsChip {
  constructor({
    http,
    doc = globalThis.document,
    intervalMs = 60000,
    setInterval: setIntervalFn = globalThis.setInterval?.bind(globalThis),
  } = {}) {
    if (!http) throw new Error("OpenRequestsChip requires an HttpClient");
    this._http = http;
    this._doc = doc;
    this._intervalMs = intervalMs;
    this._setInterval = setIntervalFn;
    this._box = null;
    this._button = null;
    this._list = null;
    this._open = false;
  }

  start() {
    this.poll();
    if (this._setInterval)
      this._setInterval(() => this.poll(), this._intervalMs);
  }

  async poll() {
    let payload;
    try {
      payload = await this._http.getJSON("/api/worker-activity");
    } catch {
      return; // the dashboard itself is down; keep what was last shown
    }
    this._render(summarizeRequests(payload));
  }

  _render(summary) {
    if (!summary) {
      this._box?.remove();
      this._box = null;
      return;
    }
    if (!this._box) this._mount();
    this._button.textContent = summary.label;
    this._list.textContent = "";
    for (const item of summary.items.slice(0, NAMED))
      this._line(`${item.title}\n${item.line}\nNext: ${item.next}`);
    if (summary.items.length > NAMED)
      this._line(
        `…and ${summary.items.length - NAMED} more: see Worker Activity.`,
      );
    this._list.style.display = this._open ? "block" : "none";
  }

  _line(text) {
    const line = this._doc.createElement("div");
    line.textContent = text;
    Object.assign(line.style, {
      whiteSpace: "pre-wrap",
      padding: "6px 0",
      borderTop: "1px solid rgba(255,255,255,.25)",
    });
    this._list.appendChild(line);
  }

  _mount() {
    const box = this._doc.createElement("div");
    box.id = "open-requests-chip";
    Object.assign(box.style, {
      position: "fixed",
      right: "12px",
      bottom: "12px",
      zIndex: "9999",
      maxWidth: "min(460px, calc(100vw - 24px))",
      background: "#5a3d00",
      color: "#fff",
      borderRadius: "6px",
      boxShadow: "0 2px 8px rgba(0,0,0,.4)",
      fontSize: "13px",
      overflowWrap: "anywhere",
    });
    const button = this._doc.createElement("button");
    button.type = "button";
    button.setAttribute("aria-expanded", "false");
    Object.assign(button.style, {
      display: "block",
      width: "100%",
      textAlign: "left",
      padding: "8px 12px",
      background: "transparent",
      color: "#fff",
      border: "none",
      cursor: "pointer",
      font: "inherit",
    });
    button.addEventListener("click", () => {
      this._open = !this._open;
      this._list.style.display = this._open ? "block" : "none";
      button.setAttribute("aria-expanded", String(this._open));
    });
    const list = this._doc.createElement("div");
    Object.assign(list.style, {
      display: "none",
      maxHeight: "50vh",
      overflowY: "auto",
      padding: "0 12px 8px",
    });
    box.appendChild(button);
    box.appendChild(list);
    this._doc.body.appendChild(box);
    this._box = box;
    this._button = button;
    this._list = list;
  }
}
