// Deterministic ranking of the worker ledger down to its highest-priority
// rows, for the Worker Activity page's top-five-jobs view. Pure: no DOM, no
// network, no randomness. Never invents a row — it only orders and trims the
// real ledger it is given.
import { statusGroup } from "./bridge-workflow-render.js";

/** Queued with zero attempts is the same "may be stagnant" signal already
 *  surfaced as a warning on the ledger table (worker-activity-render.js). */
export function isStalledTask(task) {
  return statusGroup(task?.status) === "queued" && Number(task?.attempts) === 0;
}

function timeKey(task) {
  return String(
    task?.last_update ?? task?.updated_at ?? task?.created_at ?? "",
  );
}

function idKey(task) {
  return String(task?.id ?? "");
}

// 0: failed (error). 1: stalled queued work. 2: running. 3: queued (not
// stalled). 4: everything else (completed/cancelled/other — "recent results").
function tierOf(task) {
  const group = statusGroup(task?.status);
  if (group === "failed") return 0;
  if (isStalledTask(task)) return 1;
  if (group === "running") return 2;
  if (group === "queued") return 3;
  return 4;
}

// Tiers 0/1/2/4 surface the most recently touched row first; tier 3 (queued,
// not stalled) surfaces the oldest first, since "age" is the priority signal
// for work that is simply waiting. Ties break on task id for a stable order.
function compareWithinTier(tier) {
  return (a, b) => {
    const ta = timeKey(a);
    const tb = timeKey(b);
    if (ta !== tb)
      return tier === 3 ? ta.localeCompare(tb) : tb.localeCompare(ta);
    return idKey(a).localeCompare(idKey(b));
  };
}

/** Up to `limit` real tasks, highest priority first. Duplicate ids in the
 *  supplied ledger collapse to their first occurrence rather than repeating a
 *  job across two rows. */
export function rankActiveTasks(tasks, limit = 5) {
  const seen = new Set();
  const unique = [];
  for (const task of Array.isArray(tasks) ? tasks : []) {
    if (!task || task.id == null) continue;
    const key = String(task.id);
    if (seen.has(key)) continue;
    seen.add(key);
    unique.push(task);
  }
  const byTier = new Map();
  for (const task of unique) {
    const tier = tierOf(task);
    if (!byTier.has(tier)) byTier.set(tier, []);
    byTier.get(tier).push(task);
  }
  const ordered = [];
  for (const tier of [0, 1, 2, 3, 4]) {
    const group = byTier.get(tier);
    if (!group) continue;
    ordered.push(...[...group].sort(compareWithinTier(tier)));
  }
  return ordered.slice(0, limit);
}
