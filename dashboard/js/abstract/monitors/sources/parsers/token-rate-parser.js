import { MonitorSnapshot } from "../monitor-snapshot.js";
import { asList, withStale } from "./parse-helpers.js";

/** /api/claude-sdk-token-rate → tokens/minute over the last minute; trend kept by the view. */
export function parseTokenRate(payload) {
  const windows = asList(payload.windows);
  const run = payload.current_run || {};
  return new MonitorSnapshot({
    level:
      payload.ok === false ? "warn" : run.status === "error" ? "crit" : "ok",
    value: Number(windows[0]?.tokens_per_minute ?? 0),
    unit: "tok/min",
    detail: withStale(
      payload,
      payload.error ||
        `last run ${run.status || "—"} · ${run.model || ""} · ${run.total_tokens ?? 0} tokens`,
    ),
    series: windows.map((w) => Number(w.tokens_per_minute)),
    items: windows.map((w) => ({
      label: w.label,
      text: `${Math.round(w.tokens_per_minute)} tok/min · ${w.runs} runs`,
      level: "ok",
    })),
  });
}
