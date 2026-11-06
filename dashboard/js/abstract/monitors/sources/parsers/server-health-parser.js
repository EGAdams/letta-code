import { worstLevel } from "../../levels/level-rank.js";
import { statusLevel } from "../../levels/status-level.js";
import { MonitorSnapshot } from "../monitor-snapshot.js";
import { asList, percentOf, withStale } from "./parse-helpers.js";

/** /api/server-health → share of servers up. */
export function parseServerHealth(payload) {
  const servers = asList(payload.servers);
  const up = servers.filter((s) => s.status === "up").length;
  const items = servers.map((s) => ({
    label: s.name || s.key,
    text: s.status,
    level: statusLevel(s.status),
  }));
  return new MonitorSnapshot({
    level: worstLevel(items.map((i) => i.level)),
    value: percentOf(up, servers.length),
    unit: "%",
    detail: withStale(payload, `${up} of ${servers.length} up`),
    items,
  });
}
