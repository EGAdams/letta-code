// Normalize the optional event shapes owned by the worker. This module never
// invents agent actions; callers may add explicitly labelled UI observations.
import { TextUtils } from "./text-utils.js";

const esc = TextUtils.esc;
const EVENT_KEYS = ["events", "event_log", "progress_events"];
const PHASE_FIELDS = [
  ["queued_at", "queued"],
  ["started_at", "started"],
  ["completed_at", "completed"],
  ["finished_at", "completed"],
  ["failed_at", "failed"],
];

function timeOf(event, task) {
  return (
    event?.timestamp ??
    event?.time ??
    event?.at ??
    event?.last_update ??
    task?.last_update ??
    task?.updated_at ??
    task?.created_at ??
    "—"
  );
}

function messageOf(event, task) {
  return (
    event?.message ??
    event?.detail ??
    event?.description ??
    event?.action ??
    event?.text ??
    task?.message ??
    task?.progress ??
    "status update"
  );
}

/** Return safe, display-ready events supplied by the worker snapshot. */
export function explicitWorkerEvents(tasks) {
  const result = [];
  for (const task of Array.isArray(tasks) ? tasks : []) {
    for (const key of EVENT_KEYS) {
      const events = Array.isArray(task?.[key]) ? task[key] : [];
      for (const event of events) {
        if (typeof event === "string") {
          result.push({
            time: task.last_update ?? "—",
            taskId: task.id,
            agent: task.agent,
            message: event,
            source: "worker",
          });
        } else if (event && typeof event === "object") {
          result.push({
            time: timeOf(event, task),
            taskId: event.task_id ?? task.id,
            agent: event.agent ?? task.agent,
            phase: event.phase ?? event.status,
            message: messageOf(event, task),
            source: "worker",
          });
        }
      }
    }
  }
  return result;
}

/** Lifecycle markers are emitted only when the worker supplied their times. */
export function explicitWorkerLifecycle(tasks) {
  const result = [];
  for (const task of Array.isArray(tasks) ? tasks : []) {
    for (const [field, phase] of PHASE_FIELDS) {
      if (task?.[field])
        result.push({
          time: task[field],
          taskId: task.id,
          agent: task.agent,
          phase,
          operation: task.operation,
          detail: task[`${phase}_detail`] ?? task.message,
          source: "worker",
        });
    }
  }
  return result;
}

export function renderWorkerEvents(events) {
  return events
    .map((event) => {
      const identity = [event.taskId, event.agent].filter(Boolean).join(" / ");
      const source =
        event.source === "worker" ? "worker event" : "dashboard observation";
      const phase = event.phase ? ` ${esc(event.phase)}` : "";
      return `${esc(event.time ?? "—")} [${esc(identity || "worker")}]${phase} ${esc(event.message || "status update")} (${source})`;
    })
    .join("\n");
}
