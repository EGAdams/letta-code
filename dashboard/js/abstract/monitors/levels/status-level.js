/**
 * Maps the many status words the endpoints use onto a monitor level.
 */
const WORDS = Object.freeze({
  ok: [
    "ok",
    "up",
    "idle",
    "active",
    "normal",
    "valid",
    "succeeded",
    "healthy",
    "connected",
    "running",
  ],
  warn: [
    "warn",
    "starting",
    "queued",
    "pending",
    "stale",
    "expiring",
    "degraded",
    "busy",
  ],
  crit: [
    "crit",
    "down",
    "error",
    "failed",
    "invalid",
    "expired",
    "offline",
    "dead",
  ],
});

export function statusLevel(status) {
  const word = String(status ?? "")
    .trim()
    .toLowerCase();
  for (const [level, words] of Object.entries(WORDS)) {
    if (words.includes(word)) return level;
  }
  return "unknown";
}
