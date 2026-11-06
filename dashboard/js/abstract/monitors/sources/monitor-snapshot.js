import { LEVELS } from "../levels/level-rank.js";

/**
 * MonitorSnapshot — what every parser returns and every view draws.
 * value: the one number a gauge/ring shows (or null); items: per-row detail;
 * series: numbers for a sparkline; segments: {label, value, level} for a donut.
 */
export class MonitorSnapshot {
  constructor({
    level = "unknown",
    value = null,
    unit = "",
    detail = "",
    items = [],
    series = [],
    segments = [],
    fraction = null,
    at = Date.now(),
  } = {}) {
    this.level = LEVELS.includes(level) ? level : "unknown";
    this.value = Number.isFinite(value) ? value : null;
    this.unit = String(unit);
    this.detail = String(detail);
    this.items = items;
    this.series = series.filter(Number.isFinite);
    this.segments = segments;
    this.fraction = Number.isFinite(fraction)
      ? Math.min(1, Math.max(0, fraction))
      : null;
    this.at = at;
    Object.freeze(this);
  }

  static failed(error) {
    return new MonitorSnapshot({
      level: "unknown",
      detail: `No data: ${error?.message || error}`,
    });
  }
}
