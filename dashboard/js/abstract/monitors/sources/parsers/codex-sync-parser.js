import { MonitorSnapshot } from "../monitor-snapshot.js";
import { asList, withStale } from "./parse-helpers.js";

/** /api/codex-sync-status → countdown to the next Codex OAuth sync. */
export function parseCodexSync(payload) {
  const interval = Number(payload.interval_seconds);
  const left = Number(payload.seconds_remaining);
  return new MonitorSnapshot({
    level: payload.needs_reauth
      ? "crit"
      : payload.sync_enabled === false
        ? "warn"
        : "ok",
    value: Number.isFinite(left) ? left : null,
    unit: "s",
    fraction: interval > 0 && Number.isFinite(left) ? left / interval : null,
    detail: withStale(
      payload,
      payload.needs_reauth
        ? "Re-auth needed"
        : payload.sync_enabled === false
          ? "Sync disabled"
          : "Sync on schedule",
    ),
    items: asList(payload.slots).map((s) => ({
      label: s.label || s.key,
      text: s.email || "",
      level: "ok",
    })),
  });
}
