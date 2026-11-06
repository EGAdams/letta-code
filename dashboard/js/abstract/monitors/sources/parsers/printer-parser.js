import { worstLevel } from "../../levels/level-rank.js";
import { statusLevel } from "../../levels/status-level.js";
import { MonitorSnapshot } from "../monitor-snapshot.js";
import { asList, withStale } from "./parse-helpers.js";

const jobLevel = (state) =>
  /fail|error|cancel/i.test(state)
    ? "crit"
    : /complete/i.test(state)
      ? "ok"
      : "warn";

/** /api/printer → printer status LEDs plus the last few jobs. */
export function parsePrinter(payload) {
  if (payload.enabled === false)
    return new MonitorSnapshot({ detail: "Printer agent disabled" });
  const printers = asList(payload.printers).map((p) => ({
    label: p.is_default ? `${p.name} ★` : p.name,
    text: p.status,
    level: statusLevel(p.status),
  }));
  const jobs = asList(payload.recent)
    .slice(0, 3)
    .map((j) => ({
      label: j.title || j.job_id,
      text: j.state,
      level: jobLevel(j.state || ""),
    }));
  return new MonitorSnapshot({
    level:
      payload.ok === false ? "crit" : worstLevel(printers.map((p) => p.level)),
    value: printers.length,
    detail: withStale(
      payload,
      payload.error ||
        `${printers.length} printers · ${payload.documents ?? 0} documents`,
    ),
    items: [...printers, ...jobs],
  });
}
