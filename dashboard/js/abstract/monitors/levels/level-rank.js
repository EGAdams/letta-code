/**
 * Monitor levels, worst last. Every monitor reduces to one of these.
 */
export const LEVELS = Object.freeze(["ok", "unknown", "warn", "crit"]);

const rank = (level) => {
  const i = LEVELS.indexOf(level);
  return i < 0 ? LEVELS.indexOf("unknown") : i;
};

/** The worst of several levels; "unknown" when there are none. */
export function worstLevel(levels) {
  let worst = "ok";
  let seen = false;
  for (const level of levels) {
    seen = true;
    if (rank(level) > rank(worst)) worst = LEVELS[rank(level)];
  }
  return seen ? worst : "unknown";
}
