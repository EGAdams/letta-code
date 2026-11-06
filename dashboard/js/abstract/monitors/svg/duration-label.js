/** 75 → "1m 15s", 7300 → "2h 1m", null → "—". */
export function durationLabel(seconds) {
  if (!Number.isFinite(seconds)) return "—";
  const s = Math.round(seconds);
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s`;
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
}
