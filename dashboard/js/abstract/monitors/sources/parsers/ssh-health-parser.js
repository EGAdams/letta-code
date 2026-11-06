import { worstLevel } from "../../levels/level-rank.js";
import { statusLevel } from "../../levels/status-level.js";
import { MonitorSnapshot } from "../monitor-snapshot.js";
import { asList, countBy, withStale } from "./parse-helpers.js";

/** /api/ssh-connection-health → up/down donut; muted links never alert. */
export function parseSshHealth(payload) {
  const links = asList(payload.connections);
  const items = links.map((c) => ({
    label: c.name || c.key,
    text: c.muted ? `${c.status} (muted)` : c.status,
    level: c.muted ? "ok" : statusLevel(c.status),
  }));
  const segments = countBy(links, (c) => c.status).map((s) => ({
    ...s,
    level: statusLevel(s.label),
  }));
  return new MonitorSnapshot({
    level: worstLevel(items.map((i) => i.level)),
    value: links.filter((c) => c.status === "up").length,
    detail: withStale(payload, `${links.length} connections`),
    items,
    segments,
  });
}
