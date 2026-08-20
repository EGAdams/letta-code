/**
 * "Mazda Fill": one button, one cheap model, both document kinds.
 *
 * The defect these cover: the form used to carry five reading buttons, and
 * every one of them required the operator to already know whether the page
 * held one expense or several -- a question only reading the document can
 * answer. A local-OCR heuristic was wired in to guess it and read the DTE gas
 * bill (every date spelled out, headed MULTIPLE BILL STATEMENTS ENCLOSED) as
 * one $28.07 expense. The shape is now an OUTPUT of the read, decided
 * server-side by the same classify the automatic pipeline runs, and the form
 * branches on what came back.
 */
import { describe, expect, test } from "bun:test";
import {
  buildMazdaFillPayload,
  DEFAULT_MAZDA_FILL_MODEL,
  FILL_SHAPE,
  MAZDA_FILL_MODEL_OPTIONS,
  mazdaFillModelLabel,
  readMazdaFillResponse,
  summarizeMazdaReread,
} from "../abstract/mazda-fill.interface.js";
import { ManualEntryForm } from "../implementation/manual-entry-form.js";
import { FakeDocument } from "./_fake-dom.js";

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
  root.dataset.imagePath = "/staged/scan.jpg";
  root.dataset.conversationId = "conv-1";
  root.dataset.scannerKey = "freezer";
  doc.add(root);
  const http = fakeHttp({
    "/api/vendor-keys": { ok: true, vendor_keys: [] },
    "/api/rol-finance-categories": { ok: true, categories: ["Utilities"] },
    "/api/manual-receipt-entry-archive-preview": { ok: false, error: "n/a" },
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

describe("MAZDA_FILL_MODEL_OPTIONS", () => {
  test("offers only models BOTH readers accept, and no free-OCR tier", () => {
    const models = MAZDA_FILL_MODEL_OPTIONS.map((opt) => opt.model);
    expect(models).toEqual(["gemini-only", "haiku-only", "codex-only"]);
    // finance/mazda_fill.assert_models_are_supported() enforces the
    // intersection server-side; these two are the guard against the list
    // quietly regaining the tiers it exists to exclude.
    expect(models).not.toContain("local");
    expect(models).not.toContain("auto");
  });

  test("the default is a real option", () => {
    expect(MAZDA_FILL_MODEL_OPTIONS.map((o) => o.model)).toContain(
      DEFAULT_MAZDA_FILL_MODEL,
    );
  });

  test("every model has a label a human would recognize", () => {
    expect(mazdaFillModelLabel("gemini-only")).toBe("Gemini Flash");
    expect(mazdaFillModelLabel("haiku-only")).toBe("Claude Haiku");
    expect(mazdaFillModelLabel("codex-only")).toBe("Codex (luna)");
    // An unknown value must still read as something, not "undefined": the
    // label goes straight into the operator's status line.
    expect(mazdaFillModelLabel("something-new")).toBe("something-new");
    expect(mazdaFillModelLabel(undefined)).toBe("");
  });
});

describe("buildMazdaFillPayload", () => {
  test("sends the image and model, with blank metadata on a first press", () => {
    expect(
      buildMazdaFillPayload({ imagePath: "/a.jpg" }, "haiku-only"),
    ).toEqual({
      image_path: "/a.jpg",
      model: "haiku-only",
      bank_name: "",
      account_last4: "",
    });
  });

  test("carries operator-typed bank/account back on a retry, trimmed", () => {
    expect(
      buildMazdaFillPayload({ imagePath: "/a.jpg" }, "gemini-only", {
        bankName: "  Choice Privileges  ",
        accountLast4: " 5596 ",
      }),
    ).toEqual({
      image_path: "/a.jpg",
      model: "gemini-only",
      bank_name: "Choice Privileges",
      account_last4: "5596",
    });
  });
});

describe("readMazdaFillResponse", () => {
  test("reads a one-expense answer into the receipt prefill", () => {
    const result = readMazdaFillResponse({
      ok: true,
      shape: "one-expense",
      model: "gemini-only",
      doc_kind: "receipt",
      receipt: {
        ok: true,
        merchant_name: "Kroger",
        transaction_date: "2026-08-15",
        total_amount: 12.34,
      },
    });
    expect(result.shape).toBe(FILL_SHAPE.ONE_EXPENSE);
    expect(result.prefill.merchantName).toBe("Kroger");
    expect(result.prefill.totalAmount).toBe(12.34);
    // The statement half is present and empty rather than undefined, so a
    // caller that reads the wrong half gets nothing, never a crash.
    expect(result.items).toEqual([]);
  });

  test("reads a many-expenses answer into walkable rows", () => {
    const result = readMazdaFillResponse({
      ok: true,
      shape: "many-expenses",
      model: "haiku-only",
      doc_kind: "statement",
      statement: {
        ok: true,
        bank_name: "Choice Privileges Mastercard",
        account_last4: "5596",
        transactions: [
          {
            transaction_date: "2025-05-23",
            description: "QUALITY INNS",
            amount: -93.99,
            reviewable: true,
          },
          {
            transaction_date: "2025-05-31",
            description: "PAYMENT - THANK YOU",
            amount: 2900,
            reviewable: false,
          },
        ],
      },
    });
    expect(result.shape).toBe(FILL_SHAPE.MANY_EXPENSES);
    expect(result.items).toHaveLength(1);
    expect(result.excludedRows).toHaveLength(1);
    expect(result.header.accountLast4).toBe("5596");
    expect(result.prefill.ok).toBe(false);
  });

  test("an unreadable shape falls back to ONE expense, the recoverable one", () => {
    // A receipt shown wrong costs three field corrections. A statement shown
    // as one expense silently discards every transaction but one -- which is
    // the whole defect. So the safe default is the one a human can see.
    for (const json of [null, {}, { shape: "sideways" }, "nope", 7]) {
      expect(readMazdaFillResponse(json).shape).toBe(FILL_SHAPE.ONE_EXPENSE);
    }
  });

  test("a malformed response reads as not-ok with blank halves, never throws", () => {
    const result = readMazdaFillResponse({ ok: "yes", statement: "garbage" });
    expect(result.ok).toBe(false);
    expect(result.items).toEqual([]);
    expect(result.prefill.merchantName).toBe(null);
    expect(result.needsStatementMetadata).toBe(false);
  });

  test("needs-metadata survives into the form's view of the answer", () => {
    const result = readMazdaFillResponse({
      ok: true,
      shape: "many-expenses",
      statement: {
        ok: false,
        needs_statement_metadata: true,
        missing_fields: ["account_last4"],
        transactions: [],
      },
    });
    expect(result.needsStatementMetadata).toBe(true);
    expect(result.missingFields).toEqual(["account_last4"]);
  });
});

describe("ManualEntryForm Mazda Fill routing", () => {
  test("one page, one request — the form never asks which parser to use", async () => {
    const { form, http } = setup({
      "/api/mazda-fill": {
        ok: true,
        shape: "one-expense",
        model: "gemini-only",
        doc_kind: "receipt",
        receipt: { ok: true, merchant_name: "Kroger" },
      },
    });
    await form.mount();
    await form._mazdaFill();
    expect(posts(http, "/api/mazda-fill")).toHaveLength(1);
    // The endpoints the retired buttons aimed at are never called by hand.
    expect(posts(http, "/api/manual-receipt-entry-preview")).toHaveLength(0);
    expect(posts(http, "/api/manual-statement-breakup")).toHaveLength(0);
    expect(posts(http, "/api/process-document")).toHaveLength(0);
  });

  test("mounting costs nothing — no read happens until the button is pressed", async () => {
    // The classify-on-open pass this replaced fired a request on every mount.
    // Mazda Fill is deliberate: a human opens the form, looks at the page
    // with Show Image, and decides to spend the call.
    const { form, http } = setup();
    await form.mount();
    expect(posts(http, "/api/mazda-fill")).toHaveLength(0);
  });

  test("the same page classified as a statement fills MANY rows instead", async () => {
    const { form } = setup({
      "/api/mazda-fill": {
        ok: true,
        shape: "many-expenses",
        model: "gemini-only",
        doc_kind: "statement",
        statement: {
          ok: true,
          bank_name: "DTE Energy",
          account_last4: "0544",
          transactions: [
            {
              transaction_date: "2025-08-14",
              description: "Gas service",
              amount: -28.07,
              reviewable: true,
            },
            {
              transaction_date: "2025-08-14",
              description: "Electric service",
              amount: -41.12,
              reviewable: true,
            },
          ],
        },
      },
    });
    await form.mount();
    expect(form.items).toHaveLength(1);
    await form._mazdaFill();
    // The DTE repro: this page used to be filed as a single expense.
    expect(form.items).toHaveLength(2);
    expect(form.statementHeader.bankName).toBe("DTE Energy");
    expect(form._statusEl.textContent).toContain("MANY expenses");
  });

  test("a read that failed says so and leaves the form typable", async () => {
    const { form } = setup({
      "/api/mazda-fill": {
        ok: false,
        shape: "one-expense",
        model: "haiku-only",
        receipt: { ok: false, error: "quota exhausted" },
        error: "quota exhausted",
      },
    });
    await form.mount();
    form.mazdaModelSelect.value = "haiku-only";
    await form._mazdaFill();
    expect(form._statusEl.textContent).toContain("quota exhausted");
    expect(form._statusEl.textContent).toContain("try the other model");
    expect(form.mazdaFillButton.disabled).toBe(false);
    expect(form.merchantNameInput.value).toBe("");
  });

  test("a statement fill leaves no stale receipt prefill in the fields", async () => {
    // Filling as a receipt first, then re-reading as a statement, must not
    // leave the receipt's merchant sitting on top of transaction row 1.
    const responses = [
      {
        ok: true,
        shape: "one-expense",
        receipt: { ok: true, merchant_name: "DTE Energy" },
      },
      {
        ok: true,
        shape: "many-expenses",
        statement: {
          ok: true,
          bank_name: "DTE Energy",
          account_last4: "0544",
          transactions: [
            {
              transaction_date: "2025-08-14",
              description: "Gas service",
              amount: -28.07,
              reviewable: true,
            },
          ],
        },
      },
    ];
    let call = 0;
    const { form } = setup({
      "/api/mazda-fill": () => responses[call++] ?? responses[1],
    });
    await form.mount();
    await form._mazdaFill();
    expect(form.merchantNameInput.value).toBe("DTE Energy");
    await form._mazdaFill();
    expect(form.merchantNameInput.value).toBe("Gas service");
    expect(form.totalAmountInput.value).toBe("-28.07");
  });
});

// ── the read overrules the classifier (2026-08-19) ─────────────────────────
// The server re-reads a page as a statement when the receipt reader ANSWERED
// that it has no one date and no one merchant AND the page's text holds a
// transaction table. The form must say so: quietly answering a different
// question than the one asked is how an operator stops trusting the button.

describe("readMazdaFillResponse — reread_after", () => {
  test("carries the reason the page was read a second time", () => {
    const result = readMazdaFillResponse({
      ok: true,
      shape: "many-expenses",
      model: "gemini-only",
      reread_after: "gemini-3.6-flash found no transaction date",
      statement: { ok: true, transactions: [] },
    });
    expect(result.rereadAfter).toBe(
      "gemini-3.6-flash found no transaction date",
    );
  });

  test("is empty on a first-time-right read, and on junk", () => {
    expect(
      readMazdaFillResponse({ ok: true, shape: "one-expense" }).rereadAfter,
    ).toBe("");
    expect(readMazdaFillResponse({ reread_after: 7 }).rereadAfter).toBe("");
    expect(readMazdaFillResponse(null).rereadAfter).toBe("");
  });
});

describe("summarizeMazdaReread", () => {
  test("says both what happened and why", () => {
    const sentence = summarizeMazdaReread({
      rereadAfter: "gemini-3.6-flash found no transaction date",
    });
    expect(sentence).toContain("re-read as a statement");
    expect(sentence).toContain("no transaction date");
  });

  test("says nothing when nothing was re-read", () => {
    expect(summarizeMazdaReread({ rereadAfter: "" })).toBe("");
    expect(summarizeMazdaReread(null)).toBe("");
  });
});

describe("the form after a re-read", () => {
  test("the status line tells the operator the page was re-read", async () => {
    const { form } = setup({
      "/api/mazda-fill": {
        ok: true,
        shape: "many-expenses",
        model: "gemini-only",
        reread_after: "gemini-3.6-flash found no transaction date",
        statement: {
          ok: true,
          bank_name: "Chase",
          account_last4: "5783",
          transactions: [
            {
              transaction_date: "2025-03-18",
              description: "Check 11051",
              amount: -30.5,
            },
          ],
        },
      },
    });
    await form.mount();
    await form._mazdaFill();
    expect(form._statusEl.textContent).toContain("re-read as a statement");
    expect(form._statusEl.textContent).toContain("no transaction date");
  });
});
