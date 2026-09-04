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

function setup({
  responses = {},
  categories = ["Office", "Rosemary"],
  confirm = () => true,
} = {}) {
  const doc = new FakeDocument();
  const root = doc.createElement("div");
  doc.add(root);
  const http = fakeHttp(responses);
  const saved = [];
  const deleted = [];
  const dialog = new ExpenseEditDialog({
    http,
    root,
    doc,
    categoryNames: () => categories,
    onSaved: (result) => saved.push(result),
    onDeleted: (id) => deleted.push(id),
    confirm,
  });
  dialog.render();
  return { dialog, http, root, saved, deleted };
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

describe("deleting a row", () => {
  async function pickThenDelete({ deleteResponse, confirm } = {}) {
    const ctx = setup({
      responses: {
        "/api/expense-search": { ok: true, records: [RECORD] },
        "/api/expense-delete": deleteResponse ?? {
          ok: true,
          record: RECORD,
          warnings: [],
        },
      },
      ...(confirm ? { confirm } : {}),
    });
    ctx.dialog.merchantInput.value = "Kroger";
    await ctx.dialog._search();
    click(ctx.root.querySelector('[data-action="expense-pick"]'));
    await ctx.dialog._delete();
    return ctx;
  }

  test("deleting with nothing picked asks for a row first", async () => {
    const { dialog, http } = setup();
    await dialog._delete();
    expect(http.calls).toEqual([]);
    expect(dialog.statusEl.textContent).toContain("Pick a row");
  });

  test("declining the confirmation makes no request", async () => {
    const { dialog, http } = await pickThenDelete({ confirm: () => false });
    expect(http.calls).toHaveLength(1); // the search only
    expect(dialog.selectedId).toBe(501);
  });

  test("confirming posts the expense id and clears the selection", async () => {
    const { dialog, http, deleted } = await pickThenDelete();
    const [url, body] = http.calls[1];
    expect(url).toBe("/api/expense-delete");
    expect(body).toEqual({ expense_id: 501 });
    expect(dialog.selectedId).toBe(null);
    expect(dialog.editEl.style.display).toBe("none");
    expect(dialog.statusEl.textContent).toContain("Deleted Kroger");
    expect(deleted).toEqual([501]);
  });

  test("the deleted row drops out of the results list", async () => {
    const { root } = await pickThenDelete();
    expect(root.querySelectorAll('[data-action="expense-pick"]')).toHaveLength(
      0,
    );
  });

  test("a server error is reported and the selection is left alone", async () => {
    const { dialog, deleted } = await pickThenDelete({
      deleteResponse: { ok: false, error: "expense already deleted" },
    });
    expect(dialog.statusEl.textContent).toContain("expense already deleted");
    expect(dialog.selectedId).toBe(501);
    expect(deleted).toEqual([]);
  });

  test("a rejected request leaves the button usable again", async () => {
    const { dialog } = await pickThenDelete({
      deleteResponse: new Error("offline"),
    });
    expect(dialog.statusEl.textContent).toContain("offline");
    expect(dialog.deleteButton.disabled).toBe(false);
  });
});

// ===========================================================================
// Edge cases
// ===========================================================================

const OTHER_RECORD = {
  id: 777,
  transaction_date: "2026-07-01",
  total_amount: 5.0,
  description: "Meijer",
  vendor_key: "meijer_07_01_26_5_00",
  category_name: "Office",
};

describe("stale selection after a new search", () => {
  async function pickThenSearchAgain(secondResults) {
    let results = [RECORD];
    const http = fakeHttp({
      "/api/expense-search": () => ({ ok: true, records: results }),
    });
    const doc = new FakeDocument();
    const root = doc.createElement("div");
    doc.add(root);
    const dialog = new ExpenseEditDialog({
      http,
      root,
      doc,
      categoryNames: () => ["Office"],
    });
    dialog.render();
    dialog.merchantInput.value = "Kroger";
    await dialog._search();
    click(root.querySelector('[data-action="expense-pick"]'));
    results = secondResults;
    await dialog._search();
    return { dialog, http, root };
  }

  test("a search that no longer contains the picked row clears the selection", async () => {
    // Otherwise the edit fields kept showing the old row and Save would
    // silently correct a row the operator was no longer looking at.
    const { dialog } = await pickThenSearchAgain([OTHER_RECORD]);
    expect(dialog.selectedId).toBe(null);
    expect(dialog.editEl.style.display).toBe("none");
  });

  test("saving after the selection was cleared asks for a row instead of writing", async () => {
    const { dialog, http } = await pickThenSearchAgain([OTHER_RECORD]);
    const before = http.calls.length;
    await dialog._save();
    expect(http.calls).toHaveLength(before);
    expect(dialog.statusEl.textContent).toContain("Pick a row");
  });

  test("a search that still contains the picked row keeps editing it", async () => {
    const { dialog } = await pickThenSearchAgain([RECORD, OTHER_RECORD]);
    expect(dialog.selectedId).toBe(501);
    expect(dialog.editEl.style.display).toBe("");
  });

  test("an empty second search clears the selection too", async () => {
    const { dialog } = await pickThenSearchAgain([]);
    expect(dialog.selectedId).toBe(null);
  });
});

describe("dialog input edge cases", () => {
  test("the amount field is formatted to cents on blur", () => {
    const { dialog } = setup();
    dialog.editAmountInput.value = "12.5";
    dialog.editAmountInput._listeners.blur[0]();
    expect(dialog.editAmountInput.value).toBe("12.50");
  });

  test("a not-yet-numeric amount is left alone rather than fought", () => {
    const { dialog } = setup();
    for (const partial of ["", "-", "1.2.3", "abc"]) {
      dialog.editAmountInput.value = partial;
      dialog.editAmountInput._listeners.blur[0]();
      expect(dialog.editAmountInput.value).toBe(partial);
    }
  });

  test("a trailing decimal point is a finished number and gets formatted", () => {
    // Number("12.") is 12, so this is a complete value, not mid-typing.
    const { dialog } = setup();
    dialog.editAmountInput.value = "12.";
    dialog.editAmountInput._listeners.blur[0]();
    expect(dialog.editAmountInput.value).toBe("12.00");
  });

  test("a search whose only criterion is whitespace never reaches the network", async () => {
    const { dialog, http } = setup();
    dialog.merchantInput.value = "   ";
    await dialog._search();
    expect(http.calls).toEqual([]);
  });

  test("an invalid edit does not clear the operator's typing", async () => {
    const ctx = setup({
      responses: { "/api/expense-search": { ok: true, records: [RECORD] } },
    });
    ctx.dialog.merchantInput.value = "Kroger";
    await ctx.dialog._search();
    click(ctx.root.querySelector('[data-action="expense-pick"]'));
    ctx.dialog.editAmountInput.value = "-5";
    await ctx.dialog._save();
    expect(ctx.dialog.editAmountInput.value).toBe("-5");
    expect(ctx.dialog.errorsEl.textContent).toContain("positive");
  });

  test("a successful save clears a previously shown validation error", async () => {
    const ctx = setup({
      responses: {
        "/api/expense-search": { ok: true, records: [RECORD] },
        "/api/expense-edit": {
          ok: true,
          record: RECORD,
          changed_fields: [],
          warnings: [],
        },
      },
    });
    ctx.dialog.merchantInput.value = "Kroger";
    await ctx.dialog._search();
    click(ctx.root.querySelector('[data-action="expense-pick"]'));
    ctx.dialog.editMerchantInput.value = "  ";
    await ctx.dialog._save();
    expect(ctx.dialog.errorsEl.textContent).toBeTruthy();
    ctx.dialog.editMerchantInput.value = "Kroger";
    await ctx.dialog._save();
    expect(ctx.dialog.errorsEl.textContent).toBe("");
  });

  test("re-rendering the category list keeps the current pick", () => {
    const { dialog } = setup();
    dialog._renderCategoryOptions();
    dialog.editCategorySelect.value = "Rosemary";
    dialog._renderCategoryOptions();
    expect(dialog.editCategorySelect.value).toBe("Rosemary");
  });

  test("an unchanged save is reported as a no-op rather than as a write", async () => {
    const ctx = setup({
      responses: {
        "/api/expense-search": { ok: true, records: [RECORD] },
        "/api/expense-edit": {
          ok: true,
          record: RECORD,
          changed_fields: [],
          warnings: [],
        },
      },
    });
    ctx.dialog.merchantInput.value = "Kroger";
    await ctx.dialog._search();
    click(ctx.root.querySelector('[data-action="expense-pick"]'));
    await ctx.dialog._save();
    expect(ctx.dialog.statusEl.textContent).toContain("No changes");
  });
});
