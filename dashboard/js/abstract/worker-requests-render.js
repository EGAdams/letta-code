// Pure rendering of the Star Trek Bridge gateway's request supervision
// (agent_blocks gateway/src/RequestWatch.php), as relayed in
// /api/worker-activity's `requests`. A request is the user's ask, above its
// tasks: it stays here until it is completed with evidence, or failed or
// cancelled with a reason. No DOM or network access.
import { TextUtils } from "./text-utils.js";

const esc = TextUtils.esc;

const TIMER_LABELS = {
  ok: "on track",
  not_assigned: "nothing assigned yet",
  no_progress: "no progress",
  warning: "WARNING: stalled",
  escalated: "ESCALATED",
  closed: "closed",
};

export function requestTimerClass(timer) {
  if (timer === "escalated") return "am-bad";
  if (
    timer === "warning" ||
    timer === "no_progress" ||
    timer === "not_assigned"
  )
    return "am-warn";
  return "";
}

function watchLine(state) {
  const w = state?.watch || {};
  const ago = w.checked_seconds_ago;
  const refresh = w.refresh_seconds;
  if (typeof ago !== "number")
    return `<p class="am-warn">Gateway watch health is unknown.</p>`;
  // The cron runs bin/watch.php every 5 min; any client call refreshes sooner.
  const late = ago > 600;
  return `<p class="${late ? "am-warn" : "am-dim"}">Gateway watch last checked ${esc(String(ago))} s ago${refresh ? ` (refreshes every ${esc(String(refresh))} s on any call; cron every 5 min)` : ""}${late ? " — later than expected" : ""}.</p>`;
}

function deliverables(list) {
  return (Array.isArray(list) ? list : [])
    .filter((d) => d && typeof d === "object")
    .map(
      (d) =>
        `${esc(d.label || d.key)}: <strong>${esc(d.status || "unknown")}</strong>${d.evidence ? ` <span class="am-dim">(${esc(d.evidence)})</span>` : ""}`,
    )
    .join("<br>");
}

function row(r) {
  const timer = r.timer || "ok";
  const children = (Array.isArray(r.child_tasks) ? r.child_tasks : [])
    .map(
      (t) =>
        `${esc(t.task_id)} ${esc(t.operation || "")} <em>${esc(t.state || "")}</em>${t.status_check ? " (check)" : ""}`,
    )
    .join("<br>");
  const pending = (Array.isArray(r.pending) ? r.pending : [])
    .map((p) => esc(p))
    .join("<br>");
  const blocked = r.blocked_on
    ? `<p class="am-warn">Blocked on: ${esc(r.blocked_on)}${r.blocked_owner ? ` — owner ${esc(r.blocked_owner)}` : ""}</p>`
    : "";
  const escalations = Array.isArray(r.escalations) ? r.escalations.length : 0;
  return `<tr data-request-id="${esc(r.request_id)}"><td><strong>${esc(r.title)}</strong><br><span class="am-dim">${esc(r.request_id)} · ${esc(r.client || "")}</span>${blocked}</td><td>${esc(r.phase || "")}<br><span class="${requestTimerClass(timer)}">${esc(TIMER_LABELS[timer] || timer)}</span></td><td>${esc(r.since_progress || "")}${escalations ? `<br>${escalations} escalation event(s)` : ""}${r.recovery_attempts ? `<br>${esc(String(r.recovery_attempts))} recovery attempt(s)` : ""}</td><td>${esc(r.responsible || "")}</td><td>${deliverables(r.deliverables)}${pending ? `<br><span class="am-dim">${pending}</span>` : ""}</td><td>${children || '<span class="am-dim">none</span>'}</td></tr>`;
}

export function renderWorkerRequests(payload) {
  const state = payload?.requests;
  const head = `<h3>Supervised requests (Star Trek Bridge gateway)</h3>`;
  if (!state?.available) {
    return `<section aria-label="Supervised requests">${head}<p class="am-warn">${esc(state?.reason || "Request supervision unavailable.")} Requests are not known to be clear.</p></section>`;
  }
  const open = (Array.isArray(state.open) ? state.open : []).filter(
    (r) => r && typeof r === "object",
  );
  const closed = (
    Array.isArray(state.recently_closed) ? state.recently_closed : []
  ).filter((r) => r && typeof r === "object");
  const t = state.thresholds || {};
  const rules = `<p class="am-dim">Timers: assign ${esc(String(t.accept_seconds ?? "?"))} s · no progress ${esc(String(t.progress_seconds ?? "?"))} s · visible warning ${esc(String(t.warn_seconds ?? "?"))} s · escalate ${esc(String(t.escalate_seconds ?? "?"))} s. Status checks and heartbeats are not progress. A print counts only at spooler completion, and that is not proof paper came out.</p>`;
  const table = open.length
    ? `<table><thead><tr><th>Request</th><th>Phase</th><th>Since progress</th><th>Responsible</th><th>Deliverables / pending</th><th>Child tasks</th></tr></thead><tbody>${open.map(row).join("")}</tbody></table>`
    : `<p>No open requests on the gateway.</p>`;
  const recent = closed.length
    ? `<details><summary>Closed in the last day (${closed.length})</summary><ul>${closed
        .map(
          (r) =>
            `<li>${esc(r.title)} — <strong>${esc(r.state)}</strong>${r.outcome ? `: ${esc(r.outcome)}` : ""}</li>`,
        )
        .join("")}</ul></details>`
    : "";
  return `<section aria-label="Supervised requests">${head}${watchLine(state)}${table}${recent}${rules}</section>`;
}
