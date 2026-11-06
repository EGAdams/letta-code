import { MonitorSnapshot } from "../monitor-snapshot.js";
import { asList, withStale } from "./parse-helpers.js";

/** /api/code-status → amber when the dashboard's code changed since it started. */
export function parseCodeStatus(payload) {
  const files = asList(payload.changed_files);
  return new MonitorSnapshot({
    level: payload.changed ? "warn" : "ok",
    value: files.length,
    detail: withStale(
      payload,
      payload.changed
        ? "Code changed — restart pending"
        : "Running current code",
    ),
    items: files
      .slice(0, 5)
      .map((f) => ({ label: String(f), text: "changed", level: "warn" })),
  });
}
