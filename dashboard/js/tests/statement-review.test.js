import { describe, expect, test } from "bun:test";
import {
  answerableFields,
  answerableRows,
  buildMazdaReviewPrompt,
  buildResolvePayload,
  collectCorrections,
  isSubmittable,
  nextPendingReview,
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

  test("date-only failures expose a date field", () => {
    const item = {
      kind: REVIEW_KIND.AMOUNTS,
      rows: [
        {
          index: 0,
          date: null,
          description: "MICROSOFT 365",
          missing: ["date"],
        },
      ],
    };
    expect(answerableFields(item)).toEqual([
      expect.objectContaining({ index: 0, field: "date", inputType: "date" }),
    ]);
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
    expect(
      collectCorrections(amountsItem, { "3:amount": "$1,234.50" }).corrections,
    ).toEqual({
      3: { amount: 1234.5 },
    });
  });

  test("a blank entry is an error, never a silent skip", () => {
    // Skipping would resubmit the same hole and quarantine the statement again.
    const { corrections, errors } = collectCorrections(amountsItem, {
      "3:amount": "  ",
    });
    expect(corrections).toEqual({});
    expect(errors["3:amount"]).toContain("Enter the amount");
  });

  test("rejects junk and non-positive amounts", () => {
    expect(
      collectCorrections(amountsItem, { "3:amount": "abc" }).errors["3:amount"],
    ).toBeTruthy();
    expect(
      collectCorrections(amountsItem, { "3:amount": "0" }).errors["3:amount"],
    ).toBeTruthy();
    expect(
      collectCorrections(amountsItem, { "3:amount": "-5" }).errors["3:amount"],
    ).toBeTruthy();
  });

  test("accepts an ISO transaction date", () => {
    const item = {
      kind: REVIEW_KIND.AMOUNTS,
      rows: [{ index: 0, missing: ["date"] }],
    };
    expect(
      collectCorrections(item, { "0:date": "2025-09-15" }).corrections,
    ).toEqual({ 0: { date: "2025-09-15" } });
  });
});

describe("submittability", () => {
  test("workbook OK is always pressable", () => {
    expect(isSubmittable(workbookItem, {})).toBe(true);
  });

  test("amounts need every row answered", () => {
    expect(isSubmittable(amountsItem, {})).toBe(false);
    expect(isSubmittable(amountsItem, { "3:amount": "4.50" })).toBe(true);
  });
});

describe("resolve payload", () => {
  test("workbook sends just the id", () => {
    expect(buildResolvePayload(workbookItem, {})).toEqual({
      id: "sidecar.json",
    });
  });

  test("amounts send the typed values keyed by row index", () => {
    expect(buildResolvePayload(amountsItem, { "3:amount": "4.50" })).toEqual({
      id: "sidecar.json",
      corrections: { 3: { amount: 4.5 } },
    });
  });

  test("refuses to build a payload while an entry is invalid", () => {
    expect(buildResolvePayload(amountsItem, { "3:amount": "" })).toBeNull();
  });
});

describe("Ask Mazda handoff", () => {
  test("prefills the complete document context and path", () => {
    const item = {
      id: "review.jpg.json",
      document_path: "/bank_statements/_needs_review/review.jpg",
      document_context: {
        source_file: "/incoming/scan.jpg",
        bank_name: "Fifth Third",
        workbook_ambiguous_last4: ["3119", "5938", "6285"],
        transactions: [{ date: "2025-03-17", amount: -12.34 }],
      },
    };

    const prompt = buildMazdaReviewPrompt(item);

    expect(prompt).toContain("/bank_statements/_needs_review/review.jpg");
    expect(prompt).toContain("/incoming/scan.jpg");
    expect(prompt).toContain('"6285"');
    expect(prompt).toContain('"transactions"');
    expect(prompt).toContain("# My question for Mazda");
  });
});

describe("leaving a review for later", () => {
  test("skips the deferred item while leaving it in the server queue", () => {
    const first = { id: "first.json", source_file: "/scans/first.jpg" };
    const second = { id: "second.json" };
    const reviews = [first, second];

    expect(nextPendingReview(reviews, new Set(["/scans/first.jpg"]))).toBe(
      second,
    );
    expect(reviews).toEqual([first, second]);
  });

  test("deferring a source suppresses every retry sidecar for that image", () => {
    const reviews = [
      { id: "retry.json", source_file: "/scans/microsoft.jpg" },
      { id: "original.json", source_file: "/scans/microsoft.jpg" },
    ];

    expect(
      nextPendingReview(reviews, new Set(["/scans/microsoft.jpg"])),
    ).toBeNull();
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

  test("a failed field retry does not incorrectly blame the amount", () => {
    const state = nextStateAfterResolve(amountsItem, {
      ok: false,
      error: "store returned no JSON",
    });
    expect(state.message).toContain("highlighted details");
    expect(state.message).not.toContain("amounts");
  });

  test("singular phrasing for one transaction", () => {
    expect(successMessage({ stored: 1 })).toBe("Stored 1 transaction.");
  });
});
