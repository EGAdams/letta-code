/**
 * Pure decision logic for the Scanner screen's statement-review dialog.
 *
 * No DOM, no fetch — so the rules that decide what the human is asked, and what
 * gets sent back, are unit-testable in Node. The concrete dialog
 * (js/implementation/statement-review-dialog.js) renders whatever these return.
 *
 * A statement lands here only because it was refused: either its account's last
 * four digits could not be resolved ("workbook"), or one or more transaction
 * rows were unreadable ("amounts"). Nothing here ever fabricates a value — a
 * suggested amount comes from the server, which only offers one when
 * subtraction makes it certain.
 */

export const REVIEW_KIND = Object.freeze({
  WORKBOOK: "workbook",
  AMOUNTS: "amounts",
});

/** Rows the human must actually answer (those missing an amount). */
export function answerableRows(item) {
  if (!item || item.kind !== REVIEW_KIND.AMOUNTS) return [];
  return (item.rows || []).filter((row) =>
    (row.missing || []).includes("amount"),
  );
}

/** Prefill for a row's input: the server's suggestion, or blank. */
export function prefillFor(row) {
  const suggested = row && row.suggested_amount;
  return typeof suggested === "number" && Number.isFinite(suggested)
    ? suggested.toFixed(2)
    : "";
}

/**
 * Validate what the human typed, per row.
 * Returns { amounts, errors } — `amounts` keyed by row index, ready to POST.
 * A blank or non-positive entry is an error, never silently skipped: skipping
 * would resubmit the statement with the same hole and quarantine it again.
 */
export function collectAmounts(item, rawValues) {
  const amounts = {};
  const errors = {};
  answerableRows(item).forEach((row) => {
    const raw = String((rawValues && rawValues[row.index]) ?? "")
      .trim()
      .replace(/[$,]/g, "");
    if (raw === "") {
      errors[row.index] = "Enter the amount for this row.";
      return;
    }
    const value = Number(raw);
    if (!Number.isFinite(value) || value <= 0) {
      errors[row.index] = "Enter a dollar amount like 4.50";
      return;
    }
    amounts[row.index] = value;
  });
  return { amounts, errors };
}

/** True when every answerable row has a valid entry. */
export function isSubmittable(item, rawValues) {
  if (!item) return false;
  if (item.kind === REVIEW_KIND.WORKBOOK) return true; // OK is always pressable
  const { errors } = collectAmounts(item, rawValues);
  return Object.keys(errors).length === 0;
}

/** The body for POST /api/statement-review-resolve. */
export function buildResolvePayload(item, rawValues) {
  if (!item) return null;
  if (item.kind === REVIEW_KIND.WORKBOOK) return { id: item.id };
  const { amounts, errors } = collectAmounts(item, rawValues);
  if (Object.keys(errors).length) return null;
  return { id: item.id, amounts };
}

/**
 * What the dialog shows after a resolve attempt.
 * A failed workbook resolve is the "pops up again" case EG asked for: the item
 * stays, with a nudge that the sheet still doesn't have the card.
 */
export function nextStateAfterResolve(item, response) {
  if (response && response.ok) {
    return { done: true, message: successMessage(response.report) };
  }
  const stillQueued = (response && response.item) || item;
  const reason = (response && response.error) || "That did not go through.";
  const retryHint =
    stillQueued && stillQueued.kind === REVIEW_KIND.WORKBOOK
      ? " The card still is not in the sheet — add the row, save the file, then press OK again."
      : " Check the amounts and try again.";
  return { done: false, item: stillQueued, message: reason + retryHint };
}

export function successMessage(report) {
  const stored = (report && report.stored) || 0;
  const duplicates = (report && report.duplicates) || 0;
  const uncategorized = (report && report.uncategorized) || 0;
  const bits = [`Stored ${stored} transaction${stored === 1 ? "" : "s"}`];
  if (duplicates) bits.push(`${duplicates} already on file`);
  if (uncategorized) bits.push(`${uncategorized} awaiting a vendor`);
  return `${bits.join(", ")}.`;
}
