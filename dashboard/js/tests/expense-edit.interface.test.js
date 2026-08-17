import { describe, expect, test } from "bun:test";
import {
  blankSearchCriteria,
  buildEditPayload,
  buildSearchPayload,
  describeEditResult,
  formatRecordLabel,
  readEditResponse,
  readExpenseRecord,
  readSearchResponse,
  recordToFields,
  validateSearchCriteria,
} from "../abstract/expense-edit.interface.js";

function criteria(overrides = {}) {
  return { ...blankSearchCriteria(), ...overrides };
}

const RECORD_JSON = {
  id: 501,
  transaction_date: "2026-08-15",
  total_amount: 12.34,
  description: "Kroger",
  vendor_key: "kroger_08_15_26_12_34",
  category_name: "Office",
};

describe("validateSearchCriteria", () => {
  test("an empty search is a mistake, not a request for everything", () => {
    const result = validateSearchCriteria(criteria());
    expect(result.valid).toBe(false);
    expect(result.errors.merchant).toContain("Enter a merchant");
  });

  test("any one criterion is enough", () => {
    expect(validateSearchCriteria(criteria({ merchant: "Kroger" })).valid).toBe(
      true,
    );
    expect(validateSearchCriteria(criteria({ amount: "12.34" })).valid).toBe(
      true,
    );
    expect(
      validateSearchCriteria(criteria({ dateFrom: "2026-08-01" })).valid,
    ).toBe(true);
  });

  test("a reversed date range is rejected", () => {
    const result = validateSearchCriteria(
      criteria({ dateFrom: "2026-08-20", dateTo: "2026-08-01" }),
    );
    expect(result.valid).toBe(false);
    expect(result.errors.dateTo).toContain("must not be after");
  });

  test("a non-ISO date is rejected before the round trip", () => {
    const result = validateSearchCriteria(criteria({ dateFrom: "08/20/2026" }));
    expect(result.valid).toBe(false);
    expect(result.errors.dateFrom).toBeTruthy();
  });

  test("a non-positive amount is rejected", () => {
    expect(validateSearchCriteria(criteria({ amount: "0" })).valid).toBe(false);
    expect(validateSearchCriteria(criteria({ amount: "-5" })).valid).toBe(
      false,
    );
    expect(validateSearchCriteria(criteria({ amount: "abc" })).valid).toBe(
      false,
    );
  });

  test("survives a criteria object missing fields entirely", () => {
    expect(validateSearchCriteria({}).valid).toBe(false);
    expect(validateSearchCriteria(null).valid).toBe(false);
  });
});

describe("buildSearchPayload", () => {
  test("sends the amount as a JSON number, not a string", () => {
    const payload = buildSearchPayload(criteria({ amount: "12.34" }));
    expect(payload.amount).toBe(12.34);
  });

  test("sends null for an omitted amount", () => {
    expect(buildSearchPayload(criteria({ merchant: "Kroger" })).amount).toBe(
      null,
    );
  });

  test("trims the merchant and includes an explicit limit only when given", () => {
    expect(
      buildSearchPayload(criteria({ merchant: "  Kroger " })).merchant,
    ).toBe("Kroger");
    expect(buildSearchPayload(criteria({ merchant: "Kroger" })).limit).toBe(
      undefined,
    );
    expect(buildSearchPayload(criteria({ merchant: "Kroger" }), 5).limit).toBe(
      5,
    );
  });
});

describe("readExpenseRecord", () => {
  test("maps the server's snake_case into the form's shape", () => {
    expect(readExpenseRecord(RECORD_JSON)).toEqual({
      id: 501,
      transactionDate: "2026-08-15",
      totalAmount: 12.34,
      description: "Kroger",
      vendorKey: "kroger_08_15_26_12_34",
      categoryName: "Office",
    });
  });

  test("a negative amount reads as positive", () => {
    expect(
      readExpenseRecord({ ...RECORD_JSON, total_amount: -12.34 }).totalAmount,
    ).toBe(12.34);
  });

  test.each([
    ["a missing id", { ...RECORD_JSON, id: undefined }],
    ["a string id", { ...RECORD_JSON, id: "501" }],
    ["a string amount", { ...RECORD_JSON, total_amount: "12.34" }],
    ["a non-ISO date", { ...RECORD_JSON, transaction_date: "08/15/2026" }],
    ["a non-object", "nope"],
    ["null", null],
    ["an array", []],
  ])("rejects %s", (_label, raw) => {
    expect(readExpenseRecord(raw)).toBe(null);
  });

  test("missing optional text fields become empty strings, not undefined", () => {
    const record = readExpenseRecord({
      id: 1,
      transaction_date: "2026-08-15",
      total_amount: 1,
    });
    expect(record.description).toBe("");
    expect(record.vendorKey).toBe("");
    expect(record.categoryName).toBe("");
  });
});

describe("readSearchResponse", () => {
  test("reads a successful search", () => {
    const result = readSearchResponse({ ok: true, records: [RECORD_JSON] });
    expect(result.ok).toBe(true);
    expect(result.records).toHaveLength(1);
  });

  test("drops a malformed row instead of poisoning the whole list", () => {
    const result = readSearchResponse({
      ok: true,
      records: [RECORD_JSON, { id: "bad" }, null],
    });
    expect(result.records.map((r) => r.id)).toEqual([501]);
  });

  test.each([
    ["a malformed body", "not json"],
    ["null", null],
    ["ok:false", { ok: false, error: "boom" }],
    ["records that are not an array", { ok: true, records: "nope" }],
  ])("degrades safely on %s", (_label, json) => {
    const result = readSearchResponse(json);
    expect(result.records).toEqual([]);
  });

  test("carries the server's error message through", () => {
    expect(readSearchResponse({ ok: false, error: "boom" }).error).toBe("boom");
  });
});

describe("recordToFields / buildEditPayload", () => {
  test("a record round-trips into the shared field shape", () => {
    expect(recordToFields(readExpenseRecord(RECORD_JSON))).toEqual({
      merchantName: "Kroger",
      transactionDate: "2026-08-15",
      totalAmount: "12.34",
      categoryName: "Office",
    });
  });

  test("builds the payload the server's ExpenseEdit expects", () => {
    const fields = recordToFields(readExpenseRecord(RECORD_JSON));
    expect(buildEditPayload(501, fields)).toEqual({
      expense_id: 501,
      merchant_name: "Kroger",
      transaction_date: "2026-08-15",
      total_amount: 12.34,
      category_name: "Office",
    });
  });

  test("refuses to build a payload for fields a fresh entry would reject", () => {
    const fields = recordToFields(readExpenseRecord(RECORD_JSON));
    expect(buildEditPayload(501, { ...fields, merchantName: "  " })).toBe(null);
    expect(
      buildEditPayload(501, { ...fields, transactionDate: "08/15/2026" }),
    ).toBe(null);
    expect(buildEditPayload(501, { ...fields, totalAmount: "0" })).toBe(null);
  });

  test.each([0, -1, 1.5, "501", null])(
    "refuses a bad expense id (%p)",
    (badId) => {
      const fields = recordToFields(readExpenseRecord(RECORD_JSON));
      expect(buildEditPayload(badId, fields)).toBe(null);
    },
  );
});

describe("readEditResponse / describeEditResult", () => {
  test("reads a successful edit with its warnings", () => {
    const result = readEditResponse({
      ok: true,
      record: RECORD_JSON,
      changed_fields: ["description", "amount"],
      warnings: ["vendor key is stale"],
    });
    expect(result.ok).toBe(true);
    expect(result.record.id).toBe(501);
    expect(result.changedFields).toEqual(["description", "amount"]);
    expect(result.warnings).toEqual(["vendor key is stale"]);
  });

  test("non-string entries are dropped from the string arrays", () => {
    const result = readEditResponse({
      ok: true,
      record: RECORD_JSON,
      changed_fields: ["amount", 7, null, ""],
      warnings: "not an array",
    });
    expect(result.changedFields).toEqual(["amount"]);
    expect(result.warnings).toEqual([]);
  });

  test.each([
    ["a malformed body", "nope"],
    ["null", null],
  ])("degrades safely on %s", (_label, json) => {
    expect(readEditResponse(json).ok).toBe(false);
  });

  test("an unchanged save is reported as a no-op, not as a write", () => {
    const message = describeEditResult({
      ok: true,
      record: readExpenseRecord(RECORD_JSON),
      changedFields: [],
      warnings: [],
      error: null,
    });
    expect(message).toContain("No changes");
  });

  test("a real change names the fields it wrote", () => {
    const message = describeEditResult({
      ok: true,
      record: readExpenseRecord(RECORD_JSON),
      changedFields: ["description", "amount"],
      warnings: [],
      error: null,
    });
    expect(message).toContain("expense 501");
    expect(message).toContain("description, amount");
  });

  test("a failure reports the server's error", () => {
    expect(
      describeEditResult({ ok: false, error: "no expense with id 9" }),
    ).toBe("no expense with id 9");
  });
});

describe("formatRecordLabel", () => {
  test("shows id, date, money-formatted amount, name, and category", () => {
    const label = formatRecordLabel(readExpenseRecord(RECORD_JSON));
    expect(label).toBe("#501 · 2026-08-15 · $12.34 · Kroger · Office");
  });

  test("falls back to the vendor key, then to a placeholder", () => {
    const noDescription = readExpenseRecord({
      ...RECORD_JSON,
      description: "",
    });
    expect(formatRecordLabel(noDescription)).toContain("kroger_08_15_26_12_34");
    const bare = readExpenseRecord({
      ...RECORD_JSON,
      description: "",
      vendor_key: "",
      category_name: "",
    });
    expect(formatRecordLabel(bare)).toContain("(no description)");
    expect(formatRecordLabel(bare)).toContain("Uncategorized");
  });
});
