// Pure rendering of the independent supervisor's published observations.
import { TextUtils } from "./text-utils.js";

const esc = TextUtils.esc;

export function renderWorkerEscalation(payload) {
  const state = payload?.escalation;
  if (!state?.available) {
    return `<section aria-label="ADW supervisor"><h3>ADW supervisor</h3><p class="am-warn">${esc(state?.reason || "Supervisor telemetry unavailable.")}</p></section>`;
  }
  const warnings = [
    state.stale
      ? "Supervisor heartbeat is stale; showing last recorded observations."
      : "",
    state.ledger_stale ? "Task ledger is stale." : "",
    state.ledger_error || "",
    state.coverage_complete === true
      ? ""
      : `Incomplete coverage (coverage_complete: ${state.coverage_complete === false ? "false" : "unknown"}). ${state.coverage_reason || "Full queue coverage is unverified."}`,
  ]
    .filter(Boolean)
    .map((text) => `<p class="am-warn">${esc(text)}</p>`)
    .join("");
  const alerts = Array.isArray(state.alerts) ? state.alerts : [];
  const rows = alerts
    .filter((alert) => alert && typeof alert === "object")
    .map((alert) => {
      const events = Array.isArray(alert.recent_events)
        ? alert.recent_events
        : [];
      const messages = events
        .filter((event) => event && typeof event === "object")
        .map((event) => esc(event.message || ""))
        .join("<br>");
      return `<tr><td>${esc(alert.task_id)}</td><td>${esc(alert.tier)}</td><td>${esc(alert.observation_error || "")}${messages}</td></tr>`;
    })
    .join("");
  const status = rows
    ? `<table><thead><tr><th>Task</th><th>Escalation</th><th>Recorded recommendation</th></tr></thead><tbody>${rows}</tbody></table>`
    : `<p>${state.ok === true && !state.stale ? "No escalations in observed local tasks." : "Task health is unknown; no current escalation verdict."}</p>`;
  return `<section aria-label="ADW supervisor"><h3>ADW supervisor</h3>${warnings}${status}<p class="am-dim">Recommendations only. No model dispatch, notification delivery, or worker restart is performed.</p></section>`;
}
