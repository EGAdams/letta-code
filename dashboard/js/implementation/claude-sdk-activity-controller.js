import { PollingController } from "../abstract/polling-controller.interface.js";

const CATEGORIES = ["thoughts", "tool_calls", "messages"];

function eventText(event) {
  if (event.category !== "tool_calls") return String(event.text || "");
  const input =
    event.input && Object.keys(event.input).length
      ? `\n${JSON.stringify(event.input, null, 2)}`
      : "";
  return `${event.tool || event.text || "Tool"}${input}`;
}

function statusText(run) {
  if (!run) return "Ready — waiting for the next run_claude_code_sdk call.";
  const where = run.working_dir ? ` in ${run.working_dir}` : "";
  if (run.status === "running") {
    return `Running ${run.model || "Claude"}${where}…`;
  }
  const labels = {
    complete: "Completed",
    cancelled: "Cancelled",
    timed_out: "Timed out",
    error: "Failed",
  };
  return `${labels[run.status] || run.status || "Finished"}${where}.`;
}

export class ClaudeSdkActivityController extends PollingController {
  constructor({ http, doc = document, ...opts } = {}) {
    super({ intervalMs: 1000, ...opts });
    if (!http) throw new Error("ClaudeSdkActivityController requires http");
    this._http = http;
    this._status = doc.getElementById("claude-sdk-live-status");
    this._progress = doc.getElementById("claude-sdk-live-progress");
    this._panes = Object.fromEntries(
      CATEGORIES.map((category) => [
        category,
        doc.getElementById(`claude-sdk-${category.replace("_", "-")}`),
      ]),
    );
    this._lastSignature = "";
  }

  async poll() {
    let payload;
    try {
      payload = await this._http.getJSON("/api/claude-sdk-activity");
    } catch (error) {
      this._showUnavailable(error.message);
      return;
    }
    if (!payload?.ok) {
      this._showUnavailable(payload?.error || "activity endpoint unavailable");
      return;
    }

    const run = payload.current_run || null;
    if (this._status) {
      this._status.textContent = statusText(run);
      this._status.className = `claude-sdk-live-status is-${run?.status || "idle"}`;
    }
    this._progress?.classList.toggle("is-running", run?.status === "running");

    const events = Array.isArray(payload.events) ? payload.events : [];
    const signature = `${events.at(-1)?.seq || 0}:${events.length}`;
    if (signature === this._lastSignature) return;
    this._lastSignature = signature;
    for (const category of CATEGORIES) {
      this._renderPane(
        category,
        events.filter((event) => event.category === category),
      );
    }
  }

  _showUnavailable(detail) {
    if (this._status) {
      this._status.textContent = `Activity unavailable — ${detail}`;
      this._status.className = "claude-sdk-live-status is-error";
    }
    this._progress?.classList.remove("is-running");
  }

  _renderPane(category, events) {
    const pane = this._panes[category];
    if (!pane) return;
    pane.innerHTML = "";
    if (!events.length) {
      const empty =
        pane.ownerDocument?.createElement?.("div") ||
        pane._doc?.createElement?.("div");
      if (empty) {
        empty.className = "claude-sdk-empty";
        empty.textContent = `No ${category.replace("_", " ")} emitted yet.`;
        pane.appendChild(empty);
      }
      return;
    }
    const doc = pane.ownerDocument || pane._doc || document;
    for (const event of events) {
      const row = doc.createElement("div");
      row.className = "claude-sdk-event";
      const stamp = doc.createElement("time");
      stamp.textContent = new Date(
        Number(event.timestamp || 0) * 1000,
      ).toLocaleTimeString();
      const text = doc.createElement("pre");
      text.textContent = eventText(event);
      row.append(stamp, text);
      pane.appendChild(row);
    }
    pane.scrollTop = pane.scrollHeight;
  }
}

export { eventText, statusText };
