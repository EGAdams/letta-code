import { worstLevel } from "../../levels/level-rank.js";
import { statusLevel } from "../../levels/status-level.js";
import { MonitorSnapshot } from "../monitor-snapshot.js";
import { asList, countBy, withStale } from "./parse-helpers.js";

/** /api/worker-activity → task outcome donut; failures listed. */
export function parseWorkerActivity(payload) {
  const tasks = asList(payload.tasks);
  const segments = countBy(tasks, (t) => t.status).map((s) => ({
    ...s,
    level: statusLevel(s.label),
  }));
  const failed = tasks.filter((t) => statusLevel(t.status) === "crit");
  return new MonitorSnapshot({
    level: payload.fetch_error
      ? "warn"
      : tasks.length
        ? worstLevel(segments.map((s) => s.level))
        : "ok",
    value: tasks.length,
    detail: withStale(
      payload,
      payload.fetch_error || `${tasks.length} recent tasks`,
    ),
    segments,
    items: failed.slice(0, 4).map((t) => ({
      label: `${t.agent} ${t.operation}`,
      text: t.error || t.status,
      level: "crit",
    })),
  });
}
