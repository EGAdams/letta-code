import { statusLevel } from "../../levels/status-level.js";
import { MonitorSnapshot } from "../monitor-snapshot.js";
import { withStale } from "./parse-helpers.js";

/** /api/scanner-intake-status → one LED for the scanner intake loop. */
export function parseScannerIntake(payload) {
  const level = payload.ok === false ? "crit" : statusLevel(payload.status);
  return new MonitorSnapshot({
    level,
    detail: withStale(payload, payload.error || payload.status || "unknown"),
    items: [{ label: "intake", text: payload.status || "", level }],
  });
}
