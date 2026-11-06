import { worstLevel } from "../../levels/level-rank.js";
import { MonitorSnapshot } from "../monitor-snapshot.js";
import { asList, withStale } from "./parse-helpers.js";

/** /api/pc-metrics?pc=… → the busiest of RAM / disk / network. */
export function parsePcMetrics(payload) {
  const metrics = asList(payload.metrics);
  const percents = metrics
    .map((m) => Number(m.percent))
    .filter(Number.isFinite);
  return new MonitorSnapshot({
    level:
      payload.ok === false
        ? "crit"
        : payload.level || worstLevel(metrics.map((m) => m.level)),
    value: percents.length ? Math.max(...percents) : null,
    unit: "%",
    detail: withStale(
      payload,
      payload.ok === false
        ? payload.error || "unreachable"
        : payload.note || "",
    ),
    items: metrics.map((m) => ({
      key: m.key,
      label: m.label,
      text: m.text,
      percent: Number(m.percent),
      level: m.level || "unknown",
    })),
  });
}
