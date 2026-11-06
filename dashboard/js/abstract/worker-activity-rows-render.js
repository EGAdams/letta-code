// Worker Activity's top-five-jobs view: five compact rows of the same four
// stations ("EG Android" -> "Bridge connector" -> "Worker" -> "Result") as
// the original single-row bridge workflow (bridge-workflow-render.js), each
// row bound to one real, ranked task. Pure rendering: no DOM, no network, no
// fabricated jobs — a slot with no real task says so explicitly.
import { coarseStage, statusGroup } from "./bridge-workflow-render.js";
import { TextUtils } from "./text-utils.js";
import {
  explicitWorkerEvents,
  explicitWorkerLifecycle,
} from "./worker-activity-events.js";
import { rankActiveTasks } from "./worker-activity-priority.js";

const esc = TextUtils.esc;
const ROW_COUNT = 5;
const TITLES = ["EG Android", "Bridge connector", "Worker", "Result"];
const ROW_BOX = { y: 6, w: 180, h: 42 };
const ROW_BOX_X = [20, 240, 460, 680];
const GROUP_COLOR = {
  queued: "#d6a900",
  running: "#2674d9",
  completed: "#2b9b55",
  failed: "#c62828",
  cancelled: "#8a8a8a",
  other: "#8a8a8a",
};
const VIEW_HEIGHT = ROW_BOX.y * 2 + ROW_BOX.h;

function rowArrows(markerId) {
  const y = ROW_BOX.y + ROW_BOX.h / 2;
  return [0, 1, 2]
    .map(
      (i) =>
        `<path class="bridge-arrow" d="M${ROW_BOX_X[i] + ROW_BOX.w + 2} ${y} H${ROW_BOX_X[i + 1] - 4}" marker-end="url(#${markerId})"/>`,
    )
    .join("");
}

function rowStepBox(stage, title, activeStage, group) {
  const x = ROW_BOX_X[stage - 1];
  const isHere = stage === activeStage;
  const color = GROUP_COLOR[group] || GROUP_COLOR.other;
  const dot = isHere
    ? `<circle class="bridge-worker-marker${group === "running" ? " is-processing" : ""}${group === "failed" ? " is-failed" : ""}" cx="${x + ROW_BOX.w - 16}" cy="${ROW_BOX.y + ROW_BOX.h - 12}" r="7" style="--worker-color:${esc(color)}"></circle>`
    : "";
  return `<g class="bridge-step${isHere ? " has-active" : ""}"><rect x="${x}" y="${ROW_BOX.y}" width="${ROW_BOX.w}" height="${ROW_BOX.h}" rx="8"/><text x="${x + 10}" y="${ROW_BOX.y + 17}" class="bridge-number">${stage}</text><text x="${x + 26}" y="${ROW_BOX.y + 17}" class="bridge-step-title">${esc(title)}</text>${dot}</g>`;
}

function rowSvg(markerId, activeStage, group, ariaLabel) {
  return `<svg class="worker-activity-row-svg" viewBox="0 0 880 ${VIEW_HEIGHT}" role="img" aria-label="${esc(ariaLabel)}"><defs><marker id="${esc(markerId)}" class="bridge-arrowhead" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0,0 L7,3.5 L0,7 z"/></marker></defs>${rowArrows(markerId)}${TITLES.map((title, i) => rowStepBox(i + 1, title, activeStage, group)).join("")}</svg>`;
}

/** Most recently touched explicit event for one task, or null when the
 *  worker has reported no event/lifecycle detail for it. */
export function latestEventForTask(task, activityEvents) {
  if (!task) return null;
  const events = [
    ...explicitWorkerLifecycle([task]),
    ...explicitWorkerEvents([task]),
    ...(Array.isArray(activityEvents)
      ? activityEvents.filter((event) => event.taskId === task.id)
      : []),
  ];
  if (!events.length) return null;
  return [...events].sort((a, b) =>
    String(b.time ?? "").localeCompare(String(a.time ?? "")),
  )[0];
}

function renderTaskRow(task, index, activityEvents, isChanged) {
  const group = statusGroup(task.status);
  const stage = coarseStage(task.status);
  const idPrefix =
    index === 0 ? "worker-activity" : `worker-activity-row${index + 1}`;
  const taskId = esc(String(task.id ?? "unknown"));
  const svg = rowSvg(
    `${idPrefix}-arrow`,
    stage,
    group,
    `Task ${taskId} at the ${esc(group)} stage`,
  );
  const event = latestEventForTask(task, activityEvents);
  const eventText = event
    ? `${esc(event.time ?? "—")} — ${esc(event.message || "status update")}`
    : "No event detail reported for this task.";
  const classes = [
    "worker-activity-row",
    `is-${esc(group)}`,
    isChanged ? "is-changed" : "",
  ]
    .filter(Boolean)
    .join(" ");
  return `<div class="${classes}" data-worker-row-index="${index}" data-worker-row-task-id="${taskId}">${svg}<div class="worker-activity-row-meta"><span class="worker-activity-row-rank">#${index + 1}</span><span class="worker-activity-row-task"><strong>Task ${taskId}</strong> · ${esc(task.agent ?? "unknown agent")}</span><span class="worker-activity-row-status is-${esc(group)}"><span class="worker-activity-row-dot" aria-hidden="true"></span>${esc(task.status ?? "unknown")}</span><span class="worker-activity-row-event">${eventText}</span></div></div>`;
}

function renderEmptyRow(index) {
  const idPrefix = `worker-activity-row${index + 1}-empty`;
  const svg = rowSvg(
    `${idPrefix}-arrow`,
    0,
    "other",
    `Priority slot ${index + 1}: no job`,
  );
  return `<div class="worker-activity-row is-empty" data-worker-row-index="${index}">${svg}<div class="worker-activity-row-meta is-empty"><span class="worker-activity-row-rank">#${index + 1}</span><span class="am-dim">No further active or recent job to display.</span></div></div>`;
}

/**
 * Five rows of the same four stations, one per highest-priority real task
 * (rankActiveTasks). Fewer than five real tasks fills the rest with an
 * explicit empty slot; no task ledger at all adds one explicit unavailable
 * banner above the (then all-empty) five rows, rather than guessing.
 * `changedIds` (a Set of task ids, or any iterable) marks rows whose status
 * just transitioned, for a one-shot highlight — never a fabricated blink.
 */
export function renderWorkerActivityRows(payload, { changedIds } = {}) {
  const changed =
    changedIds instanceof Set ? changedIds : new Set(changedIds || []);
  const available = Boolean(payload?.tasks_available);
  const banner = available
    ? ""
    : `<div class="worker-activity-rows-unavailable"><strong>Top active jobs unavailable</strong><p>${esc(payload?.tasks_error || payload?.fetch_error || "No task ledger is configured.")}</p><p class="am-dim">Job rows are not inferred without a real task ledger.</p></div>`;
  const ranked = available ? rankActiveTasks(payload.tasks, ROW_COUNT) : [];
  const rows = [];
  for (let index = 0; index < ROW_COUNT; index += 1) {
    const task = ranked[index];
    rows.push(
      task
        ? renderTaskRow(
            task,
            index,
            payload.activity_events,
            changed.has(String(task.id)),
          )
        : renderEmptyRow(index),
    );
  }
  return `<div class="worker-activity-rows" aria-label="Top five priority jobs">${banner}${rows.join("")}</div>`;
}
