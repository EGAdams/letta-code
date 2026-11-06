import { MonitorSnapshot } from "../monitor-snapshot.js";
import { percentOf, withStale } from "./parse-helpers.js";

/** /api/agent-health → share of agents whose tools check out; lists the rest. */
export function parseAgentHealth(payload) {
  const agents = Object.entries(payload)
    .filter(
      ([key, v]) => key.startsWith("agent-") && v && typeof v === "object",
    )
    .map(([, v]) => v);
  const sick = agents.filter((a) => !a.ok);
  return new MonitorSnapshot({
    level: agents.length === 0 ? "unknown" : sick.length ? "warn" : "ok",
    value: percentOf(agents.length - sick.length, agents.length),
    unit: "%",
    detail: withStale(
      payload,
      `${agents.length - sick.length} of ${agents.length} healthy`,
    ),
    items: sick.map((a) => ({
      label: a.name || "agent",
      text: a.text || "",
      level: "warn",
    })),
  });
}
