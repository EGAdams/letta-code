/**
 * Model Stats warning-silencer — shape guard for the `muted`/`raw_status`
 * fields POST /api/model-stats-mute (and GET /api/model-stats) attach to a
 * model_stats payload. Pure validation, no DOM/fetch — mirrors the
 * assert*Status guards in codex-sync-status.js and
 * chatgpt-provider-account-status.js: the server's Pydantic StrictModel
 * (model_stats_mute.apply_mute_overlay) guards this shape on the way out,
 * this is the mirror guard on the way in.
 */

/**
 * @param {any} d
 * @returns {{muted:boolean, raw_status:string|null}}
 */
export function assertModelStatsMuteFields(d) {
  if (!d || typeof d !== "object") {
    throw new TypeError(`ModelStats: expected object, got ${typeof d}`);
  }
  if (d.muted != null && typeof d.muted !== "boolean") {
    throw new TypeError(
      `ModelStats.muted: expected boolean, got ${typeof d.muted}`,
    );
  }
  if (d.raw_status != null && typeof d.raw_status !== "string") {
    throw new TypeError(
      `ModelStats.raw_status: expected string|null, got ${typeof d.raw_status}`,
    );
  }
  return { muted: Boolean(d.muted), raw_status: d.raw_status ?? null };
}
