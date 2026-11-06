import { MonitorSnapshot } from "../monitor-snapshot.js";
import { secondsUntil, withStale } from "./parse-helpers.js";

/** /api/agent-bridge-poll → countdown to the worker's next check. */
export function parseBridgePoll(payload, now = Date.now()) {
  const state = payload.state || {};
  const running = payload.service?.active === "active";
  const left = secondsUntil(state.next_check_at, now);
  const delay = Number(state.delay_seconds);
  return new MonitorSnapshot({
    level: !running ? "crit" : state.outcome === "error" ? "warn" : "ok",
    value: left,
    unit: "s",
    fraction: left !== null && delay > 0 ? left / delay : null,
    detail: withStale(
      payload,
      running
        ? `${state.phase || "?"} · ${state.outcome || "?"} · ${state.checks ?? 0} checks`
        : `worker ${payload.service?.active || "stopped"}`,
    ),
    items: [
      {
        label: "polling",
        text: payload.reason || payload.polling || "",
        level: running ? "ok" : "crit",
      },
    ],
  });
}
