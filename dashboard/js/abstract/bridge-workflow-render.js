// Pure mapping/rendering for the live Star Trek Bridge workflow SVG, shared by
// System Status > Worker Activity and Poll Settings. No DOM or network access.
// The task ledger is coarse telemetry: it does not claim progress through
// ADW/Codex substeps that the API does not expose.
import { TextUtils } from "./text-utils.js";

const esc = TextUtils.esc;
const PALETTE = [
  {
    key: "worker1",
    name: "Worker 1",
    color: "#d6a900",
    className: "worker-yellow",
  },
  {
    key: "worker2",
    name: "Worker 2",
    color: "#f4f4f4",
    className: "worker-white",
  },
  {
    key: "worker3",
    name: "Worker 3",
    color: "#e87500",
    className: "worker-orange",
  },
  {
    key: "worker4",
    name: "Worker 4",
    color: "#2674d9",
    className: "worker-blue",
  },
  {
    key: "worker5",
    name: "Worker 5",
    color: "#2b9b55",
    className: "worker-green",
  },
  {
    key: "worker6",
    name: "Worker 6",
    color: "#a34db8",
    className: "worker-purple",
  },
  {
    key: "worker7",
    name: "Worker 7",
    color: "#008c95",
    className: "worker-teal",
  },
];

// Ledger status -> display group. Anything not listed is "other" and is never
// placed on the diagram, so an unknown status cannot look like progress.
const GROUPS = {
  queued: ["queued", "pending"],
  running: ["running", "active", "processing", "working"],
  completed: ["succeeded", "success", "completed"],
  failed: ["failed", "error", "timed_out"],
  cancelled: ["cancelled", "canceled"],
};
const STAGE = { queued: 2, running: 3, completed: 4, failed: 4, cancelled: 4 };

// Box geometry, one row left to right. Markers sit along each box's bottom.
const BOX = { y: 40, w: 180, h: 128 };
const BOX_X = [20, 240, 460, 680];
const MARKERS_PER_BOX = 6;

export function workerPalette() {
  return PALETTE.map((entry) => ({ ...entry }));
}

export function statusGroup(status) {
  const value = String(status || "").toLowerCase();
  return (
    Object.keys(GROUPS).find((group) => GROUPS[group].includes(value)) ||
    "other"
  );
}

export function coarseStage(status) {
  return STAGE[statusGroup(status)] || 0;
}

/** Counts of the supplied ledger rows by display group. */
export function summarizeTasks(payload) {
  const counts = {
    queued: 0,
    running: 0,
    completed: 0,
    failed: 0,
    cancelled: 0,
    other: 0,
    total: 0,
  };
  if (!payload?.tasks_available) return counts;
  for (const task of payload.tasks || []) {
    counts[statusGroup(task.status)] += 1;
    counts.total += 1;
  }
  return counts;
}

function workerKey(task, index) {
  const raw = String(
    task.worker_id ?? task.worker ?? task.agent ?? `worker${index + 1}`,
  ).trim();
  return raw || `worker${index + 1}`;
}

function paletteEntry(key, used) {
  const numbered = Number(
    key
      .toLowerCase()
      .replace(/[^a-z0-9]/g, "")
      .match(/^worker(\d+)$/)?.[1],
  );
  if (numbered && numbered <= PALETTE.length) return PALETTE[numbered - 1];
  return (
    PALETTE.find((entry) => !used.has(entry.key)) ||
    PALETTE[used.size % PALETTE.length]
  );
}

const isOpen = (task) =>
  ["queued", "running"].includes(statusGroup(task.status));

// Open work first, then newest; the ledger already sends this order, but the
// renderer must not depend on it to pick a worker's current task.
function byRelevance(a, b) {
  if (isOpen(a) !== isOpen(b)) return isOpen(a) ? -1 : 1;
  return String(b.last_update || "").localeCompare(String(a.last_update || ""));
}

/**
 * One entry per worker/agent: its current task (open work first, else the most
 * recent), plus how many rows of each group it has in the supplied snapshot.
 * Without a task ledger there are no workers: a heartbeat is not task activity.
 */
export function normalizeWorkers(payload) {
  if (!payload?.tasks_available) return [];
  const tasks = (Array.isArray(payload.tasks) ? payload.tasks : []).map(
    (task, index) => ({ task, index }),
  );
  const byKey = new Map();
  for (const { task, index } of tasks) {
    const key = workerKey(task, index);
    if (!byKey.has(key))
      byKey.set(key, {
        key,
        name: String(task.worker ?? task.agent ?? key),
        tasks: [],
      });
    byKey.get(key).tasks.push(task);
  }
  const used = new Set();
  return [...byKey.values()].map((worker) => {
    const entry = paletteEntry(worker.key, used);
    used.add(entry.key);
    const current = [...worker.tasks].sort(byRelevance)[0];
    const counts = summarizeTasks({
      tasks_available: true,
      tasks: worker.tasks,
    });
    return {
      key: worker.key,
      name: worker.name,
      color: entry.color,
      className: entry.className,
      current,
      taskIds: [String(current.id ?? "—")],
      status: String(current.status ?? "unknown").toLowerCase(),
      group: statusGroup(current.status),
      counts,
    };
  });
}

function markers(workers, stage) {
  const here = workers.filter((worker) => STAGE[worker.group] === stage);
  const x0 = BOX_X[stage - 1] + 22;
  const y = BOX.y + BOX.h - 22;
  const shown = here.slice(0, MARKERS_PER_BOX).map((worker, index) => {
    const state =
      worker.group === "running"
        ? "is-processing"
        : worker.group === "failed"
          ? "is-failed"
          : "";
    return `<circle class="bridge-worker-marker ${esc(worker.className)} ${state}" cx="${x0 + index * 24}" cy="${y}" r="9" style="--worker-color:${esc(worker.color)}"><title>${esc(worker.name)}: ${esc(worker.status)} (task ${esc(worker.taskIds[0])})</title></circle>`;
  });
  const extra = here.length - MARKERS_PER_BOX;
  if (extra > 0)
    shown.push(
      `<text class="bridge-step-detail" x="${x0 + MARKERS_PER_BOX * 24 - 8}" y="${y + 4}">+${extra}</text>`,
    );
  return shown.join("");
}

function stepBox(stage, title, detail, workers) {
  const x = BOX_X[stage - 1];
  const active = workers.some((worker) => STAGE[worker.group] === stage);
  return `<g class="bridge-step${active ? " has-active" : ""}"><rect x="${x}" y="${BOX.y}" width="${BOX.w}" height="${BOX.h}" rx="12"/><text x="${x + 14}" y="${BOX.y + 30}" class="bridge-number">${stage}</text><text x="${x + 40}" y="${BOX.y + 29}" class="bridge-step-title">${esc(title)}</text><text x="${x + 14}" y="${BOX.y + 60}" class="bridge-step-detail">${esc(detail)}</text>${markers(workers, stage)}</g>`;
}

function arrows(markerId) {
  const y = BOX.y + 52;
  return [0, 1, 2]
    .map(
      (i) =>
        `<path class="bridge-arrow" d="M${BOX_X[i] + BOX.w + 2} ${y} H${BOX_X[i + 1] - 4}" marker-end="url(#${markerId})"/>`,
    )
    .join("");
}

function loopPath(active, markerId) {
  // Runs under box 3 and comes back into it: the worker's processing loop.
  const left = BOX_X[2] + 50;
  const right = BOX_X[2] + BOX.w - 50;
  const top = BOX.y + BOX.h;
  return `<path class="bridge-loop${active ? " is-active" : ""}" d="M${right} ${top + 2} V${top + 30} Q${right} ${top + 46} ${right - 16} ${top + 46} H${left + 16} Q${left} ${top + 46} ${left} ${top + 30} V${top + 6}" marker-end="url(#${markerId})"/><text class="bridge-step-detail" x="${BOX_X[2] + BOX.w / 2}" y="${top + 66}" text-anchor="middle">processing loop</text>`;
}

/** Count chips: real counts from the snapshot, or one explicit "unavailable". */
export function renderTaskSummary(payload) {
  if (!payload) return "";
  if (!payload.tasks_available)
    return '<p class="bridge-summary is-muted">Task counts unavailable: no task ledger data.</p>';
  const c = summarizeTasks(payload);
  const chip = (group, label) =>
    `<span class="bridge-chip is-${group}">${label} <strong>${c[group]}</strong></span>`;
  const other = c.other ? chip("other", "Other") : "";
  return `<p class="bridge-summary">${chip("queued", "Queued")}${chip("running", "Running")}${chip("completed", "Completed")}${chip("failed", "Failed")}${c.cancelled ? chip("cancelled", "Cancelled") : ""}${other}<span class="bridge-summary-note">of the ${c.total} most recent ledger rows</span></p>`;
}

/**
 * The workflow SVG. `idPrefix` keeps element ids unique when more than one
 * page renders it into the same document.
 */
export function renderBridgeWorkflow(payload, { idPrefix = "bridge" } = {}) {
  const workers = normalizeWorkers(payload);
  const c = summarizeTasks(payload);
  const unavailable = !payload?.tasks_available;
  const markerId = `${idPrefix}-arrow`;
  const titleId = `${idPrefix}-workflow-title`;
  const loopActive = workers.some((worker) => worker.group === "running");
  const n = (count) => (unavailable ? "—" : String(count));
  const loading = !payload;
  const badge = loading
    ? "Checking…"
    : unavailable
      ? "Telemetry unavailable"
      : `${workers.length} worker${workers.length === 1 ? "" : "s"} observed`;
  const note = loading
    ? "Checking worker telemetry…"
    : unavailable
      ? `Task telemetry unavailable: ${payload?.tasks_error || "no task ledger is configured."} The diagram shows the route only; no worker positions are inferred.`
      : "Each colored marker is one worker at the coarse state of its current task (open work first, else its latest). Red ring = that task failed.";
  return `<section class="bridge-workflow" aria-labelledby="${esc(titleId)}"><div class="bridge-workflow-heading"><div><h3 id="${esc(titleId)}">Live Star Trek Bridge workflow</h3><p>Coarse task state from the real worker ledger; internal ADW steps are not exposed by this API.</p></div><span class="bridge-telemetry${unavailable ? " is-muted" : ""}">${badge}</span></div><svg class="bridge-workflow-svg" viewBox="0 0 880 250" role="img" aria-label="Request from EG Android through the bridge connector and processing loop to the result"><defs><marker id="${esc(markerId)}" class="bridge-arrowhead" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z"/></marker></defs>${arrows(markerId)}${stepBox(1, "EG Android", "request via ChatGPT", workers)}${stepBox(2, "Bridge connector", `queued: ${n(c.queued)}`, workers)}${stepBox(3, "Worker", `running: ${n(c.running)}`, workers)}${stepBox(4, "Result", `done ${n(c.completed)} · failed ${n(c.failed)}`, workers)}${loopPath(loopActive, markerId)}</svg>${renderTaskSummary(payload)}<p class="bridge-workflow-note${unavailable && !loading ? " is-unavailable" : ""}">${esc(note)}</p></section>`;
}

export function renderWorkerLegend(payload) {
  const head = "<h2>Worker legend</h2>";
  if (!payload)
    return `${head}<p class="worker-legend-empty">Checking worker telemetry&hellip;</p>`;
  if (!payload.tasks_available) {
    const beat = payload.worker?.status
      ? `<p class="worker-legend-empty">Bridge worker heartbeat: ${esc(payload.worker.status)}</p>`
      : "";
    return `${head}<p class="worker-legend-empty">Task activity unavailable; no worker activity inferred.</p>${beat}`;
  }
  const workers = normalizeWorkers(payload);
  if (!workers.length)
    return `${head}<p class="worker-legend-empty">No workers in the supplied snapshot.</p>`;
  return `${head}${workers
    .map(
      (worker) =>
        `<div class="worker-legend-row"><span class="worker-swatch ${esc(worker.className)}${worker.group === "failed" ? " is-failed" : ""}" style="--worker-color:${esc(worker.color)}" aria-hidden="true"></span><span><strong>${esc(worker.name)}</strong><small>task ${esc(worker.taskIds.join(", "))} · <span class="worker-status is-${esc(worker.group)}">${esc(worker.status)}</span></small></span></div>`,
    )
    .join("")}`;
}
