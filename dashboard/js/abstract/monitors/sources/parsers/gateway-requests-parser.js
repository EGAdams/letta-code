import { MonitorSnapshot } from "../monitor-snapshot.js";

const TIMER_LEVEL = {
  escalated: "crit",
  warning: "warn",
  no_progress: "warn",
  not_assigned: "warn",
};

/**
 * /api/worker-activity's `requests` → the gateway's supervised user requests.
 * Unavailable is "unknown", never "ok": an unreadable gateway hides stalls.
 * A blocked request whose owner has been told is still at least "warn".
 */
export function parseGatewayRequests(payload) {
  const state = payload?.requests;
  if (!state?.available) {
    return new MonitorSnapshot({
      level: "unknown",
      detail: state?.reason || "Request supervision unavailable",
      items: [],
    });
  }
  const open = (Array.isArray(state.open) ? state.open : []).filter(
    (r) => r && typeof r === "object",
  );
  const ago = state.watch?.checked_seconds_ago;
  const watchLate = typeof ago !== "number" || ago > 600;
  const items = open.slice(0, 6).map((r) => {
    const level =
      TIMER_LEVEL[r.timer] || (r.phase === "blocked" ? "warn" : "ok");
    const why = r.blocked_on
      ? `blocked: ${r.blocked_on}`
      : `${r.phase || "?"}, ${r.since_progress || "?"} since progress`;
    return {
      label: String(r.title || r.request_id || "request").slice(0, 40),
      text: why.slice(0, 120),
      level,
    };
  });
  items.push({
    label: "gateway watch",
    text: typeof ago === "number" ? `checked ${ago} s ago` : "unknown",
    level: watchLate ? "warn" : "ok",
  });
  const levels = items.map((i) => i.level);
  const level = levels.includes("crit")
    ? "crit"
    : levels.includes("warn")
      ? "warn"
      : "ok";
  return new MonitorSnapshot({
    level,
    detail: open.length ? `${open.length} open request(s)` : "No open requests",
    items,
  });
}
