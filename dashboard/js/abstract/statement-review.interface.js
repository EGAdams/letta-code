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
  UNSUPPORTED: "unsupported",
});

/** Rows the human must actually answer (those missing an amount). */
export function answerableRows(item) {
  if (!item || item.kind !== REVIEW_KIND.AMOUNTS) return [];
  return (item.rows || []).filter((row) =>
    (row.missing || []).includes("amount"),
  );
}

/** One input descriptor for every field the statement validator rejected. */
export function answerableFields(item) {
  if (!item || item.kind !== REVIEW_KIND.AMOUNTS) return [];
  const supported = new Set(["date", "description", "amount"]);
  const fields = [];
  for (const row of item.rows || []) {
    for (const field of row.missing || []) {
      if (!supported.has(field)) continue;
      fields.push({
        ...row,
        field,
        key: `${row.index}:${field}`,
        inputType: field === "date" ? "date" : "text",
      });
    }
  }
  return fields;
}

/** Prefill for a field: arithmetic amount suggestion, existing value, or blank. */
export function prefillFor(row, field = "amount") {
  if (field === "amount") {
    const suggested = row && row.suggested_amount;
    return typeof suggested === "number" && Number.isFinite(suggested)
      ? suggested.toFixed(2)
      : "";
  }
  return String((row && row[field]) || "");
}

/**
 * Validate what the human typed, per missing field.
 * Returns { corrections, errors } — corrections are grouped by row index.
 * A blank or non-positive entry is an error, never silently skipped: skipping
 * would resubmit the statement with the same hole and quarantine it again.
 */
export function collectCorrections(item, rawValues) {
  const corrections = {};
  const errors = {};
  answerableFields(item).forEach((entry) => {
    const raw = String((rawValues && rawValues[entry.key]) ?? "").trim();
    if (raw === "") {
      errors[entry.key] =
        entry.field === "date"
          ? "Enter the transaction date."
          : entry.field === "description"
            ? "Enter the merchant or description."
            : "Enter the amount for this row.";
      return;
    }
    let value = raw;
    if (entry.field === "amount") {
      value = Number(raw.replace(/[$,]/g, ""));
      if (!Number.isFinite(value) || value <= 0) {
        errors[entry.key] = "Enter a dollar amount like 4.50";
        return;
      }
    } else if (entry.field === "date" && !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
      errors[entry.key] = "Enter a date like 2025-09-15";
      return;
    }
    corrections[entry.index] ||= {};
    corrections[entry.index][entry.field] = value;
  });
  return { corrections, errors };
}

/** Backward-compatible amount-only projection. */
export function collectAmounts(item, rawValues) {
  const keyed = {};
  for (const row of answerableRows(item)) {
    keyed[`${row.index}:amount`] =
      rawValues && (rawValues[`${row.index}:amount`] ?? rawValues[row.index]);
  }
  const { corrections, errors: keyedErrors } = collectCorrections(item, keyed);
  const amounts = {};
  for (const [index, fields] of Object.entries(corrections)) {
    if (fields.amount !== undefined) amounts[index] = fields.amount;
  }
  const errors = {};
  for (const [key, error] of Object.entries(keyedErrors)) {
    errors[key.split(":")[0]] = error;
  }
  return { amounts, errors };
}

/** True when every answerable row has a valid entry. */
export function isSubmittable(item, rawValues) {
  if (!item) return false;
  if (item.kind === REVIEW_KIND.WORKBOOK) return true; // OK is always pressable
  const fields = answerableFields(item);
  if (!fields.length) return false;
  const { errors } = collectCorrections(item, rawValues);
  return Object.keys(errors).length === 0;
}

/** The body for POST /api/statement-review-resolve. */
export function buildResolvePayload(item, rawValues) {
  if (!item) return null;
  if (item.kind === REVIEW_KIND.WORKBOOK) return { id: item.id };
  const { corrections, errors } = collectCorrections(item, rawValues);
  if (Object.keys(errors).length) return null;
  if (!Object.keys(corrections).length) return null;
  return { id: item.id, corrections };
}

/** Complete, editable handoff placed in Mazda's real Input Options textarea. */
export function buildMazdaReviewPrompt(item) {
  if (!item) return "";
  const context = item.document_context || {
    pending_review_id: item.id,
    quarantined_document_path: item.document_path,
    source_file: item.source_file,
    kind: item.kind,
    bank_name: item.bank_name,
    account_last4: item.account_last4,
    workbook_ambiguous_last4: item.workbook_ambiguous_last4,
    statement_total: item.statement_total,
    reason: item.reason,
    rows: item.rows,
  };
  return [
    "# Goal",
    "Help me resolve this statement review. Do not guess the card number.",
    "",
    "# Offending document",
    item.document_path || item.source_file || "(path unavailable)",
    "",
    "# Everything the dashboard knows",
    JSON.stringify(context, null, 2),
    "",
    "# My question for Mazda",
    "",
  ].join("\n");
}

/** Stable document identity; retries can create a newer sidecar for one source. */
export function reviewIdentity(item) {
  return (item && (item.source_file || item.id)) || null;
}

/** First server-queued document that was not deferred in this browser session. */
export function nextPendingReview(reviews, deferredIds) {
  const deferred = deferredIds || new Set();
  return (
    (reviews || []).find((item) => {
      const identity = reviewIdentity(item);
      return identity && !deferred.has(identity);
    }) || null
  );
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
      : " Check the highlighted details and try again.";
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
