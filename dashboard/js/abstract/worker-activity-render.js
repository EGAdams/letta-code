// Pure rendering for System Status > Worker Activity. No DOM or network access.
// The page is split into parts so the controller can redraw only the part
// whose data changed (the SVG is not rebuilt on every heartbeat tick).
import { renderBridgeWorkflow, statusGroup } from "./bridge-workflow-render.js";
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
const MAX_FAILURES = 5;

/** The bridge worker's own heartbeat (systemd + state file). Changes often. */
export function renderWorkerHealth(payload) {
  if (!payload) return '<p class="am-dim">Checking&hellip;</p>';
  if (payload.ok === false && payload.fetch_error) {
    return `<p class="worker-activity-health am-warn"><strong>Worker telemetry request failed:</strong> ${esc(payload.fetch_error)}</p>`;
  }
  const worker = payload.worker || {};
  const service = worker.service || {};
  return `<p class="worker-activity-health"><strong>Bridge worker:</strong> ${esc(worker.status || "unknown")} — ${esc(worker.reason || "No reason reported.")} <span class="am-dim">(service: ${esc(service.active || "unknown")})</span></p>`;
}

/** The live workflow SVG, always present; ids are prefixed for this page. */
export function renderWorkerWorkflow(payload) {
  return renderBridgeWorkflow(payload, { idPrefix: "worker-activity" });
}

function renderFailures(tasks) {
  const failed = tasks
    .filter((task) => statusGroup(task.status) === "failed")
    .slice(0, MAX_FAILURES);
  if (!failed.length) return "";
  const items = failed
    .map(
      (task) =>
        `<li><strong>${esc(task.id ?? "—")}</strong> · ${esc(task.agent ?? "—")} · ${esc(task.operation ?? "—")} in ${esc(task.workspace ?? "—")} · ${esc(task.last_update ?? "—")} · attempts ${esc(task.attempts ?? "—")}<br><span class="worker-failure-error">${esc(task.error || "No error text recorded.")}</span></li>`,
    )
    .join("");
  return `<div class="worker-activity-failures"><h3>Recent failures</h3><ul>${items}</ul></div>`;
}

/** Failures, stagnation warning and the ledger table; or the unavailable notice. */
export function renderWorkerTasks(payload) {
  if (!payload) return "";
  if (!payload.tasks_available) {
    return `<div class="worker-activity-unavailable"><strong>Task activity unavailable</strong><p>${esc(payload.tasks_error || payload.fetch_error || "No task source reported.")}</p><p class="am-dim">Task counts, worker positions and queue health are not inferred without a real task ledger.</p></div>`;
  }
  const tasks = payload.tasks || [];
  const rows = tasks
    .map(
      (task) =>
        `<tr class="worker-task-${esc(statusGroup(task.status))}">${fields.map(([key]) => `<td>${esc(task[key] ?? "—")}</td>`).join("")}</tr>`,
    )
    .join("");
  const warning = tasks.some(
    (task) =>
      statusGroup(task.status) === "queued" && Number(task.attempts) === 0,
  )
    ? '<p class="am-warn">Warning: queued work with zero attempts may be stagnant. This is a queue signal, not a worker diagnosis.</p>'
    : "";
  return `${renderFailures(tasks)}${warning}<div class="worker-activity-table-wrap"><table class="worker-activity-table"><thead><tr>${fields.map(([, label]) => `<th>${label}</th>`).join("")}</tr></thead><tbody>${rows || '<tr><td colspan="10">No tasks in the supplied snapshot.</td></tr>'}</tbody></table></div>`;
}

/** Whole page, for first paint. */
export function renderWorkerActivity(payload) {
  return `<div data-worker-part="health">${renderWorkerHealth(payload)}</div><div data-worker-part="workflow">${renderWorkerWorkflow(payload)}</div><div data-worker-part="tasks">${renderWorkerTasks(payload)}</div><p class="worker-activity-footer"><button type="button" data-worker-activity="refresh">Refresh now</button> <span class="am-dim" data-worker-part="updated"></span></p>`;
}

export function workerTabClass(payload) {
  if (!payload || payload.ok === false) return "poll-disabled";
  if (!payload.tasks_available) return "server-concern";
  return "server-up";
}
