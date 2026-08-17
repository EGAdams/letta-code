import { describe, expect, test } from "bun:test";
import { ExpenseEditDialog } from "../implementation/expense-edit-dialog.js";
import { FakeDocument } from "./_fake-dom.js";

function fakeHttp(responses) {
  const calls = [];
  return {
    calls,
    async postJSON(url, body) {
      calls.push([url, body]);
      const entry = responses[url];
      if (typeof entry === "function") return entry(body);
      if (entry instanceof Error) throw entry;
      return entry ?? { ok: true };
    },
  };
}

const RECORD = {
  id: 501,
  transaction_date: "2026-08-15",
  total_amount: 12.34,
  description: "Kroger",
  vendor_key: "kroger_08_15_26_12_34",
  category_name: "Office",
};

function setup({ responses = {}, categories = ["Office", "Rosemary"] } = {}) {
  const doc = new FakeDocument();
  const root = doc.createElement("div");
  doc.add(root);
  const http = fakeHttp(responses);
  const saved = [];
  const dialog = new ExpenseEditDialog({
    http,
    root,
    doc,
    categoryNames: () => categories,
    onSaved: (result) => saved.push(result),
  });
  dialog.render();
  return { dialog, http, root, saved };
}

function click(el) {
  return el._listeners.click[0]();
}

describe("mounting", () => {
  test("requires a root and an http client", () => {
    const doc = new FakeDocument();
    expect(() => new ExpenseEditDialog({ http: {}, root: null })).toThrow(
      TypeError,
    );
    expect(
      () =>
        new ExpenseEditDialog({ http: null, root: doc.createElement("div") }),
    ).toThrow(TypeError);
  });

  test("renders hidden, and the edit fields stay hidden until a row is picked", () => {
    const { dialog } = setup();
    expect(dialog.panel.style.display).toBe("none");
    expect(dialog.editEl.style.display).toBe("none");
  });

  test("toggle shows and hides the panel and reports its state", () => {
    const { dialog } = setup();
    expect(dialog.toggle()).toBe(true);
    expect(dialog.panel.style.display).toBe("");
    expect(dialog.toggle()).toBe(false);
    expect(dialog.panel.style.display).toBe("none");
  });
});

describe("search", () => {
  test("an empty search never reaches the network", async () => {
    const { dialog, http } = setup();
    await dialog._search();
    expect(http.calls).toEqual([]);
    expect(dialog.statusEl.textContent).toContain("Enter a merchant");
  });

  test("a valid search posts the criteria and lists the results", async () => {
    const { dialog, http, root } = setup({
      responses: { "/api/expense-search": { ok: true, records: [RECORD] } },
    });
    dialog.merchantInput.value = "Kroger";
    await dialog._search();
    expect(http.calls[0][0]).toBe("/api/expense-search");
    expect(http.calls[0][1].merchant).toBe("Kroger");
    const rows = root.querySelectorAll('[data-action="expense-pick"]');
    expect(rows).toHaveLength(1);
    expect(rows[0].textContent).toContain("#501");
    expect(dialog.statusEl.textContent).toContain("1 match(es)");
  });

  test("no matches is reported plainly, not as an error", async () => {
    const { dialog } = setup({
      responses: { "/api/expense-search": { ok: true, records: [] } },
    });
    dialog.amountInput.value = "12.34";
    await dialog._search();
    expect(dialog.statusEl.textContent).toContain("No stored expenses matched");
  });

  test("a server error is shown rather than throwing", async () => {
    const { dialog } = setup({
      responses: { "/api/expense-search": { ok: false, error: "db down" } },
    });
    dialog.merchantInput.value = "Kroger";
    await dialog._search();
    expect(dialog.statusEl.textContent).toContain("db down");
  });

  test("a rejected request leaves the button usable again", async () => {
    const { dialog } = setup({
      responses: { "/api/expense-search": new Error("offline") },
    });
    dialog.merchantInput.value = "Kroger";
    await dialog._search();
    expect(dialog.statusEl.textContent).toContain("offline");
    expect(dialog.searchButton.disabled).toBe(false);
  });
});

describe("picking a row", () => {
  async function pickOne(extra = {}) {
    const ctx = setup({
      responses: {
        "/api/expense-search": { ok: true, records: [RECORD] },
        ...extra,
      },
    });
    ctx.dialog.merchantInput.value = "Kroger";
    await ctx.dialog._search();
    click(ctx.root.querySelector('[data-action="expense-pick"]'));
    return ctx;
  }

  test("loads the stored values into the edit fields", async () => {
    const { dialog } = await pickOne();
    expect(dialog.selectedId).toBe(501);
    expect(dialog.editMerchantInput.value).toBe("Kroger");
    expect(dialog.editDateInput.value).toBe("2026-08-15");
    expect(dialog.editAmountInput.value).toBe("12.34");
    expect(dialog.editCategorySelect.value).toBe("Office");
    expect(dialog.editEl.style.display).toBe("");
  });

  test("a category the taxonomy no longer offers falls back to unresolved", async () => {
    const doc = new FakeDocument();
    const root = doc.createElement("div");
    doc.add(root);
    const dialog = new ExpenseEditDialog({
      http: fakeHttp({
        "/api/expense-search": { ok: true, records: [RECORD] },
      }),
      root,
      doc,
      categoryNames: () => ["Rosemary"],
    });
    dialog.render();
    dialog.merchantInput.value = "Kroger";
    await dialog._search();
    click(root.querySelector('[data-action="expense-pick"]'));
    expect(dialog.editCategorySelect.value).toBe("");
  });
});

describe("saving an edit", () => {
  async function pickThenSave(editResponse, mutate = () => {}) {
    const ctx = setup({
      responses: {
        "/api/expense-search": { ok: true, records: [RECORD] },
        "/api/expense-edit": editResponse,
      },
    });
    ctx.dialog.merchantInput.value = "Kroger";
    await ctx.dialog._search();
    click(ctx.root.querySelector('[data-action="expense-pick"]'));
    mutate(ctx.dialog);
    await ctx.dialog._save();
    return ctx;
  }

  test("saving with nothing picked asks for a row first", async () => {
    const { dialog, http } = setup();
    await dialog._save();
    expect(http.calls).toEqual([]);
    expect(dialog.statusEl.textContent).toContain("Pick a row");
  });

  test("posts the corrected fields and reports what changed", async () => {
    const { dialog, http, saved } = await pickThenSave(
      {
        ok: true,
        record: { ...RECORD, description: "Kroger Fuel" },
        changed_fields: ["description"],
        warnings: [],
      },
      (d) => {
        d.editMerchantInput.value = "Kroger Fuel";
      },
    );
    const [url, body] = http.calls[1];
    expect(url).toBe("/api/expense-edit");
    expect(body).toEqual({
      expense_id: 501,
      merchant_name: "Kroger Fuel",
      transaction_date: "2026-08-15",
      total_amount: 12.34,
      category_name: "Office",
    });
    expect(dialog.statusEl.textContent).toContain("updated description");
    expect(saved).toHaveLength(1);
  });

  test("server warnings are shown alongside the success message", async () => {
    const { dialog } = await pickThenSave({
      ok: true,
      record: RECORD,
      changed_fields: ["amount"],
      warnings: ["vendor key is stale"],
    });
    expect(dialog.statusEl.textContent).toContain("vendor key is stale");
  });

  test("an invalid field is caught before the request", async () => {
    const { dialog, http } = await pickThenSave({ ok: true }, (d) => {
      d.editMerchantInput.value = "   ";
    });
    expect(http.calls).toHaveLength(1); // the search only
    expect(dialog.errorsEl.textContent).toContain("required");
  });

  test("the results list is refreshed from the saved record", async () => {
    const { root } = await pickThenSave(
      {
        ok: true,
        record: { ...RECORD, description: "Kroger Fuel" },
        changed_fields: ["description"],
        warnings: [],
      },
      (d) => {
        d.editMerchantInput.value = "Kroger Fuel";
      },
    );
    expect(
      root.querySelector('[data-action="expense-pick"]').textContent,
    ).toContain("Kroger Fuel");
  });

  test("a failed edit does not report success and does not notify", async () => {
    const { dialog, saved } = await pickThenSave({
      ok: false,
      error: "no expense with id 501",
    });
    expect(dialog.statusEl.textContent).toContain("no expense with id 501");
    expect(saved).toEqual([]);
    expect(dialog.saveButton.disabled).toBe(false);
  });
});
