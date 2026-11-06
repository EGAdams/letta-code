import { MonitorSnapshot } from "../monitor-snapshot.js";
import { withStale } from "./parse-helpers.js";

/** /api/intake-halt → red while document intake is halted. */
export function parseIntakeHalt(payload) {
  const halted = !!payload.active;
  return new MonitorSnapshot({
    level: payload.ok === false ? "unknown" : halted ? "crit" : "ok",
    detail: withStale(
      payload,
      halted
        ? payload.reason || payload.message || "Intake halted"
        : "Intake running",
    ),
    items: [
      {
        label: "halt",
        text: halted ? "active" : "clear",
        level: halted ? "crit" : "ok",
      },
    ],
  });
}
