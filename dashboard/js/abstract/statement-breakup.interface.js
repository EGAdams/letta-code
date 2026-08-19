/**
 * Pure decision logic for treating a scanned document as a STATEMENT rather
 * than a receipt: routing it to Mazda's automatic statement pipeline
 * ("Not a receipt — process as statement"), and reading/storing it entirely
 * by hand ("Break Up Document") when MAZDA_DECISION_MODE=human_only means no
 * agent will. No DOM, no fetch — js/implementation/manual-entry-form.js
 * renders whatever these return and owns the DOM/fetch side of the boundary.
 *
 * Split out of manual-entry.interface.js (which keeps the single-expense
 * receipt concerns) once the statement half grew past a third of that file
 * on its own -- two different document shapes sharing one Prev/Next form,
 * not one shape with two buttons.
 */
import {
  ISO_DATE_RE,
  isNonEmptyString,
  optionalNumber,
} from "./field-validation.js";

/**
 * @typedef {Object} StatementMetadataInput
 * @property {string} bankName
 * @property {string} accountLast4
 *
 * @typedef {Object} StatementRouteResult
 * @property {boolean} ok
 * @property {boolean} needsStatementMetadata  true when the scan is a real
 *   statement but bank_name/account_last4 couldn't be resolved -- the caller
 *   should collect those and retry with statementMetadata set
 * @property {boolean} rejected  true when the scan can never be filed as-is
 *   (more than one account on the page, no complete transaction found) --
 *   retrying with different metadata will not help; the document itself
 *   needs to be rescanned or split
 * @property {string[]} missingFields
 * @property {boolean} mazdaDispatched
 * @property {?string} error
 */

/**
 * "Not a receipt — process as statement" escape hatch: builds the POST
 * /api/process-document body with doc_kind_override='statement', so the
 * server skips Mazda's own (paid) vision classify call -- the operator has
 * already looked at the document (see the Show Image button) and knows what
 * it is, so paying to re-derive that is wasted spend in
 * MAZDA_DECISION_MODE=human_only, whose whole point is zero-token operation.
 * @param {string} scannerKey
 * @param {?StatementMetadataInput} [statementMetadata] omit on the first
 *   attempt; pass the operator-typed values back in only after a first
 *   response comes back with needsStatementMetadata:true
 */
export function buildStatementRoutePayload(scannerKey, statementMetadata) {
  const payload = { scanner: scannerKey, doc_kind_override: "statement" };
  const bankName = (statementMetadata && statementMetadata.bankName) || "";
  const accountLast4 =
    (statementMetadata && statementMetadata.accountLast4) || "";
  if (bankName.trim() || accountLast4.trim()) {
    payload.statement_metadata = {
      bank_name: bankName.trim(),
      account_last4: accountLast4.trim(),
    };
  }
  return payload;
}

/**
 * Boundary check for POST /api/process-document's response when routed via
 * doc_kind_override. Never trusts the shape blindly -- a stray key or a
 * proxy error page must read as ok:false with an error, not throw mid-render.
 * @param {unknown} json
 * @returns {StatementRouteResult}
 */
export function readStatementRouteResponse(json) {
  const blank = {
    ok: false,
    needsStatementMetadata: false,
    rejected: false,
    missingFields: [],
    mazdaDispatched: false,
    error: "malformed response",
  };
  if (typeof json !== "object" || json === null) return blank;
  const missingFields = Array.isArray(json.missing_fields)
    ? json.missing_fields.filter((f) => typeof f === "string" && f)
    : [];
  return {
    ok: json.ok === true,
    needsStatementMetadata: json.needs_statement_metadata === true,
    rejected: json.statement_rejected === true,
    missingFields,
    mazdaDispatched: json.mazda_dispatched === true,
    error:
      typeof json.stage_error === "string"
        ? json.stage_error
        : typeof json.error === "string"
          ? json.error
          : null,
  };
}

/**
 * @typedef {Object} StatementHeader
 * @property {string} bankName
 * @property {string} accountLast4
 * @property {string} last4Source   "" | "operator" | "known_cards_workbook"
 * @property {?number} statementTotal
 *
 * @typedef {Object} StatementBreakupResult
 * @property {boolean} ok
 * @property {StatementHeader} header
 * @property {ManualEntryFields[]} items  reviewable rows, one per navigable
 *   Prev/Next stop, in page order -- excludes payments/credits/zero-amount
 *   lines the store was always going to skip (see `excludedRows`)
 * @property {ManualEntryFields[]} excludedRows  rows left off `items` because
 *   they read as a payment/credit or a $0.00 line, not an expense. Still sent
 *   to the store on Save All (see buildStatementEntryPayload) -- the store
 *   needs the complete page to reach the same verdict, and reports these back
 *   as `skipped_credits`. Kept here only so the operator sees what was left
 *   out and why, instead of the row silently vanishing.
 * @property {boolean} needsStatementMetadata
 * @property {string[]} missingFields
 * @property {?string} error
 */

/**
 * "Break Up Document": ask the server to read EVERY transaction off a scanned
 * statement, using the same parse_statement_scan.py preflight the automatic
 * pipeline runs. The receipt-shaped fill buttons can only ever answer with one
 * expense (a receipt has one), which is why a five-transaction statement page
 * came back as a single row.
 * @param {IntakeRef} intakeRef
 * @param {?StatementMetadataInput} [statementMetadata] operator-typed bank /
 *   last-four, sent back only after a first pass reported them missing
 * @param {string} [engine] one of STATEMENT_ENGINE's values -- which button
 *   the operator pressed. The server's own STATEMENT_ENGINES allow-list is
 *   the enforcement point (never trust the client alone); this default just
 *   keeps a caller from having to spell out "auto" for the common case.
 */
export function buildStatementBreakupPayload(
  intakeRef,
  statementMetadata,
  engine = "auto",
) {
  return {
    image_path: intakeRef.imagePath,
    bank_name: ((statementMetadata && statementMetadata.bankName) || "").trim(),
    account_last4: (
      (statementMetadata && statementMetadata.accountLast4) ||
      ""
    ).trim(),
    engine,
  };
}

/**
 * Boundary check for POST /api/manual-statement-breakup's response.
 *
 * Rows are returned even when ok is false: a needs_statement_metadata result
 * means the transactions were read and only the account identity is missing,
 * so the operator should be looking at the five expenses while typing the bank
 * in -- not at an empty form behind an error.
 * @param {unknown} json
 * @returns {StatementBreakupResult}
 */
function statementRowToFields(row) {
  return {
    merchantName: typeof row.description === "string" ? row.description : "",
    transactionDate:
      typeof row.transaction_date === "string" ? row.transaction_date : "",
    totalAmount: optionalNumber(row.amount) === null ? "" : String(row.amount),
    // Statements are stored UNCATEGORIZED on purpose: store_statement_
    // transactions.py resolves each vendor itself and files anything it can't
    // as NEEDS_VENDOR_KEY, which is what puts the row in the New Records
    // queue. A category typed here would be discarded, so the form leaves it
    // blank rather than implying otherwise.
    categoryName: "",
  };
}

export function readStatementBreakupResponse(json) {
  const blank = {
    ok: false,
    header: {
      bankName: "",
      accountLast4: "",
      last4Source: "",
      statementTotal: null,
    },
    items: [],
    excludedRows: [],
    needsStatementMetadata: false,
    missingFields: [],
    error: "malformed response",
  };
  if (typeof json !== "object" || json === null) return blank;
  const rows = (
    Array.isArray(json.transactions) ? json.transactions : []
  ).filter((row) => typeof row === "object" && row !== null);
  // reviewable is the extractor's own verdict, computed over the whole page's
  // signs (statement_credit_split.reviewable_flags) -- a per-row read here
  // can't tell a mixed-sign page from an all-purchases one, so this only ever
  // reads the flag rather than recomputing it.
  return {
    ok: json.ok === true,
    header: {
      bankName: typeof json.bank_name === "string" ? json.bank_name : "",
      accountLast4:
        typeof json.account_last4 === "string" ? json.account_last4 : "",
      last4Source:
        typeof json.last4_source === "string" ? json.last4_source : "",
      statementTotal: optionalNumber(json.statement_total),
    },
    items: rows
      .filter((row) => row.reviewable !== false)
      .map(statementRowToFields),
    excludedRows: rows
      .filter((row) => row.reviewable === false)
      .map(statementRowToFields),
    needsStatementMetadata: json.needs_statement_metadata === true,
    missingFields: Array.isArray(json.missing_fields)
      ? json.missing_fields.filter((f) => typeof f === "string" && f)
      : [],
    error: typeof json.error === "string" ? json.error : null,
  };
}

/**
 * "Found 4 transaction(s) to review — 2 more aren't expenses (a payment or a
 * $0.00 line) and will be handled by the statement store automatically."
 *
 * Excluded rows are never just dropped silently: the operator needs to see
 * what was left off the list and why, even though nothing they can do with
 * Prev/Next would change the outcome for those rows.
 * @param {ManualEntryFields[]} excludedRows
 */
export function summarizeExcludedStatementRows(excludedRows) {
  if (!excludedRows.length) return "";
  const named = excludedRows
    .map((row) => {
      const amount = optionalNumber(row.totalAmount);
      const label = amount === null ? row.totalAmount : amount.toFixed(2);
      return `${row.merchantName} ($${label})`;
    })
    .join(", ");
  return (
    `${excludedRows.length} more line(s) on this page aren't expenses ` +
    `(a payment/credit or a $0.00 line) and will be handled by the ` +
    `statement store automatically: ${named}.`
  );
}

/**
 * The two rules a statement row must satisfy before it can be stored.
 *
 * Deliberately NOT validateManualEntry: that requires a positive amount, and a
 * statement page legitimately carries credits ("PAYMENT - THANK YOU
 * $2,900.00-"). Which rows are credits is store_statement_transactions.py's
 * decision -- it reads the whole page's sign convention -- so the form's job is
 * to refuse only a row that is empty or nonsense, never to pre-judge the sign.
 * @param {ManualEntryFields} fields
 * @returns {ManualEntryValidation}
 */
export function validateStatementRow(fields) {
  const errors = {};
  if (!isNonEmptyString(fields && fields.merchantName)) {
    errors.merchantName = "Description/merchant is required.";
  }
  if (!ISO_DATE_RE.test((fields && fields.transactionDate) || "")) {
    errors.transactionDate = "Date must be in yyyy-mm-dd form.";
  }
  const amount = Number(fields && fields.totalAmount);
  if (
    !isNonEmptyString(fields && fields.totalAmount) ||
    !Number.isFinite(amount) ||
    amount === 0
  ) {
    errors.totalAmount = "Amount must be a non-zero number (credits negative).";
  }
  return { valid: Object.keys(errors).length === 0, errors };
}

/**
 * Every corrected row -> the single POST /api/manual-statement-entry body.
 *
 * One request for the whole page, not one per row: the store dedupes and
 * archives a statement as a unit, so five posts would run the account
 * verification and archive move five times and report five unrelated outcomes.
 * @param {ManualEntryFields[]} items
 * @param {IntakeRef} intakeRef
 * @param {StatementHeader} header
 */
export function buildStatementEntryPayload(items, intakeRef, header) {
  return {
    image_path: intakeRef.imagePath,
    conversation_id: intakeRef.conversationId,
    bank_name: header.bankName.trim(),
    account_last4: header.accountLast4.trim(),
    last4_source: header.last4Source || "",
    statement_total: header.statementTotal,
    transactions: items.map((item) => ({
      transaction_date: item.transactionDate,
      description: item.merchantName.trim(),
      amount: Number(item.totalAmount),
    })),
  };
}

/**
 * @typedef {Object} StatementEntryResult
 * @property {boolean} ok
 * @property {number} transactionsParsed
 * @property {number} stored
 * @property {number} duplicates
 * @property {number} skippedCredits
 * @property {number} uncategorized
 * @property {number} failed
 * @property {number[]} expenseIds
 * @property {string[]} problems
 * @property {?string} error
 */

/** @param {unknown} value @returns {number} */
function countOf(value) {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

/**
 * Boundary check for POST /api/manual-statement-entry's response.
 * @param {unknown} json
 * @returns {StatementEntryResult}
 */
export function readStatementEntryResponse(json) {
  const blank = {
    ok: false,
    transactionsParsed: 0,
    stored: 0,
    duplicates: 0,
    skippedCredits: 0,
    uncategorized: 0,
    failed: 0,
    expenseIds: [],
    problems: [],
    error: "malformed response",
  };
  if (typeof json !== "object" || json === null) return blank;
  return {
    ok: json.ok === true,
    transactionsParsed: countOf(json.transactions_parsed),
    stored: countOf(json.stored),
    duplicates: countOf(json.duplicates),
    skippedCredits: countOf(json.skipped_credits),
    uncategorized: countOf(json.uncategorized),
    failed: countOf(json.failed),
    expenseIds: Array.isArray(json.expense_ids)
      ? json.expense_ids.filter((id) => typeof id === "number")
      : [],
    problems: Array.isArray(json.problems)
      ? json.problems.map((p) => String(p))
      : [],
    error: typeof json.error === "string" ? json.error : null,
  };
}

/**
 * The store's own counts, as one sentence for the status line.
 *
 * The counts come from store_statement_transactions.py, not from the form:
 * "2 stored" already excludes the credits it skipped and the duplicates it
 * recognized, which is exactly what a human hand-entering five statement lines
 * cannot work out for themselves.
 * @param {StatementEntryResult} result
 */
export function summarizeStatementStore(result) {
  const parts = [
    `${result.transactionsParsed} transaction(s) read`,
    `${result.stored} stored`,
  ];
  if (result.duplicates) parts.push(`${result.duplicates} already on file`);
  if (result.skippedCredits)
    parts.push(
      `${result.skippedCredits} credit/payment skipped (not expenses)`,
    );
  if (result.uncategorized)
    parts.push(`${result.uncategorized} awaiting a vendor key`);
  if (result.failed) parts.push(`${result.failed} failed`);
  return `${parts.join(" · ")}.`;
}

//: The two single-provider, no-fallback engines the dashboard's own
//: "Read with Gemini"/"Read with Haiku" buttons may request -- mirrors
//: rol_finances' parse_statement_scan.py STATEMENT_PREVIEW_ENGINES ("auto" is
//: a valid value there too, but never offered by these two buttons: an
//: operator who already chose a provider must get exactly that one, with no
//: silent fallback to a different one on failure).
export const STATEMENT_ENGINE = Object.freeze({
  GEMINI_ONLY: "gemini-only",
  HAIKU_ONLY: "haiku-only",
});

/**
 * @typedef {Object} StatementEngineOption
 * @property {string} engine  one of STATEMENT_ENGINE's values
 * @property {string} label   the button text
 */

//: Drives both the fieldset's two buttons and their POST bodies from one
//: list, so adding or renaming an engine never has to touch two places.
export const STATEMENT_ENGINE_OPTIONS = Object.freeze([
  { engine: STATEMENT_ENGINE.GEMINI_ONLY, label: "Read with Gemini" },
  { engine: STATEMENT_ENGINE.HAIKU_ONLY, label: "Read with Haiku" },
]);

//: Shown in the win98-styled Info dialog right after ANY receipt-shaped fill
//: (Prefill from OCR / Gemini Flash Fill / Fill with Haiku) when the zero-cost
//: local-OCR pass's own raw text looks like a statement's transaction table
//: (see finance/statement_heuristic.py's looks_like_multiple_transactions,
//: mirrored here only as the message text -- the server is the one place the
//: actual detection runs). A receipt fill can only ever answer with one
//: merchant/date/amount, so this is the nudge toward the tool built for more
//: than one.
export const POSSIBLE_STATEMENT_INFO_MESSAGE =
  "This document may contain more than one expense. Use the Break up " +
  "Document buttons below to read every transaction on the page.";
