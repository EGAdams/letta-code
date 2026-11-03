// Pure mapping/rendering for the Poll Settings Star Trek Bridge workflow.
// The task ledger is deliberately treated as coarse telemetry: it does not
// claim progress through ADW/Codex substeps that the API does not expose.
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

export function workerPalette() {
  return PALETTE.map((entry) => ({ ...entry }));
}

function workerKey(task, index) {
  const raw = String(
    task.worker_id ?? task.worker ?? task.agent ?? `worker${index + 1}`,
  ).trim();
  return raw || `worker${index + 1}`;
}

function paletteEntry(key, used) {
  const lower = key.toLowerCase().replace(/[^a-z0-9]/g, "");
  const numbered = Number(lower.match(/worker(\d+)/)?.[1]);
  if (numbered && numbered <= PALETTE.length) return PALETTE[numbered - 1];
  const available = PALETTE.find((entry) => !used.has(entry.key));
  return available || PALETTE[used.size % PALETTE.length];
}

export function normalizeWorkers(payload) {
  if (!payload?.tasks_available) {
    const heartbeat = payload?.worker;
    if (
      !heartbeat ||
      !heartbeat.status ||
      ["unknown", "inactive", "disabled"].includes(
        String(heartbeat.status).toLowerCase(),
      )
    )
      return [];
    const entry = PALETTE[0];
    return [
      {
        key: "worker1",
        name: heartbeat.name || "Bridge worker",
        taskIds: ["not available"],
        status: String(heartbeat.status).toLowerCase(),
        color: entry.color,
        className: entry.className,
      },
    ];
  }
  const tasks = Array.isArray(payload.tasks) ? payload.tasks : [];
  const byKey = new Map();
  const used = new Set();
  tasks.forEach((task, index) => {
    const key = workerKey(task, index);
    const current = byKey.get(key) || {
      key,
      name: String(task.worker ?? task.agent ?? key),
      taskIds: [],
      status: "unknown",
    };
    const entry = paletteEntry(key, used);
    used.add(entry.key);
    current.color = entry.color;
    current.className = entry.className;
    current.taskIds.push(String(task.id ?? "—"));
    current.status = String(task.status ?? "unknown").toLowerCase();
    byKey.set(key, current);
  });
  return [...byKey.values()];
}

export function coarseStage(status) {
  const value = String(status || "").toLowerCase();
  if (value === "queued" || value === "pending") return 2;
  if (["running", "active", "processing", "working"].includes(value)) return 3;
  if (
    [
      "succeeded",
      "success",
      "completed",
      "failed",
      "error",
      "cancelled",
    ].includes(value)
  )
    return 4;
  return 0;
}

function workerMarkers(workers, step) {
  return workers
    .filter((worker) => coarseStage(worker.status) === step)
    .map(
      (worker, index) =>
        `<circle class="bridge-worker-marker ${esc(worker.className)} ${step === 3 ? "is-processing" : ""}" cx="${155 + index * 22}" cy="${step === 3 ? 252 : 100}" r="9" aria-label="${esc(worker.name)} ${esc(worker.status)}" style="--worker-color:${esc(worker.color)}"><title>${esc(worker.name)}: ${esc(worker.status)}</title></circle>`,
    )
    .join("");
}

export function renderWorkerLegend(payload) {
  const workers = normalizeWorkers(payload);
  if (!payload?.tasks_available && !workers.length)
    return `<div class="worker-legend" aria-live="polite"><h2>Worker legend</h2><p class="worker-legend-empty">Task activity unavailable; no worker activity inferred.</p></div>`;
  if (!workers.length)
    return `<div class="worker-legend" aria-live="polite"><h2>Worker legend</h2><p class="worker-legend-empty">No workers in the supplied snapshot.</p></div>`;
  return `<div class="worker-legend" aria-live="polite"><h2>Worker legend</h2>${workers.map((worker) => `<div class="worker-legend-row"><span class="worker-swatch ${esc(worker.className)}" style="--worker-color:${esc(worker.color)}" aria-hidden="true"></span><span><strong>${esc(worker.name)}</strong><small>task ${esc(worker.taskIds.join(", "))} · <span class="worker-status">${esc(worker.status)}</span></small></span></div>`).join("")}</div>`;
}

export function renderBridgeWorkflow(payload) {
  const workers = normalizeWorkers(payload);
  const unavailable = !payload?.tasks_available;
  const loopActive = workers.some((worker) => coarseStage(worker.status) === 3);
  const active = (step) =>
    workers.some((worker) => coarseStage(worker.status) === step);
  const step = (number, title, detail, markerStep = number) =>
    `<g class="bridge-step ${active(markerStep) ? "has-active" : ""}"><rect x="${number === 1 ? 24 : number === 2 ? 240 : number === 3 ? 456 : 672}" y="${number === 3 ? 190 : 52}" width="176" height="116" rx="12"/><text x="${number === 1 ? 38 : number === 2 ? 254 : number === 3 ? 470 : 686}" y="78" class="bridge-number">${number}</text><text x="${number === 1 ? 62 : number === 2 ? 278 : number === 3 ? 494 : 710}" y="79" class="bridge-step-title">${esc(title)}</text><text x="${number === 1 ? 38 : number === 2 ? 254 : number === 3 ? 470 : 686}" y="112" class="bridge-step-detail">${esc(detail)}</text>${markerStep === number ? workerMarkers(workers, markerStep) : ""}</g>`;
  return `<section class="bridge-workflow" aria-labelledby="bridge-workflow-title"><div class="bridge-workflow-heading"><div><h3 id="bridge-workflow-title">Live Star Trek Bridge workflow</h3><p>Coarse task state from the real worker ledger; internal ADW steps are not exposed by this API.</p></div><span class="bridge-telemetry ${unavailable ? "is-muted" : ""}">${unavailable ? "Telemetry unavailable" : `${workers.length} worker${workers.length === 1 ? "" : "s"} observed`}</span></div><svg class="bridge-workflow-svg" viewBox="0 0 872 330" role="img" aria-label="Request from EG Android through the connector and processing loop to the result"><defs><marker id="bridge-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z"/></marker></defs><path class="bridge-arrow" d="M200 110 H238" marker-end="url(#bridge-arrow)"/><path class="bridge-arrow" d="M416 110 H454" marker-end="url(#bridge-arrow)"/><path class="bridge-arrow" d="M632 248 H670" marker-end="url(#bridge-arrow)"/>${step(1, "EG Android", "request")}${step(2, "Bridge connector", "submit / queue")}${step(3, "Processing loop", loopActive ? "worker running" : "waiting", 3)}${step(4, "Result", "returned to ChatGPT", 4)}<path class="bridge-loop ${loopActive ? "is-active" : ""}" d="M544 190 V154 Q544 136 526 136 H472 Q454 136 454 154 V190" marker-end="url(#bridge-arrow)"/></svg><p class="bridge-workflow-note">${unavailable ? esc(payload?.tasks_error || "No task ledger is configured.") : "Colored markers show workers at the API-observed coarse state. Gray steps have no active worker."}</p></section>`;
}
