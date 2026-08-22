/**
 * Pure decision logic for "Mazda Fill" -- the manual-entry form's one reading
 * button.
 *
 * It replaced five (Prefill from OCR / Gemini Flash Fill / Fill with Haiku /
 * Read with Gemini / Read with Haiku) plus the group box that tried to tell
 * the operator which of them to press. All five asked the operator to answer
 * "is this one expense or several?" before pressing anything -- a question
 * only reading the document can answer, and the local-OCR heuristic wired in
 * to guess it got the DTE gas bill wrong (filed as one $28.07 expense,
 * 2026-08-19). Now the server classifies with the same tool Mazda's automatic
 * pipeline uses, reads with whichever cheap model the operator picked, and
 * answers with the shape it FOUND. The operator's only remaining job is the
 * one a human is actually needed for: check it and press Save.
 *
 * No DOM, no fetch -- js/implementation/manual-entry-form.js renders whatever
 * these return. Response shapes are read defensively: an HTTP response is
 * untrusted shape, not just untrusted value.
 */

import { readPrefillResponse } from "./manual-entry.interface.js";
import { readStatementBreakupResponse } from "./statement-breakup.interface.js";

//: What the fill FOUND on the page -- an output, never a question put to the
//: operator.
export const FILL_SHAPE = Object.freeze({
  ONE_EXPENSE: "one-expense",
  MANY_EXPENSES: "many-expenses",
});

//: The dropdown beside the Mazda Fill button. Mirrors
//: finance/mazda_fill.MAZDA_FILL_MODELS, which is the enforcement point (a
//: model name only accepted here would bounce as a 400) and is itself pinned
//: to the intersection of both readers' --engine allow-lists. Only cheap
//: models appear: the whole reason this is semi-automatic rather than
//: autonomous is to keep the spend near zero while a human still checks every
//: page. tests/test_mazda_fill.py asserts this list and the Python one agree.
export const MAZDA_FILL_MODEL_OPTIONS = Object.freeze([
  { model: "gemini-only", label: "Gemini Flash" },
  { model: "haiku-only", label: "Claude Haiku" },
  // The ChatGPT/Codex subscription via the installed Codex CLI. "luna" names
  // the model that actually runs: the CLI default is gpt-5.6-luna.
  { model: "codex-only", label: "Codex (luna)" },
]);

export const DEFAULT_MAZDA_FILL_MODEL = "gemini-only";

/** Human label for a model value, for status lines. */
export function mazdaFillModelLabel(model) {
  const found = MAZDA_FILL_MODEL_OPTIONS.find((opt) => opt.model === model);
  return found ? found.label : model || "";
}

/**
 * @param {{imagePath: string}} intakeRef
 * @param {string} model one of MAZDA_FILL_MODEL_OPTIONS' `model` values
 * @param {?{bankName: string, accountLast4: string}} [statementMetadata]
 *   omitted on the first press; sent back only after a first pass reported
 *   the bank/account could not be resolved from the page itself
 */
export function buildMazdaFillPayload(intakeRef, model, statementMetadata) {
  return {
    image_path: intakeRef.imagePath,
    model,
    bank_name: ((statementMetadata && statementMetadata.bankName) || "").trim(),
    account_last4: (
      (statementMetadata && statementMetadata.accountLast4) ||
      ""
    ).trim(),
  };
}

/**
 * Boundary check for POST /api/mazda-fill's response.
 *
 * Both halves are always present in the returned object, and exactly one is
 * meaningful -- which one is named by `shape`. Reading the wrong half yields
 * a blank prefill / an empty item list rather than undefined, so a form that
 * branches on `shape` can never trip over a missing key.
 *
 * @typedef {Object} MazdaFillResult
 * @property {boolean} ok
 * @property {string} shape        one of FILL_SHAPE -- which half of this
 *   object the form should read; never anything else
 * @property {string} model        the model that read the page
 * @property {string} docKind      the classifier's verdict, "" if it had none
 * @property {ManualEntryFields} prefill      populated when shape is ONE_EXPENSE
 * @property {ManualEntryFields[]} items      populated when shape is MANY_EXPENSES
 * @property {ManualEntryFields[]} excludedRows  payment/credit/$0.00 lines,
 *   shown to the operator but handled by the statement store itself
 * @property {StatementHeader} header
 * @property {boolean} needsStatementMetadata
 * @property {string[]} missingFields
 * @property {?string} error
 * @property {string} rereadAfter  non-empty only when the receipt read was
 *   overruled and the page was read again as a statement; carries what the
 *   receipt reader said that changed the verdict
 *
 * @param {unknown} json
 * @returns {MazdaFillResult}
 */
export function readMazdaFillResponse(json) {
  const object = typeof json === "object" && json !== null ? json : {};
  // Anything that isn't explicitly the many-expenses answer is treated as one
  // expense: a receipt shown wrong costs the operator three field
  // corrections, while a statement shown as one expense silently discards
  // every transaction but one. The recoverable mistake is the default.
  const shape =
    object.shape === FILL_SHAPE.MANY_EXPENSES
      ? FILL_SHAPE.MANY_EXPENSES
      : FILL_SHAPE.ONE_EXPENSE;
  const statement = readStatementBreakupResponse(object.statement);
  return {
    ok: object.ok === true,
    shape,
    model: typeof object.model === "string" ? object.model : "",
    docKind: typeof object.doc_kind === "string" ? object.doc_kind : "",
    prefill: readPrefillResponse(object.receipt),
    items: statement.items,
    excludedRows: statement.excludedRows,
    header: statement.header,
    needsStatementMetadata: statement.needsStatementMetadata,
    missingFields: statement.missingFields,
    error: typeof object.error === "string" ? object.error : null,
    rereadAfter:
      typeof object.reread_after === "string" ? object.reread_after : "",
  };
}

/**
 * What the status line says when the page turned out to be a different shape
 * than the one that was read first.
 *
 * Answering a different question than the one asked, silently, is how an
 * operator stops trusting a button. The server re-reads a page as a statement
 * only when the receipt reader ANSWERED that it has no one date and no one
 * merchant, and the page's own text holds a transaction table -- so there is
 * always a specific reason, and it is worth showing.
 *
 * Returns "" when nothing was re-read, so callers can append it unconditionally.
 * @param {MazdaFillResult} result
 * @returns {string}
 */
export function summarizeMazdaReread(result) {
  if (!result || !result.rereadAfter) return "";
  return ` Read as a receipt first, then re-read as a statement: ${result.rereadAfter}`;
}
