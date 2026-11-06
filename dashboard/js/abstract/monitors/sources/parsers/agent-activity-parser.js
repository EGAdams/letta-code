import { worstLevel } from "../../levels/level-rank.js";
import { MonitorSnapshot } from "../monitor-snapshot.js";
import { countBy, withStale } from "./parse-helpers.js";

const LEVEL = { idle: "ok", active: "ok", error: "crit" };

/** /api/agent-activity → idle / active / error donut. */
export function parseAgentActivity(payload) {
  const states = Object.entries(payload)
    .filter(([key, v]) => key.startsWith("agent-") && typeof v === "string")
    .map(([, v]) => v);
  const segments = countBy(states, (s) => s).map((s) => ({
    ...s,
    level: LEVEL[s.label] || "unknown",
  }));
  const active = states.filter((s) => s === "active").length;
  return new MonitorSnapshot({
    level: worstLevel(segments.map((s) => s.level)),
    value: active,
    detail: withStale(payload, `${active} working of ${states.length}`),
    segments,
  });
}
