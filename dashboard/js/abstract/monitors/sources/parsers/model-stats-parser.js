import { MonitorSnapshot } from "../monitor-snapshot.js";
import { asList, withStale } from "./parse-helpers.js";

/** /api/model-stats?source=… → quota left in the tightest usage window. */
export function parseModelStats(payload) {
  if (payload.ok === false) {
    return new MonitorSnapshot({
      level: "unknown",
      detail: withStale(payload, payload.error || "no stats"),
    });
  }
  // null means "unavailable", and Number(null) would read as 0% used.
  const windows = asList(payload.windows).filter(
    (w) => w.used_percent !== null && Number.isFinite(Number(w.used_percent)),
  );
  const used = windows.map((w) => Number(w.used_percent));
  const left = used.length ? 100 - Math.max(...used) : null;
  const model = payload.model ? `${payload.model} · ` : "";
  return new MonitorSnapshot({
    level:
      left === null
        ? "unknown"
        : left < 10
          ? "crit"
          : left < 30
            ? "warn"
            : "ok",
    value: left,
    unit: "%",
    detail: withStale(
      payload,
      model + (payload.detail || payload.label || payload.key || ""),
    ),
    items: windows.map((w) => ({
      label: w.label,
      text: `${Math.round(w.used_percent)}% used${w.resets_in ? `, resets ${w.resets_in}` : ""}`,
      level:
        w.used_percent >= 90 ? "crit" : w.used_percent >= 70 ? "warn" : "ok",
    })),
  });
}
