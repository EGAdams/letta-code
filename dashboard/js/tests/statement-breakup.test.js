/**
 * "Break Up Document": one scanned statement page -> many walkable expenses.
 *
 * The defect these cover: every fill button asks the RECEIPT parser, which
 * answers with one merchant/date/amount because a receipt has one -- so the
 * six-transaction Choice Privileges page on the 2026-08-19 Last Window Scan
 * filled a single row and left Prev/Next with nothing to walk. A second
 * defect surfaced once that was fixed: the page's $2,900 payment and its
 * $0.00 "Interest Charge on Purchases" line both showed up as navigable
 * items too, as if they needed a category -- store_statement_transactions.py
 * was always going to skip both, so `reviewable` (set server-side by
 * statement_credit_split.reviewable_flags) keeps them off Prev/Next while
 * they still ride along, unedited, in what Save All submits.
 */
import { describe, expect, test } from "bun:test";
import { validateManualEntry } from "../abstract/manual-entry.interface.js";
import {
  buildStatementBreakupPayload,
  buildStatementEntryPayload,
  buildStatementRoutePayload,
  DOCUMENT_SHAPE,
  DOCUMENT_SHAPE_GUIDANCE,
  readStatementBreakupResponse,
  readStatementEntryResponse,
  readStatementRouteResponse,
  recommendedDocumentShape,
  STATEMENT_ENGINE_OPTIONS,
  summarizeExcludedStatementRows,
  summarizeStatementStore,
  validateStatementRow,
} from "../abstract/statement-breakup.interface.js";
import { ManualEntryForm } from "../implementation/manual-entry-form.js";
import { FakeDocument } from "./_fake-dom.js";

// The six rows off the real page. Four are genuine expenses; the payment and
// the $0.00 interest line carry reviewable:false, exactly as the server sets
// them (statement_credit_split.reviewable_flags, mirroring
// store_statement_transactions.py's split_expenses_and_credits).
const BREAKUP_RESPONSE = {
  ok: true,
  bank_name: "Choice Privileges Mastercard",
  account_last4: "5596",
  last4_source: "known_cards_workbook",
  statement_total: 140.45,
  transactions: [
    {
      transaction_date: "2025-05-23",
      description: "QUALITY INNS JASPER TN",
      amount: -93.99,
      reviewable: true,
    },
    {
      transaction_date: "2025-05-23",
      description: "ECONO LODGE VALDOSTA GA",
      amount: -87.8,
      reviewable: true,
    },
    {
      transaction_date: "2025-05-23",
      description: "CRACKER BARREL #428 CAVE CITY KY",
      amount: -28.73,
      reviewable: true,
    },
    {
      transaction_date: "2025-05-31",
      description: "PAYMENT - THANK YOU",
      amount: 2900.0,
      reviewable: false,
    },
    {
      transaction_date: "2025-06-07",
      description: "ELLIS SEARS LOT GRAND RAPIDS MI",
      amount: -6.0,
      reviewable: true,
    },
    {
      transaction_date: "2025-06-20",
      description: "Interest Charge on Purchases",
      amount: 0.0,
      reviewable: false,
    },
  ],
};

function fakeHttp(responses) {
  const calls = [];
  return {
    calls,
    async getJSON(url) {
      calls.push(["GET", url]);
      return responses[url] ?? { ok: true };
    },
    async postJSON(url, body, opts) {
      calls.push(["POST", url, body, opts]);
      const entry = responses[url];
      if (typeof entry === "function") return entry(body);
      return entry ?? { ok: true };
    },
  };
}

function setup(responses = {}) {
  const doc = new FakeDocument();
  doc.location = { reload: () => {} };
  const root = doc.createElement("div");
  root.id = "manual-entry-root";
  root.dataset.imagePath = "/staged/window_scan.jpg";
  root.dataset.conversationId = "conv-1";
  root.dataset.scannerKey = "window";
  doc.add(root);
  const http = fakeHttp({
    "/api/vendor-keys": { ok: true, vendor_keys: [] },
    "/api/rol-finance-categories": { ok: true, categories: ["Food"] },
    "/api/manual-statement-breakup": BREAKUP_RESPONSE,
    ...responses,
  });
  const form = new ManualEntryForm({
    http,
    root,
    doc,
    mountTerminal: async () => null,
  });
  return { form, http };
}

function posts(http, url) {
  return http.calls.filter((c) => c[0] === "POST" && c[1] === url);
}

describe("readStatementBreakupResponse", () => {
  test("navigable items exclude the payment and the zero-amount line", () => {
    const result = readStatementBreakupResponse(BREAKUP_RESPONSE);
    expect(result.ok).toBe(true);
    expect(result.items).toHaveLength(4);
    expect(result.items.map((item) => item.merchantName)).toEqual([
      "QUALITY INNS JASPER TN",
      "ECONO LODGE VALDOSTA GA",
      "CRACKER BARREL #428 CAVE CITY KY",
      "ELLIS SEARS LOT GRAND RAPIDS MI",
    ]);
    expect(result.items[0]).toEqual({
      merchantName: "QUALITY INNS JASPER TN",
      transactionDate: "2025-05-23",
      totalAmount: "-93.99",
      categoryName: "",
    });
    expect(result.header.bankName).toBe("Choice Privileges Mastercard");
    expect(result.header.accountLast4).toBe("5596");
    expect(result.header.statementTotal).toBe(140.45);
  });

  test("excludedRows carries the payment and the zero-amount line", () => {
    const result = readStatementBreakupResponse(BREAKUP_RESPONSE);
    expect(result.excludedRows).toHaveLength(2);
    expect(result.excludedRows.map((row) => row.merchantName)).toEqual([
      "PAYMENT - THANK YOU",
      "Interest Charge on Purchases",
    ]);
    expect(result.excludedRows[0].totalAmount).toBe("2900");
    expect(result.excludedRows[1].totalAmount).toBe("0");
  });

  test("a row missing the reviewable field defaults to shown", () => {
    // Backward compatibility: an older cached response with no `reviewable`
    // key at all must not silently disappear every row into excludedRows.
    const result = readStatementBreakupResponse({
      ...BREAKUP_RESPONSE,
      transactions: [
        { transaction_date: "2025-05-23", description: "X", amount: -1 },
      ],
    });
    expect(result.items).toHaveLength(1);
    expect(result.excludedRows).toHaveLength(0);
  });

  test("a needs-metadata answer still carries the rows it read", () => {
    const result = readStatementBreakupResponse({
      ...BREAKUP_RESPONSE,
      ok: false,
      account_last4: "",
      needs_statement_metadata: true,
      missing_fields: ["account_last4"],
      error: "Statement needs bank name and account last four before storage.",
    });
    expect(result.ok).toBe(false);
    expect(result.needsStatementMetadata).toBe(true);
    expect(result.missingFields).toEqual(["account_last4"]);
    expect(result.items).toHaveLength(4);
    expect(result.excludedRows).toHaveLength(2);
  });

  test("a non-object response reads as an error, never throws", () => {
    expect(readStatementBreakupResponse("<html>502</html>").ok).toBe(false);
    expect(readStatementBreakupResponse(null).items).toEqual([]);
    expect(readStatementBreakupResponse(null).excludedRows).toEqual([]);
  });
});

describe("summarizeExcludedStatementRows", () => {
  test("names what was left out and why, in dollars", () => {
    const result = readStatementBreakupResponse(BREAKUP_RESPONSE);
    const text = summarizeExcludedStatementRows(result.excludedRows);
    expect(text).toContain("2 more line(s)");
    expect(text).toContain("PAYMENT - THANK YOU ($2900.00)");
    expect(text).toContain("Interest Charge on Purchases ($0.00)");
  });

  test("an empty list produces no note at all", () => {
    expect(summarizeExcludedStatementRows([])).toBe("");
  });
});

describe("validateStatementRow", () => {
  test("accepts a credit line the receipt rules would reject", () => {
    const credit = {
      merchantName: "PAYMENT - THANK YOU",
      transactionDate: "2025-05-31",
      totalAmount: "-2900",
      categoryName: "",
    };
    // Which rows are credits is store_statement_transactions.py's call -- it
    // reads the whole page's sign convention. The form must not pre-judge it.
    expect(validateManualEntry(credit).valid).toBe(false);
    expect(validateStatementRow(credit).valid).toBe(true);
  });

  test("still rejects an empty, undated, or zero row", () => {
    expect(
      validateStatementRow({
        merchantName: "",
        transactionDate: "2025-05-31",
        totalAmount: "-5",
      }).valid,
    ).toBe(false);
    expect(
      validateStatementRow({
        merchantName: "X",
        transactionDate: "05/31/2025",
        totalAmount: "-5",
      }).valid,
    ).toBe(false);
    expect(
      validateStatementRow({
        merchantName: "X",
        transactionDate: "2025-05-31",
        totalAmount: "0",
      }).valid,
    ).toBe(false);
  });
});

describe("buildStatementEntryPayload", () => {
  test("serializes whatever rows it's given, with the shared account identity", () => {
    const result = readStatementBreakupResponse(BREAKUP_RESPONSE);
    const payload = buildStatementEntryPayload(
      result.items,
      { imagePath: "/staged/window_scan.jpg", conversationId: "conv-1" },
      result.header,
    );
    expect(payload.transactions).toHaveLength(4);
    expect(payload.bank_name).toBe("Choice Privileges Mastercard");
    expect(payload.account_last4).toBe("5596");
    expect(payload.last4_source).toBe("known_cards_workbook");
  });

  test("items plus excludedRows reconstructs the complete page", () => {
    // This is what the form actually submits (see _saveStatement): the store's
    // split_expenses_and_credits needs the WHOLE page's signs to classify a
    // borderline row correctly, so the excluded rows must ride along, not be
    // dropped just because they aren't shown.
    const result = readStatementBreakupResponse(BREAKUP_RESPONSE);
    const payload = buildStatementEntryPayload(
      [...result.items, ...result.excludedRows],
      { imagePath: "/staged/window_scan.jpg", conversationId: "conv-1" },
      result.header,
    );
    expect(payload.transactions).toHaveLength(6);
    expect(payload.transactions.map((t) => t.description)).toContain(
      "PAYMENT - THANK YOU",
    );
    expect(payload.transactions.map((t) => t.description)).toContain(
      "Interest Charge on Purchases",
    );
  });
});

describe("summarizeStatementStore", () => {
  test("reports the store's own counts, credits and duplicates included", () => {
    const text = summarizeStatementStore(
      readStatementEntryResponse({
        ok: true,
        transactions_parsed: 6,
        stored: 4,
        duplicates: 0,
        skipped_credits: 2,
      }),
    );
    expect(text).toContain("6 transaction(s) read");
    expect(text).toContain("4 stored");
    expect(text).toContain("2 credit/payment skipped");
  });
});

describe("ManualEntryForm break-up flow", () => {
  test("Break Up Document loads only the reviewable rows into Prev/Next", async () => {
    const { form } = setup();
    await form.mount();
    expect(form.items).toHaveLength(1);
    await form._breakUpDocument(undefined, "gemini-only");
    expect(form.items).toHaveLength(4);
    expect(form.statementExcludedRows).toHaveLength(2);
    expect(form.currentIndex).toBe(0);
    expect(form.merchantNameInput.value).toBe("QUALITY INNS JASPER TN");
    form._navigate(1);
    expect(form.merchantNameInput.value).toBe("ECONO LODGE VALDOSTA GA");
    form._navigate(2);
    expect(form.merchantNameInput.value).toBe(
      "ELLIS SEARS LOT GRAND RAPIDS MI",
    );
  });

  test("the break-up status names what was excluded and why", async () => {
    const { form } = setup();
    await form.mount();
    await form._breakUpDocument(undefined, "gemini-only");
    expect(form._statusEl.textContent).toContain("Found 4 transaction(s)");
    expect(form._statusEl.textContent).toContain("PAYMENT - THANK YOU");
    expect(form._statusEl.textContent).toContain(
      "Interest Charge on Purchases",
    );
  });

  test("the position readout names the account every row belongs to", async () => {
    const { form } = setup();
    await form.mount();
    await form._breakUpDocument(undefined, "gemini-only");
    expect(form._positionEl.textContent).toBe(
      "Transaction 1 of 4 — Choice Privileges Mastercard ****5596",
    );
  });

  test("a receipt-mode form still reads 'Expense 1 of 1'", async () => {
    const { form } = setup();
    await form.mount();
    expect(form._positionEl.textContent).toBe("Expense 1 of 1");
  });

  test("Save All submits the reviewable rows AND the excluded ones, merged", async () => {
    const { form, http } = setup({
      "/api/manual-statement-entry": {
        ok: true,
        transactions_parsed: 6,
        stored: 4,
        duplicates: 0,
        skipped_credits: 2,
        expense_ids: [1601, 1602, 1603, 1604],
      },
    });
    await form.mount();
    await form._breakUpDocument(undefined, "gemini-only");
    await form._saveAll();
    expect(posts(http, "/api/manual-receipt-entry")).toHaveLength(0);
    const statementPosts = posts(http, "/api/manual-statement-entry");
    expect(statementPosts).toHaveLength(1);
    // 4 reviewable + 2 excluded = every row the page actually printed.
    expect(statementPosts[0][2].transactions).toHaveLength(6);
    expect(
      statementPosts[0][2].transactions.map((t) => t.description),
    ).toContain("PAYMENT - THANK YOU");
    expect(form._statusEl.textContent).toContain("4 stored");
    expect(form._statusEl.textContent).toContain("2 credit/payment skipped");
  });

  test("the payment and the $0.00 line never need fixing to pass validation", async () => {
    // Before reviewable filtering existed, the operator would have had to
    // manually remove these two rows (or supply a fake category for a $0.00
    // "expense") before Save All would accept the page at all.
    const { form, http } = setup({
      "/api/manual-statement-entry": { ok: true, stored: 4 },
    });
    await form.mount();
    await form._breakUpDocument(undefined, "gemini-only");
    await form._saveAll();
    expect(posts(http, "/api/manual-statement-entry")).toHaveLength(1);
    expect(form._statusEl.textContent).not.toContain("Fix");
  });

  test("a store failure reports the counts it reached, not just an error", async () => {
    const { form } = setup({
      "/api/manual-statement-entry": {
        ok: false,
        transactions_parsed: 6,
        stored: 3,
        failed: 1,
        error: "row 4 has no vendor",
      },
    });
    await form.mount();
    await form._breakUpDocument(undefined, "gemini-only");
    await form._saveAll();
    expect(form._statusEl.textContent).toContain("row 4 has no vendor");
    expect(form._statusEl.textContent).toContain("3 stored");
  });

  test("needs-metadata opens the bank/account prompt and keeps the reviewable rows", async () => {
    const { form, http } = setup({
      "/api/manual-statement-breakup": {
        ...BREAKUP_RESPONSE,
        ok: false,
        account_last4: "",
        needs_statement_metadata: true,
        missing_fields: ["account_last4"],
      },
    });
    await form.mount();
    await form._breakUpDocument(undefined, "gemini-only");
    expect(form.items).toHaveLength(4);
    expect(form.statementExcludedRows).toHaveLength(2);
    expect(form.statementMetadataPrompt.style.display).toBe("");
    // Submit must continue THIS flow, not restart "process as statement".
    form.statementAccountLast4Input.value = "5596";
    await form._resubmitWithStatementMetadata({
      bankName: "Choice Privileges Mastercard",
      accountLast4: "5596",
    });
    const breakupPosts = posts(http, "/api/manual-statement-breakup");
    expect(breakupPosts).toHaveLength(2);
    expect(breakupPosts[1][2].account_last4).toBe("5596");
    expect(posts(http, "/api/process-document")).toHaveLength(0);
  });

  test("an extraction failure leaves the form usable and says why", async () => {
    const { form } = setup({
      "/api/manual-statement-breakup": {
        ok: false,
        error: "Statement rejected: this scan holds 2 separate statements",
        transactions: [],
      },
    });
    await form.mount();
    await form._breakUpDocument(undefined, "gemini-only");
    expect(form.items).toHaveLength(1);
    expect(form.statementHeader).toBe(null);
    expect(form._statusEl.textContent).toContain("2 separate statements");
    expect(form.breakUpButtons["gemini-only"].disabled).toBe(false);
  });

  test("statement mode never claims a Receipts archive path", async () => {
    const { form, http } = setup();
    await form.mount();
    await form._breakUpDocument(undefined, "gemini-only");
    await form._updateArchivePathPreview();
    expect(
      posts(http, "/api/manual-receipt-entry-archive-preview"),
    ).toHaveLength(0);
    expect(form._archivePathEl.textContent).toContain("statement mode");
  });

  test("a genuine expense can still be removed by hand, and stays out of Save All", async () => {
    // Distinct from the auto-excluded payment/interest rows: this is the
    // operator's own editorial call (e.g. "this one was already entered from
    // its receipt"), and unlike an auto-excluded row, a manually removed one
    // is dropped from what gets submitted, not carried along silently.
    const { form, http } = setup({
      "/api/manual-statement-entry": { ok: true, stored: 3 },
    });
    await form.mount();
    await form._breakUpDocument(undefined, "gemini-only");
    form._navigate(2);
    expect(form.merchantNameInput.value).toBe(
      "CRACKER BARREL #428 CAVE CITY KY",
    );
    form._removeItem();
    expect(form.items).toHaveLength(3);
    expect(form.items.map((i) => i.merchantName)).not.toContain(
      "CRACKER BARREL #428 CAVE CITY KY",
    );
    await form._saveAll();
    const submitted = posts(http, "/api/manual-statement-entry")[0][2]
      .transactions;
    // 3 remaining reviewable rows + the 2 still-carried excluded rows.
    expect(submitted).toHaveLength(5);
    expect(submitted.map((t) => t.description)).not.toContain(
      "CRACKER BARREL #428 CAVE CITY KY",
    );
  });

  test("removing every reviewable row leaves a usable blank form, not an empty one", async () => {
    const { form } = setup();
    await form.mount();
    await form._breakUpDocument(undefined, "gemini-only");
    for (let i = 0; i < 4; i++) form._removeItem();
    expect(form.items).toHaveLength(1);
    expect(form.statementHeader).toBe(null);
    expect(form.statementExcludedRows).toHaveLength(0);
    expect(form._positionEl.textContent).toBe("Expense 1 of 1");
    expect(form.merchantNameInput.value).toBe("");
  });

  test("the breakup request carries the image path the operator sees", async () => {
    const { form, http } = setup();
    await form.mount();
    form.imagePathInput.value = "/staged/other_scan.jpg";
    await form._breakUpDocument(undefined, "gemini-only");
    expect(posts(http, "/api/manual-statement-breakup")[0][2]).toEqual(
      buildStatementBreakupPayload(
        { imagePath: "/staged/other_scan.jpg" },
        undefined,
        "gemini-only",
      ),
    );
  });
});

describe("buildStatementRoutePayload", () => {
  test("first attempt (no metadata) omits statement_metadata entirely", () => {
    expect(buildStatementRoutePayload("window")).toEqual({
      scanner: "window",
      doc_kind_override: "statement",
    });
  });

  test("resubmit includes trimmed operator-typed bank/account", () => {
    expect(
      buildStatementRoutePayload("window", {
        bankName: "  Chase  ",
        accountLast4: " 1234 ",
      }),
    ).toEqual({
      scanner: "window",
      doc_kind_override: "statement",
      statement_metadata: { bank_name: "Chase", account_last4: "1234" },
    });
  });

  test("blank operator input is treated the same as no metadata", () => {
    expect(
      buildStatementRoutePayload("window", {
        bankName: "  ",
        accountLast4: "",
      }),
    ).toEqual({ scanner: "window", doc_kind_override: "statement" });
  });
});

describe("readStatementRouteResponse", () => {
  test("reads a successful dispatch", () => {
    expect(
      readStatementRouteResponse({ ok: true, mazda_dispatched: true }),
    ).toEqual({
      ok: true,
      needsStatementMetadata: false,
      rejected: false,
      missingFields: [],
      mazdaDispatched: true,
      error: null,
    });
  });

  test("reads a missing-bank-metadata pause", () => {
    const result = readStatementRouteResponse({
      ok: false,
      needs_statement_metadata: true,
      missing_fields: ["account_last4"],
    });
    expect(result.needsStatementMetadata).toBe(true);
    expect(result.missingFields).toEqual(["account_last4"]);
  });

  test("reads a rejection (e.g. two statements on one scan)", () => {
    const result = readStatementRouteResponse({
      ok: false,
      statement_rejected: true,
      error: "Statement rejected: this scan holds 2 separate statements.",
    });
    expect(result.rejected).toBe(true);
    expect(result.error).toContain("2 separate statements");
  });

  test("prefers stage_error over error, matching process_scanned_document's shape", () => {
    const result = readStatementRouteResponse({
      ok: false,
      error: "generic",
      stage_error: "Mazda was not dispatched (human_only mode).",
    });
    expect(result.error).toBe("Mazda was not dispatched (human_only mode).");
  });

  test.each([[null], [undefined], ["x"], [42]])(
    "malformed response %p never throws",
    (bad) => {
      expect(() => readStatementRouteResponse(bad)).not.toThrow();
      expect(readStatementRouteResponse(bad).ok).toBe(false);
    },
  );
});

describe("STATEMENT_ENGINE_OPTIONS", () => {
  test("names exactly the two single-provider engines, no auto", () => {
    // "auto" is a valid server-side value (the full fallback chain used for
    // Mazda's own automatic dispatch) but is never one of the two buttons an
    // operator sees -- a human who already picked a provider must get exactly
    // that one, with no silent fallback to a different one on failure.
    expect(STATEMENT_ENGINE_OPTIONS.map((o) => o.engine)).toEqual([
      "gemini-only",
      "haiku-only",
    ]);
  });
});

describe("ManualEntryForm break-up fieldset", () => {
  test("renders one labeled group box with a button per engine", async () => {
    const { form } = setup();
    await form.mount();
    expect(Object.keys(form.breakUpButtons)).toEqual([
      "gemini-only",
      "haiku-only",
    ]);
    expect(form.breakUpButtons["gemini-only"].textContent).toBe(
      "Read with Gemini",
    );
    expect(form.breakUpButtons["haiku-only"].textContent).toBe(
      "Read with Haiku",
    );
  });

  test("Read with Haiku sends engine=haiku-only, not the other provider", async () => {
    const { form, http } = setup();
    await form.mount();
    await form._breakUpDocument(undefined, "haiku-only");
    const posts = http.calls.filter(
      (c) => c[0] === "POST" && c[1] === "/api/manual-statement-breakup",
    );
    expect(posts[0][2].engine).toBe("haiku-only");
  });

  test("only the pressed engine's button is disabled while its request is in flight", async () => {
    const { form } = setup();
    await form.mount();
    const pending = form._breakUpDocument(undefined, "gemini-only");
    expect(form.breakUpButtons["gemini-only"].disabled).toBe(true);
    expect(form.breakUpButtons["haiku-only"].disabled).toBe(false);
    await pending;
    expect(form.breakUpButtons["gemini-only"].disabled).toBe(false);
  });

  test("Submit after a needs-metadata pause re-reads with the SAME engine", async () => {
    // Not "auto", and not the other button -- an operator who clicked Haiku
    // must still be reading with Haiku after typing the bank in and hitting
    // Submit, not silently switched to Gemini or the full fallback chain.
    const { form, http } = setup({
      "/api/manual-statement-breakup": {
        ...BREAKUP_RESPONSE,
        ok: false,
        account_last4: "",
        needs_statement_metadata: true,
        missing_fields: ["account_last4"],
      },
    });
    await form.mount();
    await form._breakUpDocument(undefined, "haiku-only");
    form.statementAccountLast4Input.value = "5596";
    await form._resubmitWithStatementMetadata({
      bankName: "Choice Privileges Mastercard",
      accountLast4: "5596",
    });
    const posts = http.calls.filter(
      (c) => c[0] === "POST" && c[1] === "/api/manual-statement-breakup",
    );
    expect(posts).toHaveLength(2);
    expect(posts[1][2].engine).toBe("haiku-only");
  });
});

describe("ManualEntryForm possible-statement Info dialog", () => {
  test("a receipt-shaped fill that reads like a statement shows the Info dialog", async () => {
    const { form } = setup({
      "/api/manual-receipt-entry-preview": {
        ok: false,
        error: "OCR could not read any fields from this document",
        possible_statement: true,
      },
    });
    await form.mount();
    await form._prefill();
    expect(form._infoDialog._el.style.display).toBe("flex");
    expect(form._infoDialog._messageEl.textContent).toContain(
      "Break up Document",
    );
  });

  test("an ordinary receipt fill never shows the Info dialog", async () => {
    const { form } = setup({
      "/api/manual-receipt-entry-preview": {
        ok: true,
        merchant_name: "Kroger",
        transaction_date: "2026-08-15",
        total_amount: 12.34,
        possible_statement: false,
      },
    });
    await form.mount();
    await form._prefill();
    expect(form._infoDialog._el).toBe(null);
  });

  test("OK closes the dialog", async () => {
    const { form } = setup({
      "/api/manual-receipt-entry-preview": {
        ok: false,
        error: "no result",
        possible_statement: true,
      },
    });
    await form.mount();
    await form._prefill();
    expect(form._infoDialog._okButton.textContent).toBe("OK");
    form._infoDialog._okButton._listeners.click[0]();
    expect(form._infoDialog._el.style.display).toBe("none");
  });
});

describe("recommendedDocumentShape", () => {
  test("a statement-shaped page recommends the many-expenses group", () => {
    expect(
      recommendedDocumentShape({ ok: true, possibleStatement: true }),
    ).toBe(DOCUMENT_SHAPE.MANY_EXPENSES);
  });

  test("a readable receipt recommends the one-expense group", () => {
    expect(
      recommendedDocumentShape({ ok: true, possibleStatement: false }),
    ).toBe(DOCUMENT_SHAPE.ONE_EXPENSE);
  });

  test("possibleStatement wins even when the receipt fields failed to read", () => {
    // The DTE bill's shape: the receipt-shaped fields come back thin or
    // empty, which is exactly when the nudge matters most.
    expect(
      recommendedDocumentShape({ ok: false, possibleStatement: true }),
    ).toBe(DOCUMENT_SHAPE.MANY_EXPENSES);
  });

  test("an unreadable page is UNKNOWN, never ONE_EXPENSE", () => {
    // "We could not read this" must not look like "this is a simple receipt"
    // -- that would point the operator at a Fill button on a page nobody
    // has established anything about.
    expect(
      recommendedDocumentShape({ ok: false, possibleStatement: false }),
    ).toBe(DOCUMENT_SHAPE.UNKNOWN);
    expect(recommendedDocumentShape(null)).toBe(DOCUMENT_SHAPE.UNKNOWN);
    expect(recommendedDocumentShape(undefined)).toBe(DOCUMENT_SHAPE.UNKNOWN);
  });

  test("every shape has guidance naming what to press", () => {
    for (const shape of Object.values(DOCUMENT_SHAPE)) {
      expect(typeof DOCUMENT_SHAPE_GUIDANCE[shape]).toBe("string");
      expect(DOCUMENT_SHAPE_GUIDANCE[shape].length).toBeGreaterThan(0);
    }
  });
});

describe("ManualEntryForm classify-on-open", () => {
  test("runs the free local pass once, unprompted, when the form opens", async () => {
    const { form, http } = setup({
      "/api/manual-receipt-entry-preview": {
        ok: true,
        possible_statement: true,
      },
    });
    await form.mount();
    const previews = posts(http, "/api/manual-receipt-entry-preview");
    expect(previews.length).toBe(1);
    // Zero-cost engine only -- classify must never spend a Gemini or Haiku
    // call just to decide which button group to point at.
    expect(previews[0][2].engine).toBe("local");
  });

  test("a statement-shaped page marks the many-expenses group and raises the nudge", async () => {
    const shown = [];
    const { form } = setup({
      "/api/manual-receipt-entry-preview": {
        ok: true,
        possible_statement: true,
      },
    });
    await form.mount();
    form._infoDialog = { show: (m) => shown.push(m) };
    await form._classifyDocumentShape();
    expect(form.documentShape).toBe(DOCUMENT_SHAPE.MANY_EXPENSES);
    expect(form.manyExpensesFieldset.classList.contains("is-recommended")).toBe(
      true,
    );
    expect(form.oneExpenseFieldset.classList.contains("is-recommended")).toBe(
      false,
    );
    expect(shown.length).toBe(1);
  });

  test("a receipt marks the one-expense group and raises nothing", async () => {
    const shown = [];
    const { form } = setup({
      "/api/manual-receipt-entry-preview": {
        ok: true,
        possible_statement: false,
        merchant_name: "KROGER",
      },
    });
    await form.mount();
    form._infoDialog = { show: (m) => shown.push(m) };
    await form._classifyDocumentShape();
    expect(form.documentShape).toBe(DOCUMENT_SHAPE.ONE_EXPENSE);
    expect(form.oneExpenseFieldset.classList.contains("is-recommended")).toBe(
      true,
    );
    expect(shown.length).toBe(0);
  });

  test("classify never writes a field -- it answers which tool, not what the values are", async () => {
    const { form } = setup({
      "/api/manual-receipt-entry-preview": {
        ok: true,
        possible_statement: false,
        merchant_name: "KROGER",
        total_amount: 21.89,
      },
    });
    await form.mount();
    expect(form.merchantNameInput.value).toBe("");
    expect(form.totalAmountInput.value).toBe("");
  });

  test("a dead OCR pass leaves the form fully usable", async () => {
    const { form } = setup({
      "/api/manual-receipt-entry-preview": () => {
        throw new Error("tesseract exploded");
      },
    });
    await form.mount();
    expect(form.documentShape).toBe(DOCUMENT_SHAPE.UNKNOWN);
    expect(form.documentShapeEl.textContent).toBe(
      DOCUMENT_SHAPE_GUIDANCE[DOCUMENT_SHAPE.UNKNOWN],
    );
  });
});
