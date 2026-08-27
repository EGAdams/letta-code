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
 * @property {string} [knownVendorKey] a REUSABLE vendor_category.yaml match
 *   to preselect the "known vendor" dropdown with, or "" -- optional so a
 *   plain hand-typed item (no known vendor yet) doesn't need to carry the
 *   field. Distinct from merchantName: this is never the per-transaction
 *   filing key a stored expense always carries (see StoredFindingRow below),
 *   only a name the vendor dropdown can already select.
 * @property {string} [newVendorKey] human-approved reusable key when this
 *   description is not known yet; never substituted into merchantName
 * @property {?number} [expenseId] the DB id of an already-stored row this
 *   item reflects, or null/undefined for a plain not-yet-saved item. Set
 *   ONLY by readStoredFindings (a seeded finding always already exists in
 *   the database -- see StoredFindingRow below); a hand-typed or Mazda-Fill
 *   item never carries one. buildSaveRequest below is what this actually
 *   changes: present, it builds an UPDATE through /api/expense-edit instead
 *   of an INSERT through /api/manual-receipt-entry.
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
 * @property {?string} vendorKey     an exact vendor_category.yaml match for
 *   merchantName, if any -- lets the form preselect the "known vendor"
 *   dropdown instead of leaving it on the free-text merchant name alone
 * @property {?string} categoryName  the matched vendor's (or a fuzzy
 *   category-only match's) category, prefilled even when vendorKey is null
 * @property {boolean} possibleStatement  the zero-cost local-OCR pass's raw
 *   text reads like a statement's transaction table (see
 *   finance/statement_heuristic.py), not one receipt -- the form uses this to
 *   nudge the operator toward Break Up Document instead of silently filling
 *   one field and hiding the rest of the page
 *
 * @typedef {Object} VendorOption
 * @property {string} vendorKey
 * @property {?string} categoryName  the vendor's known category, if any -- lets
 *   picking a vendor also prefill the category dropdown
 *
 * @typedef {Object} VendorRememberedResult
 * @property {boolean} remembered  true if a brand-new vendor_key was just
 *   written to vendor_category.yaml
 * @property {?string} vendorKey   the slug it was (or would be) stored under
 *
 * @typedef {Object} StoredFindingRow  one entry of the mount point's raw
 *   data-mazda-findings JSON -- the wire shape finance/intake_report_model.py's
 *   StoredFinding.model_dump() produces, before readStoredFindings turns it
 *   into a ManualEntryFields
 * @property {string} merchant_name
 * @property {string} transaction_date  ISO yyyy-mm-dd
 * @property {number} total_amount      always positive; sign already
 *   normalised server-side
 * @property {string} category_name
 * @property {string} [known_vendor_key]  a REUSABLE vendor this row's
 *   merchant resolved to, if any -- see finance.intake_report_model's
 *   StoredFinding.known_vendor_key for why this is never the row's own
 *   per-transaction filing key
 * @property {string} [new_vendor_key] server-generated initial key guess for
 *   an unknown description
 * @property {?number} [expense_id]  the DB id of the already-stored row
 *   this finding reflects -- see ManualEntryFields.expenseId
 */

import { ISO_DATE_RE, isNonEmptyString } from "./field-validation.js";

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
  if (
    fields.knownVendorKey === "__new__" &&
    !isNonEmptyString(fields.newVendorKey)
  ) {
    errors.newVendorKey = "New Vendor Key is required for an unknown vendor.";
  }
  if (
    fields.knownVendorKey === "__new__" &&
    !isNonEmptyString(fields.categoryName)
  ) {
    errors.categoryName = "Choose a category before learning a new vendor.";
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

//: The three engines POST /api/manual-receipt-entry-preview accepts -- the
//: server's own PREVIEW_ENGINES allow-list is the enforcement point (never
//: trust the client alone), this just keeps a caller from typing a stray
//: engine name that would only ever bounce as a 400.
export const PREVIEW_ENGINE = Object.freeze({
  LOCAL: "local",
  GEMINI_ONLY: "gemini-only",
  HAIKU_ONLY: "haiku-only",
});

/**
 * @param {IntakeRef} intakeRef
 * @param {string} [engine] one of PREVIEW_ENGINE's values; defaults to the
 *   zero-token local OCR pass ("Prefill from OCR" button's engine)
 */
export function buildPreviewPayload(intakeRef, engine = PREVIEW_ENGINE.LOCAL) {
  return { image_path: intakeRef.imagePath, engine };
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
    vendorKey: null,
    categoryName: null,
    possibleStatement: false,
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
  const vendorKey =
    typeof json.vendor_key === "string" ? json.vendor_key : null;
  const categoryName =
    typeof json.category_name === "string" ? json.category_name : null;
  return {
    ok: json.ok === true,
    merchantName,
    transactionDate,
    totalAmount,
    vendorKey,
    categoryName,
    vendorAmbiguous: json.vendor_ambiguous === true,
    vendorCandidates: readVendorCandidates(json.vendor_candidates),
    possibleStatement: json.possible_statement === true,
    error: typeof json.error === "string" ? json.error : null,
  };
}

/**
 * Boundary check for the `vendor_candidates` list a prefill carries when the
 * merchant name matched several stored vendors that disagree about the
 * category (e.g. "DTE Energy" -> the house's account or the church's). The
 * server prefills nothing in that case; these are what the operator picks
 * from instead. A malformed entry is dropped rather than shown as a blank
 * choice — an unlabelled option in this list would be worse than no option.
 * @param {unknown} value
 * @returns {VendorOption[]}
 */
export function readVendorCandidates(value) {
  if (!Array.isArray(value)) return [];
  return value
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
 * Boundary check for the nested vendor_remembered object POST
 * /api/manual-receipt-entry's response carries on success. Malformed or
 * absent input is a normal "nothing to report" case (an existing vendor
 * was picked, so nothing new needed remembering) -- never an error.
 * @param {unknown} json
 * @returns {?VendorRememberedResult}
 */
export function readVendorRememberedResponse(json) {
  if (typeof json !== "object" || json === null) return null;
  return {
    remembered: json.remembered === true,
    vendorKey: typeof json.vendor_key === "string" ? json.vendor_key : null,
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
      record:
        typeof json.record === "object" && json.record !== null
          ? {
              id: Number(json.record.id),
              transactionDate:
                typeof json.record.transaction_date === "string"
                  ? json.record.transaction_date
                  : "",
              totalAmount: Number(json.record.total_amount),
              description:
                typeof json.record.description === "string"
                  ? json.record.description
                  : "",
              idLight:
                typeof json.record.id_light === "string"
                  ? json.record.id_light
                  : "",
              categoryName:
                typeof json.record.category_name === "string"
                  ? json.record.category_name
                  : "",
            }
          : null,
      vendorRemembered: readVendorRememberedResponse(json.vendor_remembered),
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
 *
 * The endpoint now serves full {name, cls, bg, fg} rows (the report-page
 * picker needs the styling fields), but this form and ExpenseEditPanel only
 * ever wanted the plain names for a <select> -- so an entry is read either
 * way: a bare string, or an object with a `.name` string.
 * @param {unknown} json
 * @returns {string[]}
 */
export function readCategoriesResponse(json) {
  if (typeof json !== "object" || json === null || json.ok !== true) return [];
  const entries = Array.isArray(json.categories) ? json.categories : [];
  return entries
    .map((entry) =>
      typeof entry === "string"
        ? entry
        : entry && typeof entry.name === "string"
          ? entry.name
          : null,
    )
    .filter((name) => typeof name === "string" && name);
}

/**
 * Amount display formatting: always two decimal places (e.g. "12" or "12.5"
 * -> "12.00" / "12.50"), so the field reads as money instead of a bare
 * number. Anything that isn't a finite number yet (blank, "-", mid-typing)
 * is returned unchanged -- formatting only applies once there's a real
 * number to format, so an operator isn't fought while typing.
 * @param {string} value
 * @returns {string}
 */
export function formatAmountForDisplay(value) {
  const amount = Number(value);
  if (value === "" || !Number.isFinite(amount)) return value;
  return amount.toFixed(2);
}

/** A single blank line item for the multi-expense-per-document form. */
export function blankManualEntryFields() {
  return {
    merchantName: "",
    transactionDate: "",
    totalAmount: "",
    categoryName: "",
    knownVendorKey: "",
    newVendorKey: "",
    expenseId: null,
  };
}

/**
 * Boundary check for the mount point's data-mazda-findings attribute — the
 * server's own record of what Mazda's STEP 8 callback already read/stored for
 * this document (see server.py's presentation_rows_list), seeding the form
 * with her findings instead of a blank item on an automatic scan. Malformed
 * JSON, a non-array, or a row missing merchant/amount is dropped rather than
 * shown as a broken item — same "fail to blank, never fail to crash" rule as
 * readPrefillResponse.
 * @param {?string} raw the raw dataset value -- JSON text for a
 *   StoredFindingRow[], or null/undefined
 * @returns {ManualEntryFields[]}
 */
export function readStoredFindings(raw) {
  if (typeof raw !== "string" || !raw) return [];
  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return [];
  }
  if (!Array.isArray(parsed)) return [];
  return parsed
    .map((row) => ({
      merchantName:
        typeof row?.merchant_name === "string" ? row.merchant_name : "",
      transactionDate:
        typeof row?.transaction_date === "string" ? row.transaction_date : "",
      totalAmount:
        typeof row?.total_amount === "string" ||
        typeof row?.total_amount === "number"
          ? String(row.total_amount)
          : "",
      categoryName:
        typeof row?.category_name === "string" ? row.category_name : "",
      knownVendorKey:
        typeof row?.known_vendor_key === "string" ? row.known_vendor_key : "",
      newVendorKey:
        typeof row?.new_vendor_key === "string" ? row.new_vendor_key : "",
      expenseId:
        Number.isInteger(row?.expense_id) && row.expense_id > 0
          ? row.expense_id
          : null,
    }))
    .filter((item) => item.merchantName && item.totalAmount);
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
