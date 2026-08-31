/**
 * One scanned statement page -> many walkable expenses.
 *
 * The defect these cover: a receipt parser answers with one
 * merchant/date/amount because a receipt has one -- so the six-transaction
 * Choice Privileges page on the 2026-08-19 Last Window Scan filled a single
 * row and left Prev/Next with nothing to walk. "Mazda Fill" now classifies
 * the page first and routes a statement here on its own (see
 * mazda-fill.test.js for that decision); these cover what happens once it
 * has: which rows become navigable, and what Save All submits. A second
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
  buildStatementEntryPayload,
  readStatementBreakupResponse,
  readStatementEntryResponse,
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

//: /api/mazda-fill's answer for a page the server classified as a statement:
//: the breakup body it already produced, wrapped in the one response shape
//: both document kinds come back in (finance/mazda_fill.MazdaFillResponse).
function mazdaFillStatement(statement) {
  return {
    ok: Boolean(statement.ok || statement.needs_statement_metadata),
    shape: "many-expenses",
    model: "gemini-only",
    doc_kind: "statement",
    statement,
    error: statement.error ?? null,
  };
}

const MAZDA_FILL_STATEMENT_RESPONSE = mazdaFillStatement(BREAKUP_RESPONSE);

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
    "/api/mazda-fill": MAZDA_FILL_STATEMENT_RESPONSE,
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

  test("does not send statement-only provenance to the store", () => {
    const result = readStatementBreakupResponse({
      ...BREAKUP_RESPONSE,
      last4_source: "statement",
    });

    const payload = buildStatementEntryPayload(
      result.items,
      { imagePath: "/staged/freezer_scan.jpg", conversationId: "conv-1" },
      result.header,
    );

    expect(result.header.last4Source).toBe("statement");
    expect(payload.last4_source).toBe("");
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
    await form._mazdaFill();
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
    await form._mazdaFill();
    expect(form._statusEl.textContent).toContain("found 4 transaction(s)");
    expect(form._statusEl.textContent).toContain("PAYMENT - THANK YOU");
    expect(form._statusEl.textContent).toContain(
      "Interest Charge on Purchases",
    );
  });

  test("the position readout names the account every row belongs to", async () => {
    const { form } = setup();
    await form.mount();
    await form._mazdaFill();
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
    await form._mazdaFill();
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
    await form._mazdaFill();
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
    await form._mazdaFill();
    await form._saveAll();
    expect(form._statusEl.textContent).toContain("row 4 has no vendor");
    expect(form._statusEl.textContent).toContain("3 stored");
  });

  test("needs-metadata opens the bank/account prompt and keeps the reviewable rows", async () => {
    const { form, http } = setup({
      "/api/mazda-fill": mazdaFillStatement({
        ...BREAKUP_RESPONSE,
        ok: false,
        account_last4: "",
        needs_statement_metadata: true,
        missing_fields: ["account_last4"],
      }),
    });
    await form.mount();
    await form._mazdaFill();
    expect(form.items).toHaveLength(4);
    expect(form.statementExcludedRows).toHaveLength(2);
    expect(form.statementMetadataPrompt.style.display).toBe("");
    // Submit re-runs the same fill with the typed values -- there is one
    // reading flow now, so there is nothing for it to restart by mistake.
    form.statementAccountLast4Input.value = "5596";
    await form._mazdaFill({
      bankName: "Choice Privileges Mastercard",
      accountLast4: "5596",
    });
    const breakupPosts = posts(http, "/api/mazda-fill");
    expect(breakupPosts).toHaveLength(2);
    expect(breakupPosts[1][2].account_last4).toBe("5596");
    expect(breakupPosts[1][2].model).toBe("gemini-only");
  });

  test("an extraction failure leaves the form usable and says why", async () => {
    const { form } = setup({
      "/api/mazda-fill": mazdaFillStatement({
        ok: false,
        error: "Statement rejected: this scan holds 2 separate statements",
        transactions: [],
      }),
    });
    await form.mount();
    await form._mazdaFill();
    expect(form.items).toHaveLength(1);
    expect(form.statementHeader).toBe(null);
    expect(form._statusEl.textContent).toContain("2 separate statements");
    expect(form.mazdaFillButton.disabled).toBe(false);
  });

  test("statement mode never claims a Receipts archive path", async () => {
    const { form, http } = setup();
    await form.mount();
    await form._mazdaFill();
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
    await form._mazdaFill();
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
    await form._mazdaFill();
    for (let i = 0; i < 4; i++) form._removeItem();
    expect(form.items).toHaveLength(1);
    expect(form.statementHeader).toBe(null);
    expect(form.statementExcludedRows).toHaveLength(0);
    expect(form._positionEl.textContent).toBe("Expense 1 of 1");
    expect(form.merchantNameInput.value).toBe("");
  });

  test("the fill request carries the image path the operator sees", async () => {
    const { form, http } = setup();
    await form.mount();
    form.imagePathInput.value = "/staged/other_scan.jpg";
    await form._mazdaFill();
    expect(posts(http, "/api/mazda-fill")[0][2].image_path).toBe(
      "/staged/other_scan.jpg",
    );
  });
});
