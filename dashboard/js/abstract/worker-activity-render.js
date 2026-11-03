// Pure rendering for Worker Activity. No DOM or network access.
import { TextUtils } from "./text-utils.js";

const esc = TextUtils.esc;
const fields = [
  ["id", "ID"],
  ["agent", "Agent / worker"],
  ["operation", "Operation"],
  ["workspace", "Workspace"],
  ["status", "Status"],
  ["queue_age", "Queue age"],
  ["run_duration", "Run duration"],
  ["attempts", "Attempts"],
  ["last_update", "Last update"],
  ["error", "Error"],
];

export function renderWorkerActivity(payload) {
  if (!payload) return '<p class="am-dim">Checking&hellip;</p>';
  const worker = payload.worker || {};
  const service = worker.service || {};
  const workerLine = `<p class="worker-activity-health"><strong>Bridge worker:</strong> ${esc(worker.status || "unknown")} — ${esc(worker.reason || "No reason reported.")} <span class="am-dim">(heartbeat source: ${esc(service.active || "unknown")})</span></p>`;
  if (!payload.tasks_available) {
    return `${workerLine}<div class="worker-activity-unavailable"><strong>Task activity unavailable</strong><p>${esc(payload.tasks_error || "No task source reported.")}</p><p class="am-dim">No task count, worker offline diagnosis, or queue health is inferred without a real task ledger.</p></div><p><button type="button" data-worker-activity="refresh">Refresh</button></p>`;
  }
  const rows = (payload.tasks || [])
    .map(
      (task) =>
        `<tr class="worker-task-${esc(task.status || "unknown")}">${fields.map(([key]) => `<td>${esc(task[key] ?? "—")}</td>`).join("")}</tr>`,
    )
    .join("");
  const warning = (payload.tasks || []).some(
    (task) => task.status === "queued" && Number(task.attempts) === 0,
  )
    ? '<p class="am-warn">Warning: queued work with zero attempts may be stagnant. This is a queue signal, not a worker diagnosis.</p>'
    : "";
  return `${workerLine}${warning}<table class="worker-activity-table"><thead><tr>${fields.map(([, label]) => `<th>${label}</th>`).join("")}</tr></thead><tbody>${rows || '<tr><td colspan="10">No tasks in the supplied snapshot.</td></tr>'}</tbody></table><p><button type="button" data-worker-activity="refresh">Refresh</button></p>`;
}

export function workerTabClass(payload) {
  if (!payload?.ok) return "poll-disabled";
  if (!payload.tasks_available) return "server-concern";
  return "server-up";
}
