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
  id_light: "kroger_08_15_26_12_34",
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
      idLight: "kroger_08_15_26_12_34",
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
    expect(record.idLight).toBe("");
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

  test("never displays a filing key as a vendor", () => {
    const noDescription = readExpenseRecord({
      ...RECORD_JSON,
      description: "",
    });
    expect(formatRecordLabel(noDescription)).toContain("(no description)");
    const bare = readExpenseRecord({
      ...RECORD_JSON,
      description: "",
      id_light: "",
      category_name: "",
    });
    expect(formatRecordLabel(bare)).toContain("(no description)");
    expect(formatRecordLabel(bare)).toContain("Uncategorized");
  });
});

// ===========================================================================
// Edge cases
// ===========================================================================

describe("numeric edge cases", () => {
  test.each([
    ["NaN", Number.NaN],
    ["Infinity", Number.POSITIVE_INFINITY],
    ["-Infinity", Number.NEGATIVE_INFINITY],
  ])("a %s amount is rejected, not rendered", (_label, amount) => {
    expect(readExpenseRecord({ ...RECORD_JSON, total_amount: amount })).toBe(
      null,
    );
  });

  test("an id of 0 is rejected — no expense has row id 0", () => {
    // 0 is finite, so only an explicit check keeps it out.
    const record = readExpenseRecord({ ...RECORD_JSON, id: 0 });
    expect(
      record === null || buildEditPayload(record.id, recordToFields(record)),
    ).toBeFalsy();
  });

  test("a zero amount record is read but cannot be saved", () => {
    const record = readExpenseRecord({ ...RECORD_JSON, total_amount: 0 });
    expect(record.totalAmount).toBe(0);
    expect(buildEditPayload(record.id, recordToFields(record))).toBe(null);
  });

  test("exponent notation in the amount box is accepted as the number it is", () => {
    expect(validateSearchCriteria(criteria({ amount: "1e2" })).valid).toBe(
      true,
    );
    expect(buildSearchPayload(criteria({ amount: "1e2" })).amount).toBe(100);
  });

  test("a whitespace-only amount is treated as absent, not as zero", () => {
    expect(
      validateSearchCriteria(criteria({ merchant: "K", amount: "  " })).valid,
    ).toBe(true);
    expect(
      buildSearchPayload(criteria({ merchant: "K", amount: "  " })).amount,
    ).toBe(null);
  });

  test("a very large amount survives the round trip", () => {
    const record = readExpenseRecord({
      ...RECORD_JSON,
      total_amount: 1234567.89,
    });
    expect(recordToFields(record).totalAmount).toBe("1234567.89");
    expect(buildEditPayload(501, recordToFields(record)).total_amount).toBe(
      1234567.89,
    );
  });

  test("more than two decimals are shown rounded to cents", () => {
    const record = readExpenseRecord({ ...RECORD_JSON, total_amount: 12.345 });
    expect(recordToFields(record).totalAmount).toBe("12.35");
  });
});

describe("date edge cases", () => {
  test.each([
    ["a well-formed but impossible day", "2026-02-30"],
    ["month 13", "2026-13-01"],
  ])("%s passes the shape check — the server is the authority", (_l, date) => {
    // The client regex checks shape only; ExpenseFieldRules rejects the value.
    expect(validateSearchCriteria(criteria({ dateFrom: date })).valid).toBe(
      true,
    );
  });

  test.each([
    ["unpadded", "2026-1-5"],
    ["no separators", "20260815"],
    ["with a time", "2026-08-15T00:00:00"],
  ])("a %s date fails the shape check", (_l, date) => {
    expect(validateSearchCriteria(criteria({ dateFrom: date })).valid).toBe(
      false,
    );
    expect(readExpenseRecord({ ...RECORD_JSON, transaction_date: date })).toBe(
      null,
    );
  });

  test("an equal from/to date is a valid single-day search", () => {
    expect(
      validateSearchCriteria(
        criteria({ dateFrom: "2026-08-15", dateTo: "2026-08-15" }),
      ).valid,
    ).toBe(true);
  });

  test("a reversed range is not reported twice as two separate errors", () => {
    const result = validateSearchCriteria(
      criteria({ dateFrom: "2026-08-20", dateTo: "2026-08-01" }),
    );
    expect(Object.keys(result.errors)).toEqual(["dateTo"]);
  });
});

describe("text edge cases", () => {
  test("a unicode merchant name is preserved, not stripped", () => {
    const payload = buildSearchPayload(
      criteria({ merchant: " Café Münster " }),
    );
    expect(payload.merchant).toBe("Café Münster");
  });

  test("LIKE metacharacters are passed through untouched for the server to escape", () => {
    // Escaping is the server's job (finance/expense_edit_repository.escape_like);
    // mangling them here would double-escape.
    expect(buildSearchPayload(criteria({ merchant: "50%" })).merchant).toBe(
      "50%",
    );
  });

  test("a record label survives a description containing the separator", () => {
    const record = readExpenseRecord({
      ...RECORD_JSON,
      description: "Kroger · Fuel · #12",
    });
    expect(formatRecordLabel(record)).toContain("Kroger · Fuel · #12");
    expect(formatRecordLabel(record).startsWith("#501 ·")).toBe(true);
  });

  test("a whitespace-only merchant in an edit is refused", () => {
    const fields = recordToFields(readExpenseRecord(RECORD_JSON));
    expect(buildEditPayload(501, { ...fields, merchantName: " \t\n " })).toBe(
      null,
    );
  });
});

describe("response edge cases", () => {
  test("ok:true with no record at all still reports success without crashing", () => {
    const result = readEditResponse({ ok: true, changed_fields: ["amount"] });
    expect(result.ok).toBe(true);
    expect(result.record).toBe(null);
    expect(describeEditResult(result)).toContain("updated amount");
  });

  test("a success carrying a malformed record degrades to a null record", () => {
    const result = readEditResponse({ ok: true, record: { id: "bad" } });
    expect(result.ok).toBe(true);
    expect(result.record).toBe(null);
  });

  test("an error field that is not a string falls back to a default message", () => {
    expect(readSearchResponse({ ok: false, error: 42 }).error).toBe(
      "search failed",
    );
    expect(readEditResponse({ ok: false, error: null }).error).toBe(
      "edit failed",
    );
  });

  test("ok expressed as a truthy non-true value is not treated as success", () => {
    // Strict === true, so "true", 1, and {} are all failures.
    for (const ok of ["true", 1, {}]) {
      expect(readSearchResponse({ ok, records: [RECORD_JSON] }).ok).toBe(false);
      expect(readEditResponse({ ok, record: RECORD_JSON }).ok).toBe(false);
    }
  });

  test("an empty successful search is a success, not an error", () => {
    const result = readSearchResponse({ ok: true, records: [] });
    expect(result.ok).toBe(true);
    expect(result.error).toBe(null);
  });
});
