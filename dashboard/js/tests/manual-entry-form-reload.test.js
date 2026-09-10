/**
 * Regression tests for Save All automatic reload behavior.
 *
 * User requirement: successful Save All must automatically reload exactly once
 * after the entire batch, with no manual Reload button. Failures/validation
 * must not reload.
 */
import { describe, expect, test } from "bun:test";
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

function setup({ http, dataset = {} } = {}) {
  const doc = new FakeDocument();
  let reloadCount = 0;
  doc.location = {
    reload: () => {
      reloadCount += 1;
    },
    get reloadCount() {
      return reloadCount;
    },
  };
  const root = doc.createElement("div");
  root.id = "manual-entry-root";
  root.dataset.imagePath = dataset.imagePath ?? "/staged/scan.jpg";
  root.dataset.conversationId = dataset.conversationId ?? "conv-1";
  root.dataset.scannerKey = dataset.scannerKey ?? "";
  if (dataset.mazdaFindings !== undefined) {
    root.dataset.mazdaFindings = dataset.mazdaFindings;
  }
  doc.add(root);
  const effectiveHttp =
    http ??
    fakeHttp({
      "/api/vendor-keys": { ok: true, vendor_keys: [] },
      "/api/rol-finance-categories": { ok: true, categories: [] },
    });
  const form = new ManualEntryForm({
    http: effectiveHttp,
    root,
    doc,
    mountTerminal: async () => null,
    delay: async () => {},
  });
  return { form, doc, root, http: effectiveHttp };
}

function validItem(overrides = {}) {
  return {
    merchantName: "Kroger",
    transactionDate: "2026-08-15",
    totalAmount: "12.34",
    categoryName: "",
    ...overrides,
  };
}

describe("ManualEntryForm Save All automatic reload", () => {
  test("successful receipt Save All reloads page automatically", async () => {
    const http = fakeHttp({
      "/api/vendor-keys": { ok: true, vendor_keys: [] },
      "/api/rol-finance-categories": { ok: true, categories: [] },
      "/api/manual-receipt-entry": () => ({
        ok: true,
        expense_id: 1,
        duplicate: false,
      }),
    });
    const { form, doc } = setup({ http });
    await form.mount();
    form.items = [validItem()];
    form.currentIndex = 0;
    form._renderCurrentItem();

    await form._saveAll();

    expect(doc.location.reloadCount).toBe(1);
    expect(form._statusEl.textContent).toContain("Reloading page");
  });

  test("successful receipt Save All with multiple items reloads once after all saves", async () => {
    let saveCount = 0;
    const http = fakeHttp({
      "/api/vendor-keys": { ok: true, vendor_keys: [] },
      "/api/rol-finance-categories": { ok: true, categories: [] },
      "/api/manual-receipt-entry": () => {
        saveCount += 1;
        return { ok: true, expense_id: saveCount, duplicate: false };
      },
    });
    const { form, doc } = setup({ http });
    await form.mount();
    form.items = [
      validItem({ merchantName: "Kroger" }),
      validItem({ merchantName: "Walgreens" }),
      validItem({ merchantName: "Meijer" }),
    ];
    form.currentIndex = 0;
    form._renderCurrentItem();

    await form._saveAll();

    expect(saveCount).toBe(3);
    expect(doc.location.reloadCount).toBe(1);
  });

  test("failed receipt Save All does not reload page", async () => {
    const http = fakeHttp({
      "/api/vendor-keys": { ok: true, vendor_keys: [] },
      "/api/rol-finance-categories": { ok: true, categories: [] },
      "/api/manual-receipt-entry": () => ({
        ok: false,
        error: "Duplicate expense",
      }),
    });
    const { form, doc } = setup({ http });
    await form.mount();
    form.items = [validItem()];
    form.currentIndex = 0;
    form._renderCurrentItem();

    await form._saveAll();

    expect(doc.location.reloadCount).toBe(0);
    expect(form._statusEl.textContent).toContain("failed");
    expect(form._statusEl.textContent).not.toContain("Reloading");
  });

  test("validation failure does not reload page", async () => {
    const http = fakeHttp({
      "/api/vendor-keys": { ok: true, vendor_keys: [] },
      "/api/rol-finance-categories": { ok: true, categories: [] },
    });
    const { form, doc } = setup({ http });
    await form.mount();
    form.items = [validItem({ merchantName: "" })]; // Invalid
    form.currentIndex = 0;
    form._renderCurrentItem();

    await form._saveAll();

    expect(doc.location.reloadCount).toBe(0);
    expect(form._statusEl.textContent).toContain("Fix");
  });

  test("partial failure does not reload page", async () => {
    let callCount = 0;
    const http = fakeHttp({
      "/api/vendor-keys": { ok: true, vendor_keys: [] },
      "/api/rol-finance-categories": { ok: true, categories: [] },
      "/api/manual-receipt-entry": () => {
        callCount += 1;
        return callCount === 1
          ? { ok: true, expense_id: 1, duplicate: false }
          : { ok: false, error: "Server error" };
      },
    });
    const { form, doc } = setup({ http });
    await form.mount();
    form.items = [validItem(), validItem()];
    form.currentIndex = 0;
    form._renderCurrentItem();

    await form._saveAll();

    expect(doc.location.reloadCount).toBe(0);
    expect(form._statusEl.textContent).toContain("1 of 2 saved");
    expect(form._statusEl.textContent).toContain("1 failed");
  });

  test("successful UPDATE reloads page automatically", async () => {
    const http = fakeHttp({
      "/api/vendor-keys": { ok: true, vendor_keys: [] },
      "/api/rol-finance-categories": { ok: true, categories: [] },
      "/api/expense-edit": (body) => ({
        ok: true,
        record: {
          id: body.expense_id,
          description: body.merchant_name,
          transaction_date: body.transaction_date,
          total_amount: body.total_amount,
          category_name: "",
        },
        changed_fields: ["amount"],
        warnings: [],
      }),
    });
    const { form, doc } = setup({ http });
    await form.mount();
    form.items = [validItem({ expenseId: 123 })];
    form.currentIndex = 0;
    form._renderCurrentItem();

    await form._saveAll();

    expect(doc.location.reloadCount).toBe(1);
    expect(form._statusEl.textContent).toContain("Reloading page");
  });

  test("successful statement Save All reloads page automatically", async () => {
    const http = fakeHttp({
      "/api/vendor-keys": { ok: true, vendor_keys: [] },
      "/api/rol-finance-categories": { ok: true, categories: [] },
      "/api/manual-statement-entry": () => ({
        ok: true,
        stored_count: 2,
        skipped_credits: 1,
        duplicate_count: 0,
        problems: [],
      }),
    });
    const { form, doc } = setup({ http });
    await form.mount();
    // Set statement mode
    form.statementHeader = {
      bankName: "Choice Privileges",
      accountLast4: "5596",
    };
    form.items = [
      validItem({ merchantName: "Purchase 1" }),
      validItem({ merchantName: "Purchase 2" }),
    ];
    form.currentIndex = 0;
    form._renderCurrentItem();

    await form._saveAll();

    expect(doc.location.reloadCount).toBe(1);
    expect(form._statusEl.textContent).toContain("Reloading page");
  });

  test("failed statement Save All does not reload page", async () => {
    const http = fakeHttp({
      "/api/vendor-keys": { ok: true, vendor_keys: [] },
      "/api/rol-finance-categories": { ok: true, categories: [] },
      "/api/manual-statement-entry": () => ({
        ok: false,
        error: "Could not parse statement",
        stored_count: 0,
        skipped_credits: 0,
        duplicate_count: 0,
        problems: [],
      }),
    });
    const { form, doc } = setup({ http });
    await form.mount();
    form.statementHeader = {
      bankName: "Choice Privileges",
      accountLast4: "5596",
    };
    form.items = [validItem()];
    form.currentIndex = 0;
    form._renderCurrentItem();

    await form._saveAll();

    expect(doc.location.reloadCount).toBe(0);
    expect(form._statusEl.textContent).toContain("not stored");
  });

  test("statement save network error does not reload page", async () => {
    const http = fakeHttp({
      "/api/vendor-keys": { ok: true, vendor_keys: [] },
      "/api/rol-finance-categories": { ok: true, categories: [] },
    });
    http.postJSON = async (url) => {
      if (url === "/api/manual-statement-entry") {
        throw new Error("Network error");
      }
      return { ok: true };
    };
    const { form, doc } = setup({ http });
    await form.mount();
    form.statementHeader = {
      bankName: "Choice Privileges",
      accountLast4: "5596",
    };
    form.items = [validItem()];
    form.currentIndex = 0;
    form._renderCurrentItem();

    await form._saveAll();

    expect(doc.location.reloadCount).toBe(0);
    expect(form._statusEl.textContent).toContain("failed");
  });

  test("no Reload button is created on successful save", async () => {
    const http = fakeHttp({
      "/api/vendor-keys": { ok: true, vendor_keys: [] },
      "/api/rol-finance-categories": { ok: true, categories: [] },
      "/api/manual-receipt-entry": () => ({
        ok: true,
        expense_id: 1,
        duplicate: false,
      }),
    });
    const { form, doc } = setup({ http });
    await form.mount();
    form.items = [validItem()];
    form.currentIndex = 0;
    form._renderCurrentItem();

    await form._saveAll();

    // No reload button should be appended (it reloads automatically instead)
    const buttons = doc.querySelectorAll("button");
    const reloadButton = Array.from(buttons).find((btn) =>
      btn.textContent.includes("Reload page"),
    );
    expect(reloadButton).toBeUndefined();
  });
});
