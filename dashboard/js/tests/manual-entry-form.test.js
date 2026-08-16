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
    async postJSON(url, body) {
      calls.push(["POST", url, body]);
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
