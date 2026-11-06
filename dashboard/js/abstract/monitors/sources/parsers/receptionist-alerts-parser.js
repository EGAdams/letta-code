import { MonitorSnapshot } from "../monitor-snapshot.js";
import { asList, withStale } from "./parse-helpers.js";

const words = (a) =>
  a?.message || a?.text || a?.summary || a?.title || JSON.stringify(a);

/** /api/receptionist-alerts → open alert count; errors mean a sidecar is unreachable. */
export function parseReceptionistAlerts(payload) {
  const alerts = asList(payload.alerts);
  const errors = asList(payload.errors);
  return new MonitorSnapshot({
    level: alerts.length
      ? "crit"
      : errors.length
        ? "warn"
        : payload.ok === false
          ? "unknown"
          : "ok",
    value: alerts.length,
    detail: withStale(
      payload,
      alerts.length ? `${alerts.length} unacknowledged` : "No open alerts",
    ),
    items: [
      ...alerts.map((a) => ({
        label: a?.agent || a?.source || "alert",
        text: words(a),
        level: "crit",
      })),
      ...errors.map((e) => ({
        label: "unreachable",
        text: words(e),
        level: "warn",
      })),
    ],
  });
}
