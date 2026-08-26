/**
 * The rules behind the Verified Transactions row buttons — Edit, Delete,
 * Add 6% — with no DOM and no fetch anywhere in the file.
 *
 * Why the split (see js/README.md): every one of these rules is a sentence
 * about money or about a list index, and both are the kind of thing that is
 * wrong in a way nobody notices for a month. Deleting expense 3 of 3 while the
 * review dialog is sitting on expense 3 has to leave the dialog somewhere
 * valid; a tax call that comes back malformed has to mean "nothing changed",
 * not "changed to NaN". Kept here they are ordinary unit tests
 * (js/tests/verified-transaction-actions.test.js); kept in the click handler
 * they would only ever be tested by clicking.
 *
 * The 6% itself is deliberately NOT here. finance/sales_tax.py owns Michigan's
 * rate and does the arithmetic in Decimal, so the browser asks the server to
 * add the tax rather than computing a new amount and sending it up — a rate
 * duplicated in a script tag is a rate that drifts from the one the reports
 * were built with. What this module owns is what the operator is told.
 */

/** @typedef {{expenseId: number, description: string, amount: string, date: string}} VerifiedRow */

/** The dialog's exact wording, so the test and the screen cannot disagree. */
export function deleteConfirmMessage(description) {
  const named = String(description ?? "").trim();
  // A row with no description still has to be deletable, and "Delete Expense
  // ?" names nothing. Fall back to the noun the operator can see.
  return `Delete Expense ${named || "(no description)"}?`;
}

/**
 * Where the review dialog's Prev/Next should land after one item is removed.
 *
 * The rule is "stay where you were, unless where you were no longer exists".
 * Removing an item BEFORE the current one shifts the current one down a slot,
 * so the index has to follow it or the dialog silently jumps to its neighbour.
 * An empty list answers 0: the form re-seeds itself with one blank item rather
 * than showing no fields at all.
 *
 * @param {number} currentIndex
 * @param {number} removedIndex
 * @param {number} remainingCount items left AFTER the removal
 */
export function indexAfterRemoval(currentIndex, removedIndex, remainingCount) {
  if (remainingCount <= 0) return 0;
  const next = removedIndex < currentIndex ? currentIndex - 1 : currentIndex;
  return Math.max(0, Math.min(next, remainingCount - 1));
}

/** POST /api/expense-delete body. */
export function buildDeletePayload(expenseId) {
  return { expense_id: Number(expenseId) };
}

/**
 * POST /api/expense-add-tax body.
 *
 * No rate is sent. The server's default IS Michigan's 6%, and naming it here
 * would put a second copy of the number on the page whose only job would be
 * to agree with the first one.
 */
export function buildAddTaxPayload(expenseId) {
  return { expense_id: Number(expenseId) };
}

/**
 * Read either write's response. Fails closed on anything unexpected: a
 * malformed reply means "the row is unchanged", never a guessed new amount.
 *
 * @returns {{ok: boolean, error: string, record: ?object, taxAdded: ?number}}
 */
export function readRowActionResponse(json) {
  if (!json || typeof json !== "object") {
    return {
      ok: false,
      error: "No response from the server.",
      record: null,
      taxAdded: null,
    };
  }
  if (json.ok !== true) {
    return {
      ok: false,
      error: String(json.error || "The server refused the change."),
      record: null,
      taxAdded: null,
    };
  }
  const record =
    json.record && typeof json.record === "object" ? json.record : null;
  return {
    ok: true,
    error: "",
    record,
    taxAdded: typeof json.tax_added === "number" ? json.tax_added : null,
  };
}

/** How much money a row now shows, as the table prints it. */
export function formatRowAmount(value) {
  const amount = Number(value);
  return Number.isFinite(amount) ? amount.toFixed(2) : "";
}

/**
 * The row's amount after a tax add, keeping the sign the table was showing.
 *
 * The server answers with the magnitude (ExpenseRecord.total_amount is always
 * positive); the table prints the stored, signed figure. Re-applying the sign
 * here is what stops an expense stored as -28.73 from redrawing as 30.45 and
 * reading like a credit.
 */
export function signedAmountAfterTax(previousDisplayed, newMagnitude) {
  const magnitude = Number(newMagnitude);
  if (!Number.isFinite(magnitude)) return "";
  const wasNegative = String(previousDisplayed ?? "")
    .trim()
    .startsWith("-");
  return formatRowAmount(
    wasNegative ? -Math.abs(magnitude) : Math.abs(magnitude),
  );
}
