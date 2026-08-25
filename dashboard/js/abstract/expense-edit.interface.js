/**
 * Pure decision logic for the "Edit Expense" dialog.
 *
 * Save All (manual-entry.interface.js) only ever inserts. This is the other
 * half: find a row that is already stored, then correct it. No DOM, no fetch —
 * the same three field rules finance/expense_fields.py enforces are checked
 * here first, and every response is shape-checked at the boundary, so a
 * malformed reply degrades to "nothing found" instead of throwing inside the
 * dialog.
 *
 * Field validation is deliberately *not* re-implemented here: it is imported
 * from manual-entry.interface.js, because an edit must never be allowed to
 * write a value a fresh entry would have been refused — exactly the reason
 * ExpenseEdit inherits ExpenseFieldRules on the Python side.
 *
 * @typedef {Object} ExpenseSearchCriteria
 * @property {string} merchant     free text matched against description/vendor key
 * @property {string} dateFrom     ISO yyyy-mm-dd, or ""
 * @property {string} dateTo       ISO yyyy-mm-dd, or ""
 * @property {string} amount       raw text from the input, not yet parsed
 *
 * @typedef {Object} ExpenseRecord
 * @property {number} id
 * @property {string} transactionDate  ISO yyyy-mm-dd
 * @property {number} totalAmount      always positive; the stored sign is the
 *   server's business, not the operator's
 * @property {string} description
 * @property {string} idLight immutable transaction filing key, not a vendor
 * @property {string} categoryName
 *
 * @typedef {Object} ExpenseSearchResult
 * @property {boolean} ok
 * @property {ExpenseRecord[]} records
 * @property {?string} error
 *
 * @typedef {Object} ExpenseEditResult
 * @property {boolean} ok
 * @property {?ExpenseRecord} record
 * @property {string[]} changedFields
 * @property {string[]} warnings
 * @property {?string} error
 */

import {
  formatAmountForDisplay,
  validateManualEntry,
} from "./manual-entry.interface.js";

const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

/** @param {unknown} value */
function isPlainObject(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** @param {unknown} value */
function asString(value) {
  return typeof value === "string" ? value : "";
}

/** @param {unknown} value */
function asFiniteNumber(value) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

/** Non-empty strings only — anything else in the array is dropped.
 * @param {unknown} value */
function asStringArray(value) {
  if (!Array.isArray(value)) return [];
  return value.filter((item) => typeof item === "string" && item);
}

/** A blank criteria object — every field present, so callers never see undefined. */
export function blankSearchCriteria() {
  return { merchant: "", dateFrom: "", dateTo: "", amount: "" };
}

/**
 * The mirror of ExpenseSearchCriteria's `_at_least_one_criterion`: an empty
 * search is a mistake, not a request for the whole table. Checked here so the
 * operator is told before a pointless round trip.
 * @param {ExpenseSearchCriteria} criteria
 * @returns {{valid: boolean, errors: Object<string,string>}}
 */
export function validateSearchCriteria(criteria) {
  const errors = {};
  const merchant = asString(criteria && criteria.merchant).trim();
  const dateFrom = asString(criteria && criteria.dateFrom).trim();
  const dateTo = asString(criteria && criteria.dateTo).trim();
  const amountText = asString(criteria && criteria.amount).trim();

  if (dateFrom && !ISO_DATE_RE.test(dateFrom)) {
    errors.dateFrom = "From date must be in yyyy-mm-dd form.";
  }
  if (dateTo && !ISO_DATE_RE.test(dateTo)) {
    errors.dateTo = "To date must be in yyyy-mm-dd form.";
  }
  if (
    !errors.dateFrom &&
    !errors.dateTo &&
    dateFrom &&
    dateTo &&
    dateFrom > dateTo
  ) {
    errors.dateTo = "From date must not be after the To date.";
  }
  if (amountText) {
    const amount = Number(amountText);
    if (!Number.isFinite(amount) || amount <= 0) {
      errors.amount = "Amount must be a positive number.";
    }
  }
  if (!merchant && !dateFrom && !dateTo && !amountText) {
    errors.merchant = "Enter a merchant, a date range, or an amount to search.";
  }
  return { valid: Object.keys(errors).length === 0, errors };
}

/**
 * Criteria -> the JSON POST /api/expense-search expects. Only called after
 * validateSearchCriteria reports valid:true; this does coercion, not
 * validation, so the amount really is a JSON number (the server's
 * ExpenseSearchCriteria is strict=True and rejects a string).
 * @param {ExpenseSearchCriteria} criteria
 * @param {number} [limit]
 */
export function buildSearchPayload(criteria, limit) {
  const amountText = asString(criteria.amount).trim();
  return {
    merchant: asString(criteria.merchant).trim(),
    date_from: asString(criteria.dateFrom).trim(),
    date_to: asString(criteria.dateTo).trim(),
    amount: amountText ? Number(amountText) : null,
    ...(typeof limit === "number" ? { limit } : {}),
  };
}

/**
 * Boundary check for one record inside a search or edit response. Returns null
 * for anything that is not a usable row, so a single malformed entry is
 * dropped instead of poisoning the whole list.
 * @param {unknown} raw
 * @returns {?ExpenseRecord}
 */
export function readExpenseRecord(raw) {
  if (!isPlainObject(raw)) return null;
  const id = asFiniteNumber(raw.id);
  const totalAmount = asFiniteNumber(raw.total_amount);
  const transactionDate = asString(raw.transaction_date);
  if (id === null || totalAmount === null) return null;
  if (!ISO_DATE_RE.test(transactionDate)) return null;
  return {
    id,
    transactionDate,
    totalAmount: Math.abs(totalAmount),
    description: asString(raw.description),
    idLight: asString(raw.id_light),
    categoryName: asString(raw.category_name),
  };
}

/**
 * Boundary check for POST /api/expense-search's response.
 * @param {unknown} json
 * @returns {ExpenseSearchResult}
 */
export function readSearchResponse(json) {
  if (!isPlainObject(json)) {
    return { ok: false, records: [], error: "malformed response" };
  }
  if (json.ok !== true) {
    return {
      ok: false,
      records: [],
      error: asString(json.error) || "search failed",
    };
  }
  const rows = Array.isArray(json.records) ? json.records : [];
  return {
    ok: true,
    records: rows.map(readExpenseRecord).filter((row) => row !== null),
    error: null,
  };
}

/**
 * A stored record -> the editable field shape the manual-entry validator and
 * the shared form inputs already speak. This is the seam that lets one set of
 * field rules cover both an insert and an edit.
 * @param {ExpenseRecord} record
 * @returns {import("./manual-entry.interface.js").ManualEntryFields}
 */
export function recordToFields(record) {
  return {
    merchantName: record.description,
    transactionDate: record.transactionDate,
    totalAmount: formatAmountForDisplay(String(record.totalAmount)),
    categoryName: record.categoryName,
  };
}

/**
 * Fields + the row being corrected -> the JSON POST /api/expense-edit expects.
 * Returns null when the fields are not valid, so a caller cannot skip the
 * check on the way to building a request.
 * @param {number} expenseId
 * @param {import("./manual-entry.interface.js").ManualEntryFields} fields
 */
export function buildEditPayload(expenseId, fields) {
  if (!Number.isInteger(expenseId) || expenseId <= 0) return null;
  if (!validateManualEntry(fields).valid) return null;
  return {
    expense_id: expenseId,
    merchant_name: fields.merchantName.trim(),
    transaction_date: fields.transactionDate,
    total_amount: Number(fields.totalAmount),
    category_name: (fields.categoryName || "").trim(),
    ...(fields.knownVendorKey === "__new__"
      ? {
          vendor_key: (fields.newVendorKey || "").trim(),
          learn_vendor: true,
        }
      : fields.knownVendorKey
        ? { vendor_key: fields.knownVendorKey, learn_vendor: false }
        : {}),
  };
}

/**
 * Boundary check for POST /api/expense-edit's response.
 * @param {unknown} json
 * @returns {ExpenseEditResult}
 */
export function readEditResponse(json) {
  const blank = {
    ok: false,
    record: null,
    changedFields: [],
    warnings: [],
    vendorRemembered: null,
    error: "malformed response",
  };
  if (!isPlainObject(json)) return blank;
  if (json.ok !== true) {
    return { ...blank, error: asString(json.error) || "edit failed" };
  }
  return {
    ok: true,
    record: readExpenseRecord(json.record),
    changedFields: asStringArray(json.changed_fields),
    warnings: asStringArray(json.warnings),
    vendorRemembered:
      isPlainObject(json.vendor_remembered) &&
      typeof json.vendor_remembered.vendor_key === "string"
        ? {
            remembered: json.vendor_remembered.remembered === true,
            vendorKey: json.vendor_remembered.vendor_key,
          }
        : null,
    error: null,
  };
}

/**
 * One-line summary of a saved edit, including the "nothing actually changed"
 * case — re-saving identical values is a no-op worth reporting as one rather
 * than as a success that implies a write happened.
 * @param {ExpenseEditResult} result
 */
export function describeEditResult(result) {
  if (!result.ok) return result.error || "edit failed";
  if (!result.changedFields.length) {
    return "No changes — the values you saved match what was already stored.";
  }
  const id = result.record ? ` (expense ${result.record.id})` : "";
  return `Saved${id}: updated ${result.changedFields.join(", ")}.`;
}

/**
 * How one row reads in the results list.
 * @param {ExpenseRecord} record
 */
export function formatRecordLabel(record) {
  const amount = formatAmountForDisplay(String(record.totalAmount));
  const category = record.categoryName || "Uncategorized";
  // idLight is a filing identifier, not merchant text. Do not surface it as
  // a pretend vendor when description is absent.
  const name = record.description || "(no description)";
  return `#${record.id} · ${record.transactionDate} · $${amount} · ${name} · ${category}`;
}
