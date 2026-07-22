import { describe, expect, test } from "bun:test";
import {
  answerableRows,
  buildResolvePayload,
  collectAmounts,
  isSubmittable,
  nextStateAfterResolve,
  prefillFor,
  REVIEW_KIND,
  successMessage,
} from "../abstract/statement-review.interface.js";

const amountsItem = {
  id: "sidecar.json",
  kind: REVIEW_KIND.AMOUNTS,
  rows: [
    {
      index: 3,
      date: "2025-01-07",
      description: "SMUDGED",
      missing: ["amount"],
      suggested_amount: 4.5,
    },
  ],
};

const workbookItem = {
  id: "sidecar.json",
  kind: REVIEW_KIND.WORKBOOK,
  bank_name: "Bank Of Nowhere",
  rows: [],
};

describe("answerable rows", () => {
  test("only rows missing an amount are asked about", () => {
    const item = {
      kind: REVIEW_KIND.AMOUNTS,
      rows: [
        { index: 0, missing: ["amount"] },
        { index: 1, missing: ["date"] },
      ],
    };
    expect(answerableRows(item).map((r) => r.index)).toEqual([0]);
  });

  test("a workbook item asks about no rows", () => {
    expect(answerableRows(workbookItem)).toEqual([]);
  });
});

describe("prefill", () => {
  test("uses the server's suggestion when there is one", () => {
    expect(prefillFor({ suggested_amount: 4.5 })).toBe("4.50");
  });

  test("is blank when no suggestion could be determined", () => {
    expect(prefillFor({ suggested_amount: null })).toBe("");
  });
});

describe("collecting what the human typed", () => {
  test("accepts a plain number and strips $ and commas", () => {
    expect(collectAmounts(amountsItem, { 3: "$1,234.50" }).amounts).toEqual({
      3: 1234.5,
    });
  });

  test("a blank entry is an error, never a silent skip", () => {
    // Skipping would resubmit the same hole and quarantine the statement again.
    const { amounts, errors } = collectAmounts(amountsItem, { 3: "  " });
    expect(amounts).toEqual({});
    expect(errors[3]).toContain("Enter the amount");
  });

  test("rejects junk and non-positive amounts", () => {
    expect(collectAmounts(amountsItem, { 3: "abc" }).errors[3]).toBeTruthy();
    expect(collectAmounts(amountsItem, { 3: "0" }).errors[3]).toBeTruthy();
    expect(collectAmounts(amountsItem, { 3: "-5" }).errors[3]).toBeTruthy();
  });
});

describe("submittability", () => {
  test("workbook OK is always pressable", () => {
    expect(isSubmittable(workbookItem, {})).toBe(true);
  });

  test("amounts need every row answered", () => {
    expect(isSubmittable(amountsItem, {})).toBe(false);
    expect(isSubmittable(amountsItem, { 3: "4.50" })).toBe(true);
  });
});

describe("resolve payload", () => {
  test("workbook sends just the id", () => {
    expect(buildResolvePayload(workbookItem, {})).toEqual({
      id: "sidecar.json",
    });
  });

  test("amounts send the typed values keyed by row index", () => {
    expect(buildResolvePayload(amountsItem, { 3: "4.50" })).toEqual({
      id: "sidecar.json",
      amounts: { 3: 4.5 },
    });
  });

  test("refuses to build a payload while an entry is invalid", () => {
    expect(buildResolvePayload(amountsItem, { 3: "" })).toBeNull();
  });
});

describe("after resolving", () => {
  test("success closes the dialog and reports what was stored", () => {
    const state = nextStateAfterResolve(amountsItem, {
      ok: true,
      report: { stored: 4, duplicates: 2, uncategorized: 1 },
    });
    expect(state.done).toBe(true);
    expect(state.message).toContain("Stored 4 transactions");
    expect(state.message).toContain("2 already on file");
    expect(state.message).toContain("1 awaiting a vendor");
  });

  test("a failed workbook retry keeps the dialog up and says why", () => {
    const state = nextStateAfterResolve(workbookItem, {
      ok: false,
      error: "still no workbook row",
      item: workbookItem,
    });
    expect(state.done).toBe(false);
    expect(state.item).toBe(workbookItem);
    expect(state.message).toContain("still no workbook row");
    expect(state.message).toContain("press OK again");
  });

  test("singular phrasing for one transaction", () => {
    expect(successMessage({ stored: 1 })).toBe("Stored 1 transaction.");
  });
});
