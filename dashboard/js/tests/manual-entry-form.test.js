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
  doc.location = { reload: () => {} };
  const root = doc.createElement("div");
  root.id = "manual-entry-root";
  root.dataset.imagePath = dataset.imagePath ?? "/staged/scan.jpg";
  root.dataset.conversationId = dataset.conversationId ?? "conv-1";
  root.dataset.scannerKey = dataset.scannerKey ?? "";
  doc.add(root);
  const effectiveHttp =
    http ??
    fakeHttp({
      "/api/vendor-keys": {
        ok: true,
        vendor_keys: [
          { vendor_key: "kroger", category_id: 5, category_name: "Food" },
        ],
      },
      "/api/rol-finance-categories": {
        ok: true,
        categories: ["Food", "Uncategorized"],
      },
      "/api/manual-receipt-entry-archive-preview": (body) => ({
        ok: true,
        path: `/archive/${body.archive_kind}/${body.merchant_name}.jpg`,
        is_real_destination:
          body.archive_kind === "receipt" && !body.custom_archive_root,
      }),
    });
  const form = new ManualEntryForm({
    http: effectiveHttp,
    root,
    doc,
    mountTerminal: async () => null,
  });
  return { form, doc, root, http: effectiveHttp };
}

describe("ManualEntryForm.mount", () => {
  test("prefills the image path input from the mount point's data attribute", async () => {
    const { form } = setup({
      dataset: { imagePath: "/staged/scan_freezer.jpg" },
    });
    await form.mount();
    expect(form.imagePathInput.value).toBe("/staged/scan_freezer.jpg");
  });

  test("loads vendor and category dropdown options", async () => {
    const { form } = setup();
    await form.mount();
    const vendorValues = form.vendorSelect.children.map((c) => c.value);
    expect(vendorValues).toContain("kroger");
    expect(vendorValues).toContain("__new__");
    const categoryValues = form.categorySelect.children.map((c) => c.value);
    expect(categoryValues).toContain("Food");
  });

  test("a dropdown fetch failure leaves the form usable with empty dropdowns", async () => {
    const http = fakeHttp({});
    http.getJSON = async () => {
      throw new Error("network down");
    };
    const { form } = setup({ http });
    await form.mount();
    expect(form.vendorOptions).toEqual([]);
    expect(form.categoryNames).toEqual([]);
  });
});

describe("ManualEntryForm vendor selection", () => {
  test("picking a known vendor fills the merchant name and its category", async () => {
    const { form } = setup();
    await form.mount();
    form.vendorSelect.value = "kroger";
    form.vendorSelect.dispatch("change", {});
    expect(form.merchantNameInput.value).toBe("kroger");
    expect(form.categorySelect.value).toBe("Food");
  });

  test("the '+ Add new vendor' sentinel leaves the merchant field untouched", async () => {
    const { form } = setup();
    await form.mount();
    form.merchantNameInput.value = "My Own Vendor";
    form.vendorSelect.value = "__new__";
    form.vendorSelect.dispatch("change", {});
    expect(form.merchantNameInput.value).toBe("My Own Vendor");
  });
});

describe("ManualEntryForm multi-item navigation", () => {
  test("Add Another Expense appends a blank item and moves to it", async () => {
    const { form } = setup();
    await form.mount();
    form.merchantNameInput.value = "Kroger";
    form._addItem();
    expect(form.items.length).toBe(2);
    expect(form.currentIndex).toBe(1);
    expect(form.merchantNameInput.value).toBe("");
    // The first item's data was captured before the new blank one was added.
    expect(form.items[0].merchantName).toBe("Kroger");
  });

  test("Prev/Next preserve each item's own field values", async () => {
    const { form } = setup();
    await form.mount();
    form.merchantNameInput.value = "Kroger";
    form._addItem();
    form.merchantNameInput.value = "Walgreens";
    form._navigate(-1);
    expect(form.merchantNameInput.value).toBe("Kroger");
    form._navigate(1);
    expect(form.merchantNameInput.value).toBe("Walgreens");
  });

  test("navigating past either end is a no-op", async () => {
    const { form } = setup();
    await form.mount();
    form._navigate(-1);
    expect(form.currentIndex).toBe(0);
  });
});

describe("ManualEntryForm._prefill", () => {
  test("fills blank fields from a successful OCR preview", async () => {
    const http = fakeHttp({
      "/api/vendor-keys": { ok: true, vendor_keys: [] },
      "/api/rol-finance-categories": { ok: true, categories: [] },
      "/api/manual-receipt-entry-preview": {
        ok: true,
        merchant_name: "Kroger",
        transaction_date: "2026-08-15",
        total_amount: 12.34,
      },
    });
    const { form } = setup({ http });
    await form.mount();
    await form._prefill();
    expect(form.merchantNameInput.value).toBe("Kroger");
    expect(form.transactionDateInput.value).toBe("2026-08-15");
    expect(form.totalAmountInput.value).toBe("12.34");
  });

  test("preselects the vendor dropdown and category from a matched vendor_key", async () => {
    const http = fakeHttp({
      "/api/vendor-keys": {
        ok: true,
        vendor_keys: [
          {
            vendor_key: "consumers_energy",
            category_id: 55,
            category_name: "Utilities",
          },
        ],
      },
      "/api/rol-finance-categories": { ok: true, categories: ["Utilities"] },
      "/api/manual-receipt-entry-preview": {
        ok: true,
        merchant_name: "Consumers Energy",
        vendor_key: "consumers_energy",
        category_name: "Utilities",
      },
    });
    const { form } = setup({ http });
    await form.mount();
    await form._prefill();
    // The readable OCR name stays in the free-text field -- only the
    // dropdown/category get preselected, not overwritten to the slug.
    expect(form.merchantNameInput.value).toBe("Consumers Energy");
    expect(form.vendorSelect.value).toBe("consumers_energy");
    expect(form.categorySelect.value).toBe("Utilities");
    expect(form._statusEl.textContent).toContain("Vendor/category matched too");
  });

  test("a category-only fuzzy match prefills the category without touching the vendor dropdown", async () => {
    const http = fakeHttp({
      "/api/vendor-keys": { ok: true, vendor_keys: [] },
      "/api/rol-finance-categories": { ok: true, categories: ["Restaurants"] },
      "/api/manual-receipt-entry-preview": {
        ok: true,
        merchant_name: "Mr Burger Restaurant",
        category_name: "Restaurants",
      },
    });
    const { form } = setup({ http });
    await form.mount();
    await form._prefill();
    expect(form.vendorSelect.value).toBe("");
    expect(form.categorySelect.value).toBe("Restaurants");
  });

  test("no vendor/category match leaves the dropdowns alone and doesn't claim a match", async () => {
    const http = fakeHttp({
      "/api/vendor-keys": { ok: true, vendor_keys: [] },
      "/api/rol-finance-categories": { ok: true, categories: [] },
      "/api/manual-receipt-entry-preview": {
        ok: true,
        merchant_name: "Totally Unknown Vendor",
      },
    });
    const { form } = setup({ http });
    await form.mount();
    await form._prefill();
    expect(form._statusEl.textContent).not.toContain("Vendor/category matched");
  });

  test("disables and visually presses the button only while the OCR request is in flight", async () => {
    let stateDuringRequest = null;
    const http = fakeHttp({
      "/api/vendor-keys": { ok: true, vendor_keys: [] },
      "/api/rol-finance-categories": { ok: true, categories: [] },
      "/api/manual-receipt-entry-preview": (body) => {
        stateDuringRequest = {
          disabled: form.prefillButton.disabled,
          pressed: form.prefillButton.classList.contains("is-pressed"),
        };
        return { ok: true, merchant_name: "Kroger" };
      },
    });
    const { form } = setup({ http });
    await form.mount();
    expect(form.prefillButton.disabled).toBe(false);
    await form._prefill();
    expect(stateDuringRequest).toEqual({ disabled: true, pressed: true });
    expect(form.prefillButton.disabled).toBe(false);
    expect(form.prefillButton.classList.contains("is-pressed")).toBe(false);
  });

  test("re-enables the button after a failed OCR request", async () => {
    const http = fakeHttp({
      "/api/vendor-keys": { ok: true, vendor_keys: [] },
      "/api/rol-finance-categories": { ok: true, categories: [] },
      "/api/manual-receipt-entry-preview": () => {
        throw new Error("boom");
      },
    });
    const { form } = setup({ http });
    await form.mount();
    await form._prefill();
    expect(form.prefillButton.disabled).toBe(false);
    expect(form.prefillButton.classList.contains("is-pressed")).toBe(false);
    expect(form._statusEl.textContent).toContain("Prefill request failed");
  });

  test("Gemini Flash Fill button requests the gemini-only engine and reports its own source", async () => {
    let requestedEngine = null;
    const http = fakeHttp({
      "/api/vendor-keys": { ok: true, vendor_keys: [] },
      "/api/rol-finance-categories": { ok: true, categories: [] },
      "/api/manual-receipt-entry-preview": (body) => {
        requestedEngine = body.engine;
        return { ok: true, merchant_name: "DTE Energy" };
      },
    });
    const { form } = setup({ http });
    await form.mount();
    await form._prefill("gemini-only", form.geminiFillButton, "Gemini Flash");
    expect(requestedEngine).toBe("gemini-only");
    expect(form.merchantNameInput.value).toBe("DTE Energy");
    expect(form._statusEl.textContent).toContain("Prefilled from Gemini Flash");
  });

  test("Gemini Flash Fill only disables/presses its own button, not Prefill from OCR", async () => {
    let stateDuringRequest = null;
    const http = fakeHttp({
      "/api/vendor-keys": { ok: true, vendor_keys: [] },
      "/api/rol-finance-categories": { ok: true, categories: [] },
      "/api/manual-receipt-entry-preview": () => {
        stateDuringRequest = {
          geminiPressed: form.geminiFillButton.classList.contains("is-pressed"),
          prefillDisabled: form.prefillButton.disabled,
        };
        return { ok: true, merchant_name: "DTE Energy" };
      },
    });
    const { form } = setup({ http });
    await form.mount();
    await form._prefill("gemini-only", form.geminiFillButton, "Gemini Flash");
    expect(stateDuringRequest).toEqual({
      geminiPressed: true,
      prefillDisabled: false,
    });
    expect(form.geminiFillButton.disabled).toBe(false);
    expect(form.geminiFillButton.classList.contains("is-pressed")).toBe(false);
  });

  test("Gemini Flash Fill requests a longer fetch timeout than the browser default", async () => {
    // fetch-http-client.js's default is 30s; a real call through Gemini's
    // model-fallback chain measured at 18-25s, close enough that a slightly
    // larger image could cross it and abort client-side while the (90s
    // server-side budget) request was still working. Local OCR never leaves
    // the box, so it must NOT get the same override.
    const http = fakeHttp({
      "/api/vendor-keys": { ok: true, vendor_keys: [] },
      "/api/rol-finance-categories": { ok: true, categories: [] },
      "/api/manual-receipt-entry-preview": {
        ok: true,
        merchant_name: "DTE Energy",
      },
    });
    const { form } = setup({ http });
    await form.mount();

    await form._prefill("gemini-only", form.geminiFillButton, "Gemini Flash");
    const [, , , geminiOpts] = http.calls.at(-1);
    expect(geminiOpts).toEqual({ timeout: 95000 });

    await form._prefill();
    const [, , , localOpts] = http.calls.at(-1);
    expect(localOpts).toBeUndefined();
  });

  test("Fill with Haiku button requests the haiku-only engine and reports its own source", async () => {
    let requestedEngine = null;
    const http = fakeHttp({
      "/api/vendor-keys": { ok: true, vendor_keys: [] },
      "/api/rol-finance-categories": { ok: true, categories: [] },
      "/api/manual-receipt-entry-preview": (body) => {
        requestedEngine = body.engine;
        return { ok: true, merchant_name: "DTE Energy" };
      },
    });
    const { form } = setup({ http });
    await form.mount();
    await form._prefill("haiku-only", form.haikuFillButton, "Claude Haiku");
    expect(requestedEngine).toBe("haiku-only");
    expect(form.merchantNameInput.value).toBe("DTE Energy");
    expect(form._statusEl.textContent).toContain("Prefilled from Claude Haiku");
  });

  test("Fill with Haiku only disables/presses its own button, not Prefill from OCR", async () => {
    let stateDuringRequest = null;
    const http = fakeHttp({
      "/api/vendor-keys": { ok: true, vendor_keys: [] },
      "/api/rol-finance-categories": { ok: true, categories: [] },
      "/api/manual-receipt-entry-preview": () => {
        stateDuringRequest = {
          haikuPressed: form.haikuFillButton.classList.contains("is-pressed"),
          prefillDisabled: form.prefillButton.disabled,
        };
        return { ok: true, merchant_name: "DTE Energy" };
      },
    });
    const { form } = setup({ http });
    await form.mount();
    await form._prefill("haiku-only", form.haikuFillButton, "Claude Haiku");
    expect(stateDuringRequest).toEqual({
      haikuPressed: true,
      prefillDisabled: false,
    });
    expect(form.haikuFillButton.disabled).toBe(false);
    expect(form.haikuFillButton.classList.contains("is-pressed")).toBe(false);
  });

  test("Fill with Haiku requests a longer fetch timeout than the browser default", async () => {
    // Same reasoning as Gemini Flash Fill's timeout override -- an OAuth
    // refresh (occasionally a `claude -p "ok"` subprocess call) can push the
    // real Messages API call close to the 30s browser default.
    const http = fakeHttp({
      "/api/vendor-keys": { ok: true, vendor_keys: [] },
      "/api/rol-finance-categories": { ok: true, categories: [] },
      "/api/manual-receipt-entry-preview": {
        ok: true,
        merchant_name: "DTE Energy",
      },
    });
    const { form } = setup({ http });
    await form.mount();

    await form._prefill("haiku-only", form.haikuFillButton, "Claude Haiku");
    const [, , , haikuOpts] = http.calls.at(-1);
    expect(haikuOpts).toEqual({ timeout: 95000 });
  });
});

describe("ManualEntryForm._routeAsStatement", () => {
  test("first click requests doc_kind_override without metadata", async () => {
    let sentBody = null;
    const http = fakeHttp({
      "/api/vendor-keys": { ok: true, vendor_keys: [] },
      "/api/rol-finance-categories": { ok: true, categories: [] },
      "/api/process-document": (body) => {
        sentBody = body;
        return { ok: true, mazda_dispatched: true };
      },
    });
    const { form } = setup({ http, dataset: { scannerKey: "window" } });
    await form.mount();

    await form._routeAsStatement();

    expect(sentBody).toEqual({
      scanner: "window",
      doc_kind_override: "statement",
    });
    expect(form._statusEl.textContent).toContain("Routed to statement intake");
    expect(form._statusEl.textContent).toContain(
      "investigate/categorize/store",
    );
  });

  test("a missing-metadata response opens the bank/account prompt", async () => {
    const http = fakeHttp({
      "/api/vendor-keys": { ok: true, vendor_keys: [] },
      "/api/rol-finance-categories": { ok: true, categories: [] },
      "/api/process-document": {
        ok: false,
        needs_statement_metadata: true,
        missing_fields: ["account_last4"],
      },
    });
    const { form } = setup({ http, dataset: { scannerKey: "window" } });
    await form.mount();

    await form._routeAsStatement();

    expect(form.statementMetadataPrompt.style.display).toBe("");
    expect(form._statusEl.textContent).toContain("account_last4");
  });

  test("Submit resends the operator-typed bank/account and closes the prompt on success", async () => {
    let sentBody = null;
    const http = fakeHttp({
      "/api/vendor-keys": { ok: true, vendor_keys: [] },
      "/api/rol-finance-categories": { ok: true, categories: [] },
      "/api/process-document": (body) => {
        sentBody = body;
        return { ok: true, mazda_dispatched: true };
      },
    });
    const { form } = setup({ http, dataset: { scannerKey: "window" } });
    await form.mount();
    form.statementBankNameInput.value = "Chase";
    form.statementAccountLast4Input.value = "1234";

    await form._routeAsStatement({
      bankName: form.statementBankNameInput.value,
      accountLast4: form.statementAccountLast4Input.value,
    });

    expect(sentBody).toEqual({
      scanner: "window",
      doc_kind_override: "statement",
      statement_metadata: { bank_name: "Chase", account_last4: "1234" },
    });
    expect(form.statementMetadataPrompt.style.display).toBe("none");
  });

  test("a rejected statement (e.g. two accounts on one scan) shows the reason and does not reopen the prompt", async () => {
    const http = fakeHttp({
      "/api/vendor-keys": { ok: true, vendor_keys: [] },
      "/api/rol-finance-categories": { ok: true, categories: [] },
      "/api/process-document": {
        ok: false,
        statement_rejected: true,
        error: "Statement rejected: this scan holds 2 separate statements.",
      },
    });
    const { form } = setup({ http, dataset: { scannerKey: "window" } });
    await form.mount();

    await form._routeAsStatement();

    expect(form._statusEl.textContent).toContain("2 separate statements");
    expect(form.statementMetadataPrompt.style.display).toBe("none");
  });

  test("does nothing when there is no scanner (PDF-kind intake)", async () => {
    const http = fakeHttp({
      "/api/vendor-keys": { ok: true, vendor_keys: [] },
      "/api/rol-finance-categories": { ok: true, categories: [] },
    });
    const { form } = setup({ http, dataset: { scannerKey: "" } });
    await form.mount();

    await form._routeAsStatement();

    expect(http.calls.some(([, url]) => url === "/api/process-document")).toBe(
      false,
    );
  });

  test("the button is disabled when there is no scanner, matching Show Image", async () => {
    const { form } = setup({ dataset: { scannerKey: "" } });
    await form.mount();
    expect(form.statementButton.disabled).toBe(true);
  });
});

describe("ManualEntryForm._saveAll", () => {
  function validItem(overrides = {}) {
    return {
      merchantName: "Kroger",
      transactionDate: "2026-08-15",
      totalAmount: "12.34",
      categoryName: "",
      ...overrides,
    };
  }

  test("an invalid item blocks the save and navigates to it", async () => {
    const submitCalls = [];
    const http = fakeHttp({
      "/api/vendor-keys": { ok: true, vendor_keys: [] },
      "/api/rol-finance-categories": { ok: true, categories: [] },
      "/api/manual-receipt-entry": (body) => {
        submitCalls.push(body);
        return { ok: true, expense_id: 1, duplicate: false };
      },
    });
    const { form } = setup({ http });
    await form.mount();
    form.items = [validItem(), validItem({ merchantName: "" })];
    form.currentIndex = 0;
    form._renderCurrentItem();
    await form._saveAll();
    expect(submitCalls).toEqual([]);
    expect(form.currentIndex).toBe(1);
    expect(form._errorsEl.textContent).toContain("Merchant");
  });

  test("all-valid items are submitted in order and status reports success", async () => {
    const submitCalls = [];
    const http = fakeHttp({
      "/api/vendor-keys": { ok: true, vendor_keys: [] },
      "/api/rol-finance-categories": { ok: true, categories: [] },
      "/api/manual-receipt-entry": (body) => {
        submitCalls.push(body);
        return { ok: true, expense_id: submitCalls.length, duplicate: false };
      },
    });
    const { form } = setup({ http });
    await form.mount();
    form.items = [
      validItem({ merchantName: "Kroger" }),
      validItem({ merchantName: "Walgreens" }),
    ];
    form.currentIndex = 0;
    form._renderCurrentItem();
    await form._saveAll();
    expect(submitCalls.length).toBe(2);
    expect(submitCalls[0].merchant_name).toBe("Kroger");
    expect(submitCalls[1].merchant_name).toBe("Walgreens");
    expect(form._statusEl.textContent).toContain("All 2 expense(s) saved");
  });

  test("a newly-remembered vendor is reported and the dropdown is reloaded", async () => {
    let vendorKeysCallCount = 0;
    const http = {
      calls: [],
      async getJSON(url) {
        this.calls.push(["GET", url]);
        if (url === "/api/vendor-keys") {
          vendorKeysCallCount += 1;
          return vendorKeysCallCount === 1
            ? { ok: true, vendor_keys: [] }
            : {
                ok: true,
                vendor_keys: [
                  {
                    vendor_key: "samaritans_purse",
                    category_id: 215,
                    category_name: "Samaritans Purse",
                  },
                ],
              };
        }
        return { ok: true, categories: [] };
      },
      async postJSON(url, body) {
        this.calls.push(["POST", url, body]);
        if (url === "/api/manual-receipt-entry") {
          return {
            ok: true,
            expense_id: 1,
            duplicate: false,
            vendor_remembered: {
              remembered: true,
              vendor_key: "samaritans_purse",
            },
          };
        }
        return { ok: true };
      },
    };
    const { form } = setup({ http });
    await form.mount();
    form.items = [validItem({ merchantName: "Samaritans Purse" })];
    form.currentIndex = 0;
    form._renderCurrentItem();
    await form._saveAll();
    expect(form._statusEl.textContent).toContain(
      "Remembered new vendor(s): samaritans_purse",
    );
    expect(
      form.vendorOptions.some((v) => v.vendorKey === "samaritans_purse"),
    ).toBe(true);
  });

  test("a save failure reports which item failed and does not offer reload", async () => {
    const http = fakeHttp({
      "/api/vendor-keys": { ok: true, vendor_keys: [] },
      "/api/rol-finance-categories": { ok: true, categories: [] },
      "/api/manual-receipt-entry": { ok: false, error: "merchant required" },
    });
    const { form } = setup({ http });
    await form.mount();
    form.items = [validItem()];
    form.currentIndex = 0;
    form._renderCurrentItem();
    await form._saveAll();
    expect(form._statusEl.textContent).toContain("merchant required");
    expect(form._statusEl.children.some((c) => c.tagName === "BUTTON")).toBe(
      false,
    );
  });

  test("skips archive verification when no scanner key is present", async () => {
    const archiveCalls = [];
    const http = fakeHttp({
      "/api/vendor-keys": { ok: true, vendor_keys: [] },
      "/api/rol-finance-categories": { ok: true, categories: [] },
      "/api/manual-receipt-entry": {
        ok: true,
        expense_id: 1,
        duplicate: false,
      },
      "/api/scanner-archive-path": (body) => {
        archiveCalls.push(body);
        return { ok: true, archive_path: "/archive", archive_name: "r.jpg" };
      },
    });
    const { form } = setup({ http, dataset: { scannerKey: "" } });
    await form.mount();
    form.items = [validItem()];
    form.currentIndex = 0;
    form._renderCurrentItem();
    await form._saveAll();
    expect(archiveCalls).toEqual([]);
  });

  test("mounts the archive-verification terminal when a scanner key is present", async () => {
    const sentCommands = [];
    const http = fakeHttp({
      "/api/vendor-keys": { ok: true, vendor_keys: [] },
      "/api/rol-finance-categories": { ok: true, categories: [] },
      "/api/manual-receipt-entry": {
        ok: true,
        expense_id: 1,
        duplicate: false,
      },
      "/api/scanner-archive-path": {
        ok: true,
        archive_path: "/archive",
        archive_name: "r.jpg",
      },
    });
    const doc = new FakeDocument();
    doc.location = { reload: () => {} };
    const root = doc.createElement("div");
    root.id = "manual-entry-root";
    root.dataset.imagePath = "/staged/scan.jpg";
    root.dataset.conversationId = "conv-1";
    root.dataset.scannerKey = "freezer";
    doc.add(root);
    const fakeSession = { sendLine: (cmd) => sentCommands.push(cmd) };
    const form = new ManualEntryForm({
      http,
      root,
      doc,
      mountTerminal: async () => fakeSession,
    });
    await form.mount();
    form.items = [validItem()];
    form.currentIndex = 0;
    form._renderCurrentItem();
    await form._saveAll();
    expect(sentCommands.length).toBe(1);
    expect(sentCommands[0]).toContain("cd '/archive'");
    expect(form._statusEl.children.some((c) => c.tagName === "BUTTON")).toBe(
      true,
    );
  });
});

describe("ManualEntryForm archive path preview", () => {
  test("defaults to the receipts archive for a single expense", async () => {
    const { form } = setup();
    await form.mount();
    expect(form.archiveKind).toBe("receipt");
    expect(form.archiveKindSelect.value).toBe("receipt");
  });

  test("Add Another Expense switches the default to scanned documents", async () => {
    const { form } = setup();
    await form.mount();
    form._addItem();
    expect(form.archiveKind).toBe("scanned_document");
  });

  test("a manual 'File as' choice is not overridden by adding another expense", async () => {
    const { form } = setup();
    await form.mount();
    form.archiveKindSelect.value = "receipt";
    form.archiveKindSelect.dispatch("change", {});
    form._addItem();
    expect(form.archiveKind).toBe("receipt");
  });

  test("picking 'Other folder' reveals the custom root input", async () => {
    const { form } = setup();
    await form.mount();
    expect(form.customArchiveRootInput.style.display).toBe("none");
    form.archiveKindSelect.value = "other";
    form.archiveKindSelect.dispatch("change", {});
    expect(form.customArchiveRootInput.style.display).toBe("");
  });

  test("shows a computed path once merchant/date/amount are all present", async () => {
    const { form } = setup();
    await form.mount();
    form.merchantNameInput.value = "Kroger";
    form.transactionDateInput.value = "2026-08-15";
    form.totalAmountInput.value = "12.34";
    form._captureCurrentItem();
    await form._updateArchivePathPreview();
    expect(form._archivePathEl.textContent).toContain("Kroger");
  });

  test("flags a non-receipt archive kind as preview-only", async () => {
    const { form } = setup();
    await form.mount();
    form.merchantNameInput.value = "Kroger";
    form.transactionDateInput.value = "2026-08-15";
    form.totalAmountInput.value = "12.34";
    form._captureCurrentItem();
    form.archiveKind = "scanned_document";
    await form._updateArchivePathPreview();
    expect(form._archivePathEl.textContent).toContain("preview only");
  });

  test("shows a placeholder when fields are incomplete", async () => {
    const { form } = setup();
    await form.mount();
    await form._updateArchivePathPreview();
    expect(form._archivePathEl.textContent).toContain("pick a vendor");
  });

  test("_prefill refreshes the archive path after OCR fills in fields", async () => {
    const http = fakeHttp({
      "/api/vendor-keys": { ok: true, vendor_keys: [] },
      "/api/rol-finance-categories": { ok: true, categories: [] },
      "/api/manual-receipt-entry-preview": {
        ok: true,
        merchant_name: "Kroger",
        transaction_date: "2026-08-15",
        total_amount: 12.34,
      },
      "/api/manual-receipt-entry-archive-preview": (body) => ({
        ok: true,
        path: `/archive/${body.merchant_name}.jpg`,
        is_real_destination: true,
      }),
    });
    const { form } = setup({ http });
    await form.mount();
    await form._prefill();
    expect(form._archivePathEl.textContent).toContain("Kroger");
  });
});

describe("ambiguous vendor pick-list (DTE repro)", () => {
  const AMBIGUOUS_PREFILL = {
    ok: true,
    merchant_name: "DTE Energy",
    transaction_date: "2025-05-12",
    total_amount: 90.34,
    vendor_key: null,
    category_name: null,
    vendor_ambiguous: true,
    vendor_candidates: [
      { vendor_key: "dte_energy_0544", category_name: "Housing Gas Bill" },
      { vendor_key: "dte_energy_0020", category_name: "Church Electric Bill" },
    ],
  };

  function ambiguousHttp(prefill = AMBIGUOUS_PREFILL) {
    return fakeHttp({
      "/api/vendor-keys": {
        ok: true,
        vendor_keys: [
          { vendor_key: "dte_energy_0544", category_name: "Housing Gas Bill" },
          {
            vendor_key: "dte_energy_0020",
            category_name: "Church Electric Bill",
          },
        ],
      },
      "/api/rol-finance-categories": {
        ok: true,
        categories: ["Housing Gas Bill", "Church Electric Bill"],
      },
      "/api/manual-receipt-entry-preview": prefill,
      "/api/manual-receipt-entry-archive-preview": { ok: false, error: "n/a" },
    });
  }

  async function prefilled(prefill) {
    const ctx = setup({ http: ambiguousHttp(prefill) });
    await ctx.form.mount();
    await ctx.form._prefill();
    return ctx;
  }

  test("prefills neither vendor nor category, and offers both accounts", async () => {
    const { form, root } = await prefilled();
    expect(form.vendorSelect.value).toBe("");
    expect(form.categorySelect.value).toBe("");
    const choices = root.querySelectorAll('[data-action="vendor-candidate"]');
    expect(choices).toHaveLength(2);
    expect(choices[0].textContent).toContain("dte_energy_0544");
    expect(choices[0].textContent).toContain("Housing Gas Bill");
  });

  test("the status explains why nothing was guessed", async () => {
    const { form } = await prefilled();
    expect(form._statusEl.textContent).toContain("More than one stored vendor");
  });

  test("the merchant name is still prefilled so the operator sees the read", async () => {
    const { form } = await prefilled();
    expect(form.merchantNameInput.value).toBe("DTE Energy");
    expect(form.totalAmountInput.value).toBe("90.34");
  });

  test("picking a candidate resolves the vendor and its category", async () => {
    const { form, root } = await prefilled();
    const choice = root.querySelectorAll('[data-action="vendor-candidate"]')[0];
    await choice._listeners.click[0]();
    expect(form.vendorSelect.value).toBe("dte_energy_0544");
    expect(form.categorySelect.value).toBe("Housing Gas Bill");
    expect(form.merchantNameInput.value).toBe("dte_energy_0544");
    expect(form.items[0].categoryName).toBe("Housing Gas Bill");
  });

  test("picking a candidate clears the pick-list", async () => {
    const { root } = await prefilled();
    await root
      .querySelectorAll('[data-action="vendor-candidate"]')[0]
      ._listeners.click[0]();
    expect(
      root.querySelectorAll('[data-action="vendor-candidate"]'),
    ).toHaveLength(0);
  });

  test("an unambiguous prefill shows no pick-list at all", async () => {
    const { root } = await prefilled({
      ok: true,
      merchant_name: "Kroger",
      transaction_date: "2026-08-15",
      total_amount: 12.34,
      vendor_key: null,
      category_name: null,
    });
    expect(
      root.querySelectorAll('[data-action="vendor-candidate"]'),
    ).toHaveLength(0);
  });

  test("ambiguous:true with an empty candidate list shows no pick-list", async () => {
    const { root } = await prefilled({
      ...AMBIGUOUS_PREFILL,
      vendor_candidates: [],
    });
    expect(
      root.querySelectorAll('[data-action="vendor-candidate"]'),
    ).toHaveLength(0);
  });
});
