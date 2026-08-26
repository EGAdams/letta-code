import { describe, expect, test } from "bun:test";
import {
  ARCHIVE_KIND,
  blankManualEntryFields,
  buildArchivePreviewPayload,
  buildPreviewPayload,
  buildSubmitPayload,
  defaultArchiveKind,
  PREVIEW_ENGINE,
  readArchivePreviewResponse,
  readCategoriesResponse,
  readPrefillResponse,
  readStoredFindings,
  readSubmitResponse,
  readVendorCandidates,
  readVendorKeysResponse,
  readVendorRememberedResponse,
  validateManualEntry,
} from "../abstract/manual-entry.interface.js";

const validFields = {
  merchantName: "Kroger",
  transactionDate: "2026-08-15",
  totalAmount: "12.34",
  categoryName: "",
};

describe("validateManualEntry", () => {
  test("accepts a fully filled-in, valid form", () => {
    expect(validateManualEntry(validFields)).toEqual({
      valid: true,
      errors: {},
    });
  });

  test("learning a new vendor requires both a key and category", () => {
    const missingCategory = validateManualEntry({
      ...validFields,
      knownVendorKey: "__new__",
      newVendorKey: "cracker_barrel",
    });
    expect(missingCategory.errors.categoryName).toContain("category");

    const validNewVendor = validateManualEntry({
      ...validFields,
      knownVendorKey: "__new__",
      newVendorKey: "cracker_barrel",
      categoryName: "Food",
    });
    expect(validNewVendor.valid).toBe(true);
  });

  test("rejects an empty merchant name", () => {
    const result = validateManualEntry({ ...validFields, merchantName: "   " });
    expect(result.valid).toBe(false);
    expect(result.errors.merchantName).toBeTruthy();
  });

  test("rejects a non-ISO date", () => {
    const result = validateManualEntry({
      ...validFields,
      transactionDate: "08/15/2026",
    });
    expect(result.valid).toBe(false);
    expect(result.errors.transactionDate).toBeTruthy();
  });

  test.each([["0"], ["-5"], ["not-a-number"], [""]])(
    "rejects a non-positive or non-numeric amount %p",
    (bad) => {
      const result = validateManualEntry({ ...validFields, totalAmount: bad });
      expect(result.valid).toBe(false);
      expect(result.errors.totalAmount).toBeTruthy();
    },
  );

  test("blank category name is valid (means 'unresolved')", () => {
    expect(
      validateManualEntry({ ...validFields, categoryName: "" }).valid,
    ).toBe(true);
  });

  test("any non-blank category name passes client-side (server resolves it)", () => {
    expect(
      validateManualEntry({ ...validFields, categoryName: "Food" }).valid,
    ).toBe(true);
  });
});

describe("buildSubmitPayload", () => {
  test("coerces amount to a real JSON number, never a string", () => {
    const payload = buildSubmitPayload(validFields, {
      imagePath: "/staged/scan.jpg",
      conversationId: "conv-1",
    });
    expect(payload).toEqual({
      image_path: "/staged/scan.jpg",
      conversation_id: "conv-1",
      merchant_name: "Kroger",
      transaction_date: "2026-08-15",
      total_amount: 12.34,
      category_name: "",
    });
    expect(typeof payload.total_amount).toBe("number");
  });

  test("a filled-in category name passes through trimmed", () => {
    const payload = buildSubmitPayload(
      { ...validFields, categoryName: "  Food  " },
      { imagePath: "/x.jpg", conversationId: "c" },
    );
    expect(payload.category_name).toBe("Food");
  });
});

describe("buildPreviewPayload", () => {
  test("defaults to the zero-token local engine", () => {
    expect(
      buildPreviewPayload({ imagePath: "/x.jpg", conversationId: "c" }),
    ).toEqual({
      image_path: "/x.jpg",
      engine: "local",
    });
  });

  test("carries an explicit engine through", () => {
    expect(
      buildPreviewPayload({ imagePath: "/x.jpg" }, PREVIEW_ENGINE.GEMINI_ONLY),
    ).toEqual({
      image_path: "/x.jpg",
      engine: "gemini-only",
    });
  });

  test("carries the haiku-only engine through", () => {
    expect(
      buildPreviewPayload({ imagePath: "/x.jpg" }, PREVIEW_ENGINE.HAIKU_ONLY),
    ).toEqual({
      image_path: "/x.jpg",
      engine: "haiku-only",
    });
  });
});

describe("readPrefillResponse", () => {
  test("reads a full successful preview", () => {
    expect(
      readPrefillResponse({
        ok: true,
        merchant_name: "Kroger",
        transaction_date: "2026-08-15",
        total_amount: 12.34,
      }),
    ).toEqual({
      ok: true,
      merchantName: "Kroger",
      transactionDate: "2026-08-15",
      totalAmount: 12.34,
      vendorAmbiguous: false,
      vendorCandidates: [],
      vendorKey: null,
      categoryName: null,
      possibleStatement: false,
      error: null,
    });
  });

  test("reads a matched vendor_key + category alongside the OCR fields", () => {
    const result = readPrefillResponse({
      ok: true,
      merchant_name: "Samaritans Purse",
      vendor_key: "samaritans_purse",
      category_name: "Samaritans Purse",
    });
    expect(result.vendorKey).toBe("samaritans_purse");
    expect(result.categoryName).toBe("Samaritans Purse");
  });

  test("partial OCR results still surface whatever was found", () => {
    const result = readPrefillResponse({ ok: true, merchant_name: "Kroger" });
    expect(result.merchantName).toBe("Kroger");
    expect(result.transactionDate).toBeNull();
    expect(result.totalAmount).toBeNull();
    expect(result.vendorKey).toBeNull();
    expect(result.categoryName).toBeNull();
  });

  test.each([[null], [undefined], ["a string"], [42], [[]]])(
    "malformed response %p never throws, returns a blank/failed prefill",
    (bad) => {
      expect(() => readPrefillResponse(bad)).not.toThrow();
      const result = readPrefillResponse(bad);
      expect(result.ok).toBe(false);
    },
  );

  test("a field with the wrong runtime type is dropped, not trusted", () => {
    // total_amount arriving as a string would previously have been trusted
    // and handed straight into the strict-typed submit payload.
    const result = readPrefillResponse({ ok: true, total_amount: "12.34" });
    expect(result.totalAmount).toBeNull();
  });
});

describe("readSubmitResponse", () => {
  test("reads a successful save", () => {
    expect(
      readSubmitResponse({ ok: true, expense_id: 9001, duplicate: false }),
    ).toEqual({
      ok: true,
      expenseId: 9001,
      duplicate: false,
      record: null,
      vendorRemembered: null,
    });
  });

  test("reads a successful save that remembered a new vendor", () => {
    expect(
      readSubmitResponse({
        ok: true,
        expense_id: 9001,
        duplicate: false,
        vendor_remembered: { remembered: true, vendor_key: "samaritans_purse" },
      }),
    ).toEqual({
      ok: true,
      expenseId: 9001,
      duplicate: false,
      record: null,
      vendorRemembered: { remembered: true, vendorKey: "samaritans_purse" },
    });
  });

  test("reads a failed save's error message", () => {
    expect(
      readSubmitResponse({ ok: false, error: "merchant required" }),
    ).toEqual({
      ok: false,
      error: "merchant required",
    });
  });

  test("malformed response never throws", () => {
    expect(() => readSubmitResponse(null)).not.toThrow();
    expect(readSubmitResponse(null).ok).toBe(false);
  });
});

describe("readVendorKeysResponse", () => {
  test("reads vendor_key + category_name pairs", () => {
    expect(
      readVendorKeysResponse({
        ok: true,
        vendor_keys: [
          { vendor_key: "kroger", category_id: 5, category_name: "Food" },
          { vendor_key: "walgreens", category_id: null, category_name: null },
        ],
      }),
    ).toEqual([
      { vendorKey: "kroger", categoryName: "Food" },
      { vendorKey: "walgreens", categoryName: null },
    ]);
  });

  test("drops malformed entries instead of crashing the dropdown", () => {
    expect(
      readVendorKeysResponse({
        ok: true,
        vendor_keys: [{ vendor_key: "" }, null, 42],
      }),
    ).toEqual([]);
  });

  test.each([
    [null],
    [{ ok: false }],
    [{ ok: true, vendor_keys: "not-an-array" }],
  ])("malformed response %p never throws, returns an empty list", (bad) => {
    expect(() => readVendorKeysResponse(bad)).not.toThrow();
    expect(readVendorKeysResponse(bad)).toEqual([]);
  });
});

describe("readVendorRememberedResponse", () => {
  test("reads a remembered vendor", () => {
    expect(
      readVendorRememberedResponse({
        remembered: true,
        vendor_key: "samaritans_purse",
      }),
    ).toEqual({ remembered: true, vendorKey: "samaritans_purse" });
  });

  test("reads a not-remembered result (already known)", () => {
    expect(
      readVendorRememberedResponse({
        remembered: false,
        vendor_key: "samaritans_purse",
        reason: "vendor_key already known",
      }),
    ).toEqual({ remembered: false, vendorKey: "samaritans_purse" });
  });

  test.each([[null], [undefined], ["not-an-object"]])(
    "malformed input %p returns null instead of throwing",
    (bad) => {
      expect(() => readVendorRememberedResponse(bad)).not.toThrow();
      expect(readVendorRememberedResponse(bad)).toBeNull();
    },
  );
});

describe("readCategoriesResponse", () => {
  test("reads a plain list of names", () => {
    expect(
      readCategoriesResponse({
        ok: true,
        categories: ["Food", "Uncategorized"],
      }),
    ).toEqual(["Food", "Uncategorized"]);
  });

  test("drops non-string entries", () => {
    expect(
      readCategoriesResponse({ ok: true, categories: ["Food", 42, null] }),
    ).toEqual(["Food"]);
  });

  test("malformed response never throws, returns an empty list", () => {
    expect(() => readCategoriesResponse(null)).not.toThrow();
    expect(readCategoriesResponse(null)).toEqual([]);
  });
});

describe("blankManualEntryFields", () => {
  test("every field starts empty", () => {
    expect(blankManualEntryFields()).toEqual({
      merchantName: "",
      transactionDate: "",
      totalAmount: "",
      categoryName: "",
      knownVendorKey: "",
      newVendorKey: "",
      expenseId: null,
    });
  });

  test("returns a fresh object each call (no shared mutable state)", () => {
    const a = blankManualEntryFields();
    const b = blankManualEntryFields();
    a.merchantName = "Kroger";
    expect(b.merchantName).toBe("");
  });
});

describe("readStoredFindings", () => {
  test("parses the server's JSON findings into item fields", () => {
    const raw = JSON.stringify([
      {
        merchant_name: "Kum & Go",
        transaction_date: "2025-06-01",
        total_amount: "12.34",
        category_name: "Travel & Vehicle",
        known_vendor_key: "kum_go",
        expense_id: 1391,
      },
      {
        merchant_name: "Meijer",
        transaction_date: "2025-06-02",
        total_amount: "45",
        category_name: "",
      },
    ]);
    expect(readStoredFindings(raw)).toEqual([
      {
        merchantName: "Kum & Go",
        transactionDate: "2025-06-01",
        totalAmount: "12.34",
        categoryName: "Travel & Vehicle",
        knownVendorKey: "kum_go",
        newVendorKey: "",
        expenseId: 1391,
      },
      {
        merchantName: "Meijer",
        transactionDate: "2025-06-02",
        totalAmount: "45",
        categoryName: "",
        knownVendorKey: "",
        newVendorKey: "",
        expenseId: null,
      },
    ]);
  });

  test("ignores a malformed or non-positive expense_id instead of trusting it", () => {
    const raw = JSON.stringify([
      {
        merchant_name: "Kum & Go",
        transaction_date: "2025-06-01",
        total_amount: "12.34",
        expense_id: -3,
      },
      {
        merchant_name: "Meijer",
        transaction_date: "2025-06-02",
        total_amount: "45",
        expense_id: "1391",
      },
    ]);
    const [first, second] = readStoredFindings(raw);
    expect(first.expenseId).toBeNull();
    expect(second.expenseId).toBeNull();
  });

  test("drops a row missing merchant or amount instead of showing a broken item", () => {
    const raw = JSON.stringify([
      { merchant_name: "", transaction_date: "2025-06-01", total_amount: "1" },
      { merchant_name: "Meijer", transaction_date: "2025-06-02" },
    ]);
    expect(readStoredFindings(raw)).toEqual([]);
  });

  test("fails to an empty list, never throws, for missing/malformed input", () => {
    expect(readStoredFindings(undefined)).toEqual([]);
    expect(readStoredFindings("")).toEqual([]);
    expect(readStoredFindings("not json")).toEqual([]);
    expect(readStoredFindings('{"not":"an array"}')).toEqual([]);
  });
});

describe("defaultArchiveKind", () => {
  test("a single expense defaults to the real receipts archive", () => {
    expect(defaultArchiveKind(1)).toBe(ARCHIVE_KIND.RECEIPT);
  });

  test("more than one expense on the document defaults to scanned documents", () => {
    expect(defaultArchiveKind(2)).toBe(ARCHIVE_KIND.SCANNED_DOCUMENT);
    expect(defaultArchiveKind(5)).toBe(ARCHIVE_KIND.SCANNED_DOCUMENT);
  });
});

describe("buildArchivePreviewPayload", () => {
  const fields = {
    merchantName: "Kroger",
    transactionDate: "2026-08-15",
    totalAmount: "12.34",
    categoryName: "",
  };
  const intakeRef = { imagePath: "/staged/scan.jpg", conversationId: "c" };

  test("builds the receipt-kind payload", () => {
    expect(
      buildArchivePreviewPayload(fields, intakeRef, ARCHIVE_KIND.RECEIPT),
    ).toEqual({
      image_path: "/staged/scan.jpg",
      merchant_name: "Kroger",
      transaction_date: "2026-08-15",
      total_amount: 12.34,
      archive_kind: "receipt",
    });
  });

  test("'other' sends archive_kind=receipt plus a custom_archive_root", () => {
    const payload = buildArchivePreviewPayload(
      fields,
      intakeRef,
      ARCHIVE_KIND.OTHER,
      "/some/custom/place",
    );
    expect(payload.archive_kind).toBe("receipt");
    expect(payload.custom_archive_root).toBe("/some/custom/place");
  });

  test("returns null when merchant/date/amount aren't all present yet", () => {
    expect(
      buildArchivePreviewPayload(
        { ...fields, merchantName: "" },
        intakeRef,
        ARCHIVE_KIND.RECEIPT,
      ),
    ).toBeNull();
    expect(
      buildArchivePreviewPayload(
        { ...fields, transactionDate: "" },
        intakeRef,
        ARCHIVE_KIND.RECEIPT,
      ),
    ).toBeNull();
    expect(
      buildArchivePreviewPayload(
        { ...fields, totalAmount: "0" },
        intakeRef,
        ARCHIVE_KIND.RECEIPT,
      ),
    ).toBeNull();
  });

  test("returns null for 'other' with no custom root typed yet", () => {
    expect(
      buildArchivePreviewPayload(fields, intakeRef, ARCHIVE_KIND.OTHER, ""),
    ).toBeNull();
    expect(
      buildArchivePreviewPayload(fields, intakeRef, ARCHIVE_KIND.OTHER),
    ).toBeNull();
  });
});

describe("readArchivePreviewResponse", () => {
  test("reads a real-destination receipt path", () => {
    expect(
      readArchivePreviewResponse({
        ok: true,
        path: "/a/b/c.jpg",
        is_real_destination: true,
      }),
    ).toEqual({
      ok: true,
      path: "/a/b/c.jpg",
      isRealDestination: true,
      error: null,
    });
  });

  test("reads a preview-only path", () => {
    const result = readArchivePreviewResponse({
      ok: true,
      path: "/a/b/c.jpg",
      is_real_destination: false,
    });
    expect(result.isRealDestination).toBe(false);
  });

  test("reads a failed preview's error message", () => {
    expect(
      readArchivePreviewResponse({ ok: false, error: "bad date" }),
    ).toEqual({
      ok: false,
      path: null,
      isRealDestination: false,
      error: "bad date",
    });
  });

  test.each([[null], [undefined], ["x"], [42]])(
    "malformed response %p never throws",
    (bad) => {
      expect(() => readArchivePreviewResponse(bad)).not.toThrow();
      expect(readArchivePreviewResponse(bad).ok).toBe(false);
    },
  );
});

describe("readVendorCandidates / ambiguous prefill", () => {
  test("reads the candidate list a DTE-style ambiguous prefill carries", () => {
    const prefill = readPrefillResponse({
      ok: true,
      merchant_name: "DTE Energy",
      vendor_key: null,
      category_name: null,
      vendor_ambiguous: true,
      vendor_candidates: [
        { vendor_key: "dte_energy_0544", category_name: "Housing Gas Bill" },
        {
          vendor_key: "dte_energy_0020",
          category_name: "Church Electric Bill",
        },
      ],
    });
    expect(prefill.vendorAmbiguous).toBe(true);
    expect(prefill.vendorKey).toBe(null);
    expect(prefill.categoryName).toBe(null);
    expect(prefill.vendorCandidates).toEqual([
      { vendorKey: "dte_energy_0544", categoryName: "Housing Gas Bill" },
      { vendorKey: "dte_energy_0020", categoryName: "Church Electric Bill" },
    ]);
  });

  test("an ordinary prefill reports no ambiguity and no candidates", () => {
    const prefill = readPrefillResponse({
      ok: true,
      merchant_name: "Kroger",
      vendor_key: "kroger",
      category_name: "Food",
    });
    expect(prefill.vendorAmbiguous).toBe(false);
    expect(prefill.vendorCandidates).toEqual([]);
  });

  test.each([
    ["a non-array", "nope"],
    ["null", null],
    ["undefined", undefined],
  ])("degrades safely when vendor_candidates is %s", (_label, value) => {
    expect(readVendorCandidates(value)).toEqual([]);
  });

  test("drops entries with no usable vendor key rather than showing blanks", () => {
    expect(
      readVendorCandidates([
        { vendor_key: "dte_energy_0544", category_name: "Housing Gas Bill" },
        { vendor_key: "" },
        { category_name: "orphan" },
        null,
        "nope",
      ]),
    ).toEqual([
      { vendorKey: "dte_energy_0544", categoryName: "Housing Gas Bill" },
    ]);
  });

  test("a candidate with no category still reads, with a null category", () => {
    expect(readVendorCandidates([{ vendor_key: "dte_energy_0020" }])).toEqual([
      { vendorKey: "dte_energy_0020", categoryName: null },
    ]);
  });
});
