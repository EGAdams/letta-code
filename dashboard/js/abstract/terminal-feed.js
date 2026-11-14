// Pure normalizer for the System Status > Terminal page: every event the
// dashboard already has an authoritative source for, from one call to
// /api/worker-activity (worker task events/lifecycle, the independent
// adw_supervisor's escalations, the Star Trek Bridge gateway's supervised
// requests and their child ADW tasks, the bridge worker's own supervisor
// heartbeat, and installed worker lanes). No DOM, no network, no invented
// events: a source this page cannot see is reported as a `[gap:*]` line
// instead of being left out silently.
import {
  explicitWorkerEvents,
  explicitWorkerLifecycle,
} from "./worker-activity-events.js";

const TERMINAL_TIME_FORMAT = new Intl.DateTimeFormat("en-US", {
  hour: "numeric",
  minute: "2-digit",
  second: "2-digit",
  fractionalSecondDigits: 3,
  hour12: true,
});

/** Format an ISO timestamp for display without changing the source value. */
export function formatTerminalTimestamp(timestamp) {
  if (typeof timestamp !== "string" || !timestamp.includes("T"))
    return timestamp;
  const date = new Date(timestamp);
  return Number.isNaN(date.getTime())
    ? timestamp
    : TERMINAL_TIME_FORMAT.format(date);
}

function line(ts, tags, text) {
  const id = tags.filter(Boolean).join(" ");
  return `${formatTerminalTimestamp(ts) ?? "—"} [${id || "unknown"}] ${text}`;
}

function gap(scope, reason) {
  return line("—", [`gap:${scope}`], reason || "unavailable");
}

const MAX_VISIBLE_TASKS = 4;

function taskTime(value) {
  const time = Date.parse(value ?? "");
  return Number.isNaN(time) ? null : time;
}

function taskLines(payload) {
  const lines = [];
  if (!payload?.tasks_available) {
    lines.push(
      gap(
        "tasks",
        payload?.tasks_error ||
          payload?.fetch_error ||
          "worker task ledger unavailable",
      ),
    );
  } else {
    const tasks = payload.tasks || [];
    const explicit = [
      ...explicitWorkerLifecycle(tasks),
      ...explicitWorkerEvents(tasks),
    ];
    const taskRecords = [];
    for (const event of explicit) {
      const taskId = event.taskId ?? "—";
      taskRecords.push({
        taskId: String(taskId),
        time: event.time,
        text: line(
          event.time,
          [`task:${taskId}`, `agent:${event.agent ?? "—"}`, event.phase],
          event.message || event.detail || event.operation || "status update",
        ),
      });
    }
    const covered = new Set(
      explicit
        .filter((event) => event.taskId != null)
        .map((event) => String(event.taskId)),
    );
    for (const task of tasks) {
      if (!task || covered.has(String(task.id))) continue;
      const time = task.last_update ?? task.updated_at ?? task.created_at;
      taskRecords.push({
        taskId: String(task.id ?? "—"),
        time,
        text: line(
          time,
          [`task:${task.id ?? "—"}`, `agent:${task.agent ?? "—"}`],
          `${task.operation ?? "worker event"}: ${task.status ?? "unknown"}${task.error ? ` — ${task.error}` : ""}`,
        ),
      });
    }

    // Select by the most recently updated distinct task, then show every
    // event for those tasks in chronological order. Other source categories
    // below are intentionally not part of this display-only limit.
    const groups = new Map();
    taskRecords.forEach((record, index) => {
      const group = groups.get(record.taskId) ?? {
        records: [],
        latest: null,
        index,
      };
      group.records.push({ ...record, index });
      const timestamp = taskTime(record.time);
      if (
        timestamp !== null &&
        (group.latest === null || timestamp >= group.latest)
      )
        group.latest = timestamp;
      groups.set(record.taskId, group);
    });
    [...groups.values()]
      .sort(
        (a, b) =>
          (a.latest ?? -Infinity) - (b.latest ?? -Infinity) ||
          a.index - b.index,
      )
      .slice(-MAX_VISIBLE_TASKS)
      .sort(
        (a, b) =>
          (a.latest ?? -Infinity) - (b.latest ?? -Infinity) ||
          a.index - b.index,
      )
      .forEach((group) => {
        lines.push(
          ...group.records
            .sort(
              (a, b) =>
                taskTime(a.time) - taskTime(b.time) || a.index - b.index,
            )
            .map((record) => record.text),
        );
      });
  }
  if (payload?.ledger_error)
    lines.push(gap("ledger_error", payload.ledger_error));
  if (payload?.ledger_stale)
    lines.push(gap("ledger_stale", payload.ledger_stale));
  return lines;
}

function escalationLines(payload) {
  const state = payload?.escalation;
  if (!state?.available) {
    return [gap("escalation", state?.reason || "adw-supervisor unavailable")];
  }
  const lines = [];
  if (state.stale) {
    lines.push(
      gap(
        "escalation",
        "adw-supervisor heartbeat is stale; showing its last recorded observations",
      ),
    );
  }
  if (state.coverage_complete === false) {
    lines.push(
      gap("coverage", state.coverage_reason || "incomplete task coverage"),
    );
  }
  for (const alert of Array.isArray(state.alerts) ? state.alerts : []) {
    if (!alert || typeof alert !== "object") continue;
    const tags = [
      "adw-supervisor",
      `task:${alert.task_id ?? "—"}`,
      `tier:${alert.tier ?? "—"}`,
    ];
    const events = Array.isArray(alert.recent_events)
      ? alert.recent_events
      : [];
    if (!events.length) {
      lines.push(
        line("—", tags, alert.observation_error || "escalation observed"),
      );
      continue;
    }
    for (const event of events) {
      if (!event || typeof event !== "object") continue;
      lines.push(
        line(
          event.time ?? event.timestamp,
          tags,
          event.message || "escalation event",
        ),
      );
    }
  }
  return lines;
}

function requestLines(payload) {
  const state = payload?.requests;
  if (!state?.available) {
    return [
      gap(
        "requests",
        state?.reason || "gateway request supervision unavailable",
      ),
    ];
  }
  const lines = [];
  for (const request of Array.isArray(state.open) ? state.open : []) {
    if (!request || typeof request !== "object") continue;
    const requestId = request.request_id ?? "—";
    const blocked = request.blocked_on
      ? ` BLOCKED on ${request.blocked_on}${request.blocked_owner ? ` (owner ${request.blocked_owner})` : ""}`
      : "";
    lines.push(
      line(
        "—",
        [`request:${requestId}`, "parent"],
        `${request.title ?? "request"} — phase ${request.phase ?? "unknown"} (${request.timer ?? "ok"})${blocked}`,
      ),
    );
    for (const child of Array.isArray(request.child_tasks)
      ? request.child_tasks
      : []) {
      if (!child || typeof child !== "object") continue;
      lines.push(
        line(
          "—",
          [`request:${requestId}`, `child:${child.task_id ?? "—"}`],
          `${child.operation ?? "task"} — ${child.state ?? "unknown"}${child.status_check ? " (status check)" : ""}`,
        ),
      );
    }
  }
  for (const request of Array.isArray(state.recently_closed)
    ? state.recently_closed
    : []) {
    if (!request || typeof request !== "object") continue;
    lines.push(
      line(
        "—",
        [`request:${request.request_id ?? "—"}`, "parent closed"],
        `${request.title ?? "request"} — ${request.state ?? "unknown"}${request.outcome ? `: ${request.outcome}` : ""}`,
      ),
    );
  }
  if (typeof state.watch?.checked_seconds_ago !== "number") {
    lines.push(gap("gateway-watch", "gateway watch health unknown"));
  }
  return lines;
}

function supervisorLines(payload) {
  const supervisor = payload?.supervisor;
  if (!supervisor) {
    return [
      gap("bridge-worker-supervisor", "no supervisor heartbeat file reported"),
    ];
  }
  const tags = ["bridge-worker-supervisor", `pid:${supervisor.pid ?? "—"}`];
  // checked_at changes every minute, so a healthy, do-nothing summary would
  // never repeat exactly and would reprint forever. Only a problem is news.
  const quiet =
    supervisor.status === "healthy" && (supervisor.action ?? "none") === "none";
  const lines = quiet
    ? []
    : [
        line(
          supervisor.checked_at,
          tags,
          `${supervisor.status ?? "unknown"} action=${supervisor.action ?? "none"} restarts ${supervisor.restarts_in_window ?? "—"}/${supervisor.max_restarts ?? "—"}${supervisor.reason ? ` — ${supervisor.reason}` : ""}`,
        ),
      ];
  for (const event of Array.isArray(supervisor.events)
    ? supervisor.events
    : []) {
    if (typeof event === "string") {
      lines.push(line(supervisor.checked_at, tags, event));
    } else if (event && typeof event === "object") {
      lines.push(
        line(
          event.at ?? event.time ?? event.timestamp ?? supervisor.checked_at,
          tags,
          event.message ?? event.action ?? "supervisor event",
        ),
      );
    }
  }
  return lines;
}

function laneLines(payload) {
  const lanes = Array.isArray(payload?.workers) ? payload.workers : [];
  if (!lanes.length) {
    return [gap("worker-lanes", "no worker lane telemetry reported")];
  }
  return lanes
    .filter((lane) => lane && typeof lane === "object")
    .map((lane) => {
      const state = !lane.installed
        ? "not installed"
        : lane.healthy
          ? "running"
          : `DOWN — ${lane.status ?? "unknown"}`;
      const verdict = lane.supervisor
        ? ` supervisor:${lane.supervisor.status ?? "unknown"}${lane.supervisor.action && lane.supervisor.action !== "none" ? `(${lane.supervisor.action})` : ""}`
        : "";
      return line(
        "—",
        [`lane:${lane.lane ?? "—"}`],
        `${state}${verdict}${lane.reason ? ` — ${lane.reason}` : ""}`,
      );
    });
}

function workerHealthLines(payload) {
  const worker = payload?.worker;
  if (!worker) {
    return [gap("bridge-worker", "no bridge worker telemetry reported")];
  }
  const diagnostic = payload?.diagnostic || {};
  // A healthy worker gets a fresh observed_at every poll, so its line never
  // repeats exactly and would print every 5s. Only a problem is news here.
  if (diagnostic.status === "healthy") return [];
  return [
    line(
      worker.observed_at,
      ["bridge-worker"],
      `${diagnostic.status ?? worker.status ?? "unknown"} — ${diagnostic.action ?? worker.reason ?? "no reason reported"}`,
    ),
  ];
}

/**
 * Flattens one /api/worker-activity payload into plain-text terminal lines.
 * Every line already carries its own timestamp and identifiers; nothing here
 * is inferred or re-ordered across polls — callers append whatever is new.
 */
export function buildTerminalEvents(payload) {
  if (!payload || typeof payload !== "object") {
    return [gap("worker-activity", "no worker-activity payload received")];
  }
  return [
    ...taskLines(payload),
    ...escalationLines(payload),
    ...requestLines(payload),
    ...supervisorLines(payload),
    ...laneLines(payload),
    ...workerHealthLines(payload),
  ];
}
