/**
 * LevelPalette — one colour per level, shared by every SVG builder and LED.
 * The LED colours match the-factory's MonitorLed (PASS / RUNNING / FAIL).
 */
export const LEVEL_COLORS = Object.freeze({
  ok: "#2f9e44",
  warn: "#f08c00",
  crit: "#e03131",
  unknown: "#868e96",
});

export const LEVEL_LED = Object.freeze({
  ok: "lightgreen",
  warn: "lightyellow",
  crit: "#fb6666",
  unknown: "#ced4da",
});

export function levelColor(level) {
  return LEVEL_COLORS[level] || LEVEL_COLORS.unknown;
}

export function levelLed(level) {
  return LEVEL_LED[level] || LEVEL_LED.unknown;
}
