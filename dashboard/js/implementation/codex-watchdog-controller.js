import { PollingController } from "../abstract/polling-controller.interface.js";

/** 45 -> "45s", 730 -> "12m", 4700 -> "1h 18m". */
export function formatElapsed(seconds) {
  const s = Math.max(0, Math.round(Number(seconds) || 0));
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s`;
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
}

export function formatTimestamp(ts) {
  const n = Number(ts);
  if (!n) return "unknown time";
  return new Date(n * 1000).toLocaleString();
}

/**
 * Which of the watchdog's own thresholds a session currently reads as.
 *
 * Mirrors `evaluate()`'s policy in health/codex_watchdog.py so a viewer sees
 * the same read the daemon acts on, not a second opinion: a watched session
 * (no autonomous flag) is never a target no matter its quota, a stopped
 * autonomous one reads as at-risk regardless of quota, and otherwise the
 * quota percentage against the same warn/kill bands decides the colour.
 */
export function sessionStatusClass(session) {
  if (!session.autonomous) return "is-watched";
  if (String(session.state || "").startsWith("T")) return "is-stopped";
  const pct = Number(session.primary_used_percent);
  if (Number.isFinite(pct) && pct >= 90) return "is-critical";
  if (Number.isFinite(pct) && pct >= 70) return "is-warning";
  return "is-ok";
}

/**
 * Renders the local Codex CLI quota watchdog panel on Server Management:
 * which sessions are running right now and what the watchdog has done about
 * them. A 10s cadence is plenty -- unlike the Claude SDK activity feed this
 * narrates nothing live, it is a safety-net readout.
 */
export class CodexWatchdogController extends PollingController {
  constructor({ http, doc = document, ...opts } = {}) {
    super({ intervalMs: 10000, ...opts });
    if (!http) throw new Error("CodexWatchdogController requires http");
    this._http = http;
    this._doc = doc;
    this._summary = doc.getElementById("codex-watchdog-summary");
    this._sessions = doc.getElementById("codex-watchdog-sessions");
    this._actions = doc.getElementById("codex-watchdog-actions");
    this._note = doc.getElementById("codex-watchdog-note");
  }

  async poll() {
    let payload;
    try {
      payload = await this._http.getJSON("/api/codex-watchdog-status");
    } catch (error) {
      this._showUnavailable(error.message);
      return;
    }
    if (!payload || typeof payload !== "object") {
      this._showUnavailable("empty codex-watchdog response");
      return;
    }
    this._render(payload);
  }

  _showUnavailable(detail) {
    if (this._summary) {
      this._summary.textContent = "unavailable";
      this._summary.className = "codex-watchdog-summary is-error";
    }
    if (this._note) this._note.textContent = `Codex watchdog — ${detail}`;
  }

  _render(payload) {
    const sessions = Array.isArray(payload.sessions) ? payload.sessions : [];
    const autonomous = sessions.filter((s) => s.autonomous);
    const atRisk = autonomous.filter((s) => {
      const cls = sessionStatusClass(s);
      return (
        cls === "is-warning" || cls === "is-critical" || cls === "is-stopped"
      );
    });

    if (this._summary) {
      this._summary.textContent = autonomous.length
        ? `${autonomous.length} autonomous session${autonomous.length === 1 ? "" : "s"} running` +
          (atRisk.length ? ` — ${atRisk.length} at risk` : "")
        : "No autonomous Codex sessions running";
      this._summary.className = `codex-watchdog-summary${atRisk.length ? " is-warning" : ""}`;
    }
    this._renderSessions(sessions);
    this._renderActions(
      Array.isArray(payload.recent_actions) ? payload.recent_actions : [],
    );
    if (this._note) {
      const t = payload.thresholds || {};
      const trouble =
        payload.ok === false && payload.error ? ` — ${payload.error}` : "";
      this._note.textContent =
        `Kill ≥${t.kill_percent ?? "?"}% · warn ≥${t.warn_percent ?? "?"}% ` +
        `· max concurrent ${t.max_concurrent ?? "?"}${trouble}`;
    }
  }

  _renderSessions(sessions) {
    if (!this._sessions) return;
    this._sessions.innerHTML = "";
    const doc = this._sessions.ownerDocument || this._doc;
    if (!sessions.length) {
      this._sessions.appendChild(
        this._emptyRow(doc, "No Codex CLI processes detected on this box."),
      );
      return;
    }
    for (const session of sessions) {
      const row = doc.createElement("div");
      row.className = `codex-watchdog-session ${sessionStatusClass(session)}`;
      const pct = Number(session.primary_used_percent);
      const head = doc.createElement("b");
      head.textContent =
        `pgid ${session.pgid} — ${session.autonomous ? "autonomous" : "watched"}` +
        (Number.isFinite(pct) ? ` — ${pct.toFixed(0)}% quota` : "");
      const detail = doc.createElement("span");
      detail.textContent = `${session.state || "?"} · ${formatElapsed(session.elapsed_seconds)} · ${session.cwd || "?"}`;
      row.append(head, detail);
      this._sessions.appendChild(row);
    }
  }

  _renderActions(actions) {
    if (!this._actions) return;
    this._actions.innerHTML = "";
    const doc = this._actions.ownerDocument || this._doc;
    if (!actions.length) {
      this._actions.appendChild(
        this._emptyRow(doc, "No watchdog actions recorded yet."),
      );
      return;
    }
    for (const action of [...actions].reverse()) {
      const row = doc.createElement("div");
      const isKill = String(action.action || "").startsWith("terminate");
      row.className = `codex-watchdog-action ${isKill ? "is-kill" : "is-warn"}`;
      const head = doc.createElement("b");
      head.textContent = `${formatTimestamp(action.timestamp)} — ${action.action}`;
      const detail = doc.createElement("span");
      detail.textContent = `pgid ${action.pgid} — ${action.reason}`;
      row.append(head, detail);
      this._actions.appendChild(row);
    }
  }

  _emptyRow(doc, text) {
    const empty = doc.createElement("div");
    empty.className = "codex-watchdog-empty";
    empty.textContent = text;
    return empty;
  }
}
