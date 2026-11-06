// Pure rendering for System Status > Worker Activity. No DOM or network access.
// The page is split into parts so the controller can redraw only the part
// whose data changed (the SVG is not rebuilt on every heartbeat tick).
import { renderTaskSummary, statusGroup } from "./bridge-workflow-render.js";
import { TextUtils } from "./text-utils.js";
import {
  explicitWorkerEvents,
  explicitWorkerLifecycle,
  renderWorkerEvents,
} from "./worker-activity-events.js";
import { renderWorkerActivityRows } from "./worker-activity-rows-render.js";

import { renderWorkerEscalation } from "./worker-escalation-render.js";

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

/**
 * Provider selection is deliberately read-only until the bridge worker exposes
 * a provider contract.  The renderer accepts an explicit future payload shape
 * but never infers availability from local CLI files or labels.
 */
export function renderWorkerProviderSelection(payload) {
  const selection = payload?.provider_selection;
  if (!selection || typeof selection !== "object") {
    return '<section class="worker-provider-selection" aria-labelledby="worker-provider-selection-title"><h3 id="worker-provider-selection-title">Bridge worker provider</h3><p class="am-dim">Provider availability and current selection are not exposed by the bridge worker API.</p><div class="worker-provider-options"><button type="button" disabled aria-disabled="true">Codex</button><button type="button" disabled aria-disabled="true">Claude Sonnet</button></div><p class="am-dim">Selection is unavailable until the worker adds a backend provider contract.</p></section>';
  }
  const providers = Array.isArray(selection.providers)
    ? selection.providers
    : [];
  const current =
    typeof selection.current === "string" ? selection.current : "";
  const options = providers
    .filter((provider) => provider && typeof provider === "object")
    .map((provider) => {
      const id = typeof provider.id === "string" ? provider.id : "";
      const label = typeof provider.label === "string" ? provider.label : id;
      const available = provider.available === true;
      const selected = current !== "" && current === id;
      const state = available
        ? selected
          ? "selected"
          : "available"
        : provider.configured
          ? "configured; runtime unverified"
          : "unavailable";
      return `<button type="button" disabled aria-disabled="true"${selected ? ' aria-current="true"' : ""}>${esc(label)} — ${state}</button>${provider.detail ? `<span class="am-dim">${esc(provider.detail)}</span>` : ""}`;
    })
    .join("");
  const note = current
    ? `Current worker selection: ${esc(current)}. Switching is not supported by this dashboard.`
    : "The worker did not report a current provider selection.";
  return `<section class="worker-provider-selection" aria-labelledby="worker-provider-selection-title"><h3 id="worker-provider-selection-title">Bridge worker provider</h3><div class="worker-provider-options">${options || '<span class="am-dim">No providers reported.</span>'}</div><p class="am-dim">${note}</p></section>`;
}

/**
 * One line per worker lane (general / express): its own process, heartbeat and
 * supervisor verdict. An installed lane that is down is flagged whichever lane
 * it is; a lane that was never installed is said to be that, not hidden.
 */
export function renderWorkerLanes(payload) {
  const lanes = Array.isArray(payload?.workers) ? payload.workers : [];
  if (!lanes.length) return "";
  const rows = lanes
    .map((lane) => {
      const down = lane.installed && !lane.healthy;
      const verdict = lane.supervisor
        ? ` · supervisor: ${esc(lane.supervisor.status || "unknown")}${lane.supervisor.action && lane.supervisor.action !== "none" ? ` (${esc(lane.supervisor.action)})` : ""}`
        : "";
      const state = !lane.installed
        ? "not installed"
        : lane.healthy
          ? "running"
          : `DOWN — ${lane.status || "unknown"}`;
      return `<li data-worker-lane="${esc(lane.lane)}" class="${down ? "am-warn" : ""}"><strong>${esc(lane.lane)}</strong>: ${esc(state)} <span class="am-dim">— ${esc(lane.description || "")}${verdict}</span>${down ? ` <span>${esc(lane.reason || "")}</span>` : ""}</li>`;
    })
    .join("");
  return `<ul class="worker-lanes" aria-label="Bridge worker lanes">${rows}</ul>`;
}

/** The bridge worker's own heartbeat (systemd + state file). Changes often. */
export function renderWorkerHealth(payload) {
  if (!payload) return '<p class="am-dim">Checking&hellip;</p>';
  if (payload.ok === false && payload.fetch_error) {
    return `<p class="worker-activity-health am-warn"><strong>Worker telemetry request failed:</strong> ${esc(payload.fetch_error)}</p>`;
  }
  const worker = payload.worker || {};
  const service = worker.service || {};
  const restart = payload.restart || {};
  const action = restart.configured
    ? '<button type="button" data-worker-activity="restart">Restart Worker</button>'
    : '<button type="button" disabled aria-disabled="true">Restart Worker</button> <span class="am-dim">Unavailable: no authenticated worker restart method is configured.</span>';
  const queue =
    payload.queue_depth == null ? "unavailable" : payload.queue_depth;
  const active =
    payload.active_worker_count == null
      ? "unavailable"
      : payload.active_worker_count;
  const diagnostic = payload.diagnostic || {};
  const reasons = Array.isArray(diagnostic.reasons)
    ? diagnostic.reasons.join("; ")
    : "No diagnostic details reported.";
  const attempts = diagnostic.queue?.attempts ?? "unavailable";
  return `<p class="worker-activity-health"><strong>Bridge worker:</strong> ${esc(diagnostic.status || worker.status || "unknown")} — ${esc(diagnostic.action || worker.reason || "No reason reported.")} <span class="am-dim">(service: ${esc(service.active || "unknown")})</span></p><p class="worker-activity-diagnostic"><strong>Evidence:</strong> ${esc(reasons)}</p><p class="worker-activity-counts"><strong>Queue depth:</strong> ${esc(queue)} · <strong>Attempts:</strong> ${esc(attempts)} · <strong>Actual worker process:</strong> ${esc(active)} <span class="am-dim">(local process inspection)</span></p>${renderWorkerLanes(payload)}<p class="worker-activity-restart">${action}</p>`;
}

/**
 * The aggregate ledger counts (queued/running/succeeded/failed/...), then the
 * five-row top-priority-jobs view; ids are prefixed for this page.
 */
export function renderWorkerWorkflow(payload, options) {
  return `${renderTaskSummary(payload)}${renderWorkerActivityRows(payload, options)}`;
}

/**
 * Builds the terminal's inner content (what belongs inside the live `<pre>`)
 * separately from the section/heading wrapper. Live polling updates rewrite
 * only the `<pre>` element in place (see worker-activity.js `updateTerminal`),
 * so this content must never itself contain the surrounding `<section>`/`<pre>`
 * markup — splicing that out of the full section via regex previously broke
 * whenever the "no explicit events" note added a second `<p>` before `<pre>`.
 */
function buildTerminal(payload) {
  if (!payload.tasks_available) {
    return {
      content: `<span class="worker-activity-terminal-empty">Live worker output is unavailable: ${esc(payload.tasks_error || payload.fetch_error || "no worker ledger reported")}</span>`,
      unavailable: false,
    };
  }
  const tasks = payload.tasks || [];
  const workerEvents = explicitWorkerEvents(tasks);
  const events = [
    ...explicitWorkerLifecycle(tasks),
    ...workerEvents,
    ...(payload.activity_events || []),
  ];
  const lines =
    events.length && workerEvents.length
      ? [renderWorkerEvents(events)]
      : tasks.map((task) => {
          const time =
            task.last_update ?? task.updated_at ?? task.created_at ?? "—";
          const agent = task.agent ?? "unknown-agent";
          const operation = task.operation ?? "worker event";
          const status = task.status ?? "unknown";
          const detail = task.error ? ` — ${task.error}` : "";
          return `${esc(`${time} [${agent}] ${operation}: ${status}${detail}`)}`;
        });
  if (events.length && !workerEvents.length)
    lines.push(renderWorkerEvents(events));
  const taskSummary = tasks
    .map(
      (task) =>
        `${esc(task.id ?? "—")} · ${esc(task.agent ?? "—")} · ${esc(task.operation ?? "—")} · ${esc(task.status ?? "unknown")} · last update ${esc(task.last_update ?? "—")}`,
    )
    .join("\n");
  const header = tasks.length ? `Task ${taskSummary}` : "";
  const content = lines.length
    ? `${header}${header ? "\n" : ""}${lines.join("\n")}`
    : '<span class="worker-activity-terminal-empty">No worker events in the supplied ledger.</span>';
  return { content, unavailable: !workerEvents.length && tasks.length };
}

/** Just the `<pre>` content, for in-place live updates of an existing terminal element. */
export function renderWorkerTerminalContent(payload) {
  if (!payload) return "";
  return buildTerminal(payload).content;
}

/** The shared worker ledger, shown as a terminal without inventing output. */
export function renderWorkerTerminal(payload) {
  if (!payload) return "";
  const { content, unavailable } = buildTerminal(payload);
  if (!payload.tasks_available) {
    return `<section class="worker-activity-terminal-section" aria-labelledby="worker-activity-terminal-title"><h3 id="worker-activity-terminal-title">Worker event output</h3><pre class="worker-activity-terminal" role="log">${content}</pre></section>`;
  }
  return `<section class="worker-activity-terminal-section" aria-labelledby="worker-activity-terminal-title"><h3 id="worker-activity-terminal-title">Worker event output</h3><p class="am-dim">Worker-supplied events are real; dashboard observations are lifecycle/polling updates. Agent internal thoughts and model activity are not exposed here.</p>${unavailable ? '<p class="worker-activity-terminal-empty">Detailed step logs are unavailable from the current worker feed.</p>' : ""}<pre class="worker-activity-terminal" role="log" aria-live="polite">${content}</pre></section>`;
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
  const stale = payload.snapshot_stale
    ? '<p class="am-warn">The task ledger is stale; these are the last recorded events, not current activity.</p>'
    : "";
  const warning = tasks.some(
    (task) =>
      statusGroup(task.status) === "queued" && Number(task.attempts) === 0,
  )
    ? '<p class="am-warn">Warning: queued work with zero attempts may be stagnant. This is a queue signal, not a worker diagnosis.</p>'
    : "";
  return `${renderFailures(tasks)}${stale}${warning}<div class="worker-activity-table-wrap"><table class="worker-activity-table"><thead><tr>${fields.map(([, label]) => `<th>${label}</th>`).join("")}</tr></thead><tbody>${rows || '<tr><td colspan="10">No tasks in the supplied snapshot.</td></tr>'}</tbody></table></div>`;
}

/** Whole page, for first paint. */
export function renderWorkerActivity(payload, options) {
  const sourceTime = payload?.snapshot_updated_at
    ? new Date(payload.snapshot_updated_at * 1000).toLocaleTimeString()
    : "";
  const updated = sourceTime
    ? `Last ledger update ${esc(sourceTime)}`
    : "Waiting for a worker ledger";
  return `<div data-worker-part="health">${renderWorkerHealth(payload)}</div><div data-worker-part="provider">${renderWorkerProviderSelection(payload)}</div><div data-worker-part="escalation">${renderWorkerEscalation(payload)}</div><div data-worker-part="workflow">${renderWorkerWorkflow(payload, options)}</div><div data-worker-part="terminal">${renderWorkerTerminal(payload)}</div><div data-worker-part="tasks">${renderWorkerTasks(payload)}</div><p class="worker-activity-footer"><button type="button" data-worker-activity="refresh">Refresh now</button> <span class="am-dim" data-worker-part="updated">${updated}</span></p>`;
}

export function workerTabClass(payload) {
  if (!payload || payload.ok === false) return "poll-disabled";
  if (!payload.tasks_available) return "server-concern";
  if ((payload.workers || []).some((lane) => lane.installed && !lane.healthy))
    return "server-concern";
  return "server-up";
}
