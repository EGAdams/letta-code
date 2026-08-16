/**
 * Pure decision logic for the needs_human_review manual receipt entry form.
 *
 * No DOM, no fetch — so the same three field rules the server's
 * finance/manual_entry.py enforces (non-empty merchant, ISO date, positive
 * amount) are checked here too, before a request is ever sent, and are
 * unit-testable in Node/bun without a browser. The concrete form
 * (js/implementation/manual-entry-form.js) renders whatever these return and
 * owns the DOM/fetch side of the boundary.
 *
 * @typedef {Object} ManualEntryFields
 * @property {string} merchantName
 * @property {string} transactionDate  ISO yyyy-mm-dd
 * @property {string} totalAmount      raw text from the input, not yet parsed
 * @property {string} categoryName     one of /api/rol-finance-categories' names, or ""
 *
 * @typedef {Object} ManualEntryValidation
 * @property {boolean} valid
 * @property {Object<string,string>} errors  field name -> message, only when invalid
 *
 * @typedef {Object} IntakeRef
 * @property {string} imagePath
 * @property {string} conversationId
 *
 * @typedef {Object} ManualEntryPrefill
 * @property {boolean} ok
 * @property {?string} merchantName
 * @property {?string} transactionDate
 * @property {?number} totalAmount
 * @property {?string} error
 *
 * @typedef {Object} VendorOption
 * @property {string} vendorKey
 * @property {?string} categoryName  the vendor's known category, if any -- lets
 *   picking a vendor also prefill the category dropdown
 */

const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

/** @param {string} value */
function isNonEmptyString(value) {
  return typeof value === "string" && value.trim().length > 0;
}

/**
 * The three rules finance/manual_entry.py's ManualReceiptEntry enforces,
 * checked here first so a malformed submission never round-trips to the
 * server just to bounce back.
 * @param {ManualEntryFields} fields
 * @returns {ManualEntryValidation}
 */
export function validateManualEntry(fields) {
  const errors = {};
  if (!isNonEmptyString(fields && fields.merchantName)) {
    errors.merchantName = "Merchant/vendor name is required.";
  }
  if (!ISO_DATE_RE.test((fields && fields.transactionDate) || "")) {
    errors.transactionDate = "Date must be in yyyy-mm-dd form.";
  }
  const amount = Number(fields && fields.totalAmount);
  if (!Number.isFinite(amount) || amount <= 0) {
    errors.totalAmount = "Amount must be a positive number.";
  }
  // categoryName has no client-side format to check -- "" (Uncategorized) is
  // always valid, and any other value is checked against the live taxonomy
  // server-side (_resolve_reporting_category), not duplicated here.
  return { valid: Object.keys(errors).length === 0, errors };
}

/**
 * Field values -> the exact JSON shape POST /api/manual-receipt-entry
 * expects. Only called after validateManualEntry reports valid:true — this
 * does no validation of its own, only type coercion, so the numbers really
 * are JSON numbers (the server's ManualReceiptEntry is strict=True and
 * rejects a numeric field arriving as a string).
 * @param {ManualEntryFields} fields
 * @param {IntakeRef} intakeRef
 */
export function buildSubmitPayload(fields, intakeRef) {
  return {
    image_path: intakeRef.imagePath,
    conversation_id: intakeRef.conversationId,
    merchant_name: fields.merchantName.trim(),
    transaction_date: fields.transactionDate,
    total_amount: Number(fields.totalAmount),
    category_name: (fields.categoryName || "").trim(),
  };
}

/** @param {IntakeRef} intakeRef */
export function buildPreviewPayload(intakeRef) {
  return { image_path: intakeRef.imagePath };
}

/**
 * Boundary check for POST /api/manual-receipt-entry-preview's response: an
 * HTTP response is untrusted shape, not just untrusted value. Returns a safe
 * "nothing found" prefill instead of throwing, so a malformed response never
 * crashes the form — it just leaves the fields blank, same as OCR finding
 * nothing.
 * @param {unknown} json
 * @returns {ManualEntryPrefill}
 */
export function readPrefillResponse(json) {
  const blank = {
    ok: false,
    merchantName: null,
    transactionDate: null,
    totalAmount: null,
    error: "malformed response",
  };
  if (typeof json !== "object" || json === null) return blank;
  const merchantName =
    typeof json.merchant_name === "string" ? json.merchant_name : null;
  const transactionDate =
    typeof json.transaction_date === "string" ? json.transaction_date : null;
  const totalAmount =
    typeof json.total_amount === "number" && Number.isFinite(json.total_amount)
      ? json.total_amount
      : null;
  return {
    ok: json.ok === true,
    merchantName,
    transactionDate,
    totalAmount,
    error: typeof json.error === "string" ? json.error : null,
  };
}

/**
 * POST /api/manual-receipt-entry's response, reduced to what the form needs
 * to know: did it work, and if not, what should the operator read.
 * @param {unknown} json
 */
export function readSubmitResponse(json) {
  if (typeof json !== "object" || json === null) {
    return { ok: false, error: "malformed response" };
  }
  if (json.ok === true) {
    return {
      ok: true,
      expenseId: typeof json.expense_id === "number" ? json.expense_id : null,
      duplicate: json.duplicate === true,
    };
  }
  return {
    ok: false,
    error: typeof json.error === "string" ? json.error : "save failed",
  };
}

/**
 * Boundary check for GET /api/vendor-keys's response. Each entry carries
 * {vendor_key, category_id, category_name} (see
 * rol_finances/tools/categorizer/python_libary/vendor_category_lookup.py);
 * only vendor_key and category_name are needed here. Any malformed entry is
 * dropped rather than crashing the dropdown.
 * @param {unknown} json
 * @returns {VendorOption[]}
 */
export function readVendorKeysResponse(json) {
  if (typeof json !== "object" || json === null || json.ok !== true) return [];
  const rows = Array.isArray(json.vendor_keys) ? json.vendor_keys : [];
  return rows
    .filter(
      (row) => row && typeof row.vendor_key === "string" && row.vendor_key,
    )
    .map((row) => ({
      vendorKey: row.vendor_key,
      categoryName:
        typeof row.category_name === "string" ? row.category_name : null,
    }));
}

/**
 * Boundary check for GET /api/rol-finance-categories's response.
 * @param {unknown} json
 * @returns {string[]}
 */
export function readCategoriesResponse(json) {
  if (typeof json !== "object" || json === null || json.ok !== true) return [];
  const names = Array.isArray(json.categories) ? json.categories : [];
  return names.filter((name) => typeof name === "string" && name);
}

/** A single blank line item for the multi-expense-per-document form. */
export function blankManualEntryFields() {
  return {
    merchantName: "",
    transactionDate: "",
    totalAmount: "",
    categoryName: "",
  };
}

export const ARCHIVE_KIND = Object.freeze({
  RECEIPT: "receipt",
  SCANNED_DOCUMENT: "scanned_document",
  OTHER: "other",
});

/**
 * A document with more than one expense on it isn't really "a receipt" in
 * the single-purchase sense -- default it to the scanned-documents archive;
 * a lone expense defaults to the receipts archive that Save actually files
 * to today. Either default is just a starting point -- the operator's own
 * dropdown choice always wins once they've touched it.
 * @param {number} itemCount
 */
export function defaultArchiveKind(itemCount) {
  return itemCount > 1 ? ARCHIVE_KIND.SCANNED_DOCUMENT : ARCHIVE_KIND.RECEIPT;
}

/**
 * Fields -> the exact JSON shape POST /api/manual-receipt-entry-archive-preview
 * expects. Returns null when the three required inputs (merchant, date,
 * amount) aren't all present yet -- the caller should skip the request
 * rather than send a preview payload that can only come back invalid.
 * @param {ManualEntryFields} fields
 * @param {IntakeRef} intakeRef
 * @param {string} archiveKind
 * @param {string} [customArchiveRoot] required when archiveKind === "other"
 */
export function buildArchivePreviewPayload(
  fields,
  intakeRef,
  archiveKind,
  customArchiveRoot,
) {
  const amount = Number(fields.totalAmount);
  if (
    !fields.merchantName.trim() ||
    !ISO_DATE_RE.test(fields.transactionDate || "")
  ) {
    return null;
  }
  if (!Number.isFinite(amount) || amount <= 0) return null;
  if (archiveKind === ARCHIVE_KIND.OTHER && !(customArchiveRoot || "").trim())
    return null;
  return {
    image_path: intakeRef.imagePath,
    merchant_name: fields.merchantName.trim(),
    transaction_date: fields.transactionDate,
    total_amount: amount,
    archive_kind: archiveKind === ARCHIVE_KIND.OTHER ? "receipt" : archiveKind,
    ...(archiveKind === ARCHIVE_KIND.OTHER
      ? { custom_archive_root: customArchiveRoot.trim() }
      : {}),
  };
}

/**
 * Boundary check for POST /api/manual-receipt-entry-archive-preview's
 * response.
 * @param {unknown} json
 */
export function readArchivePreviewResponse(json) {
  const blank = {
    ok: false,
    path: null,
    isRealDestination: false,
    error: "malformed response",
  };
  if (typeof json !== "object" || json === null) return blank;
  if (json.ok !== true) {
    return {
      ...blank,
      error: typeof json.error === "string" ? json.error : "preview failed",
    };
  }
  return {
    ok: true,
    path: typeof json.path === "string" ? json.path : null,
    isRealDestination: json.is_real_destination === true,
    error: null,
  };
}
