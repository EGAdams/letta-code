import { MonitorSnapshot } from "./monitor-snapshot.js";

/**
 * The snapshot narrowed to one item, for a card whose preset button picks
 * what its gauge shows. "max" (or no preset) keeps the whole snapshot. An
 * item that isn't in this reading shows as no value, never as 0.
 */
export function presetSnapshot(snapshot, preset) {
  if (!preset || preset === "max") return snapshot;
  const item = snapshot.items.find((i) => i.key === preset);
  return new MonitorSnapshot({
    ...snapshot,
    value: item ? item.percent : null,
    level: item ? item.level : "unknown",
  });
}
