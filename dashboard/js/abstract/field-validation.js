/**
 * Field-validation primitives shared by every entry form (receipt or
 * statement row). Kept in their own module, imported by both
 * manual-entry.interface.js and statement-breakup.interface.js, so neither
 * has to import the other just to borrow a date regex.
 */

export const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

/** @param {unknown} value */
export function isNonEmptyString(value) {
  return typeof value === "string" && value.trim().length > 0;
}

/** @param {unknown} value @returns {?number} */
export function optionalNumber(value) {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}
