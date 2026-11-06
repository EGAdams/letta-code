/** Small shared bits for the endpoint parsers. */

/** Appends "(stale: why)" when a LastGood runner served an old payload. */
export function withStale(payload, detail) {
  if (!payload?.stale) return detail;
  const why = payload.stale_error ? `: ${payload.stale_error}` : "";
  return `${detail} (stale${why})`.trim();
}

export function percentOf(part, whole) {
  return whole > 0 ? (part / whole) * 100 : null;
}

/** Counts items by key(item) → [{label, value}], in first-seen order. */
export function countBy(items, key) {
  const counts = new Map();
  for (const item of items) {
    const k = key(item);
    counts.set(k, (counts.get(k) || 0) + 1);
  }
  return [...counts].map(([label, value]) => ({ label, value }));
}

export const asList = (value) => (Array.isArray(value) ? value : []);

/** Seconds until an ISO time (or epoch seconds), never negative. */
export function secondsUntil(when, now = Date.now()) {
  const ms = typeof when === "number" ? when * 1000 : Date.parse(when);
  return Number.isFinite(ms) ? Math.max(0, (ms - now) / 1000) : null;
}
