import { worstLevel } from "../../levels/level-rank.js";
import { MonitorSnapshot } from "../monitor-snapshot.js";
import { asList, withStale } from "./parse-helpers.js";

/** /api/wsl-interop → one LED per machine's WSLInterop registration. */
export function parseWslInterop(payload) {
  const machines = asList(payload.machines);
  const items = machines.map((m) => ({
    label: m.label || m.key,
    text: m.detail || m.state || "",
    level: m.level || "unknown",
  }));
  return new MonitorSnapshot({
    level: payload.level || worstLevel(items.map((i) => i.level)),
    value: machines.length,
    detail: withStale(payload, `${machines.length} machines`),
    items,
  });
}
