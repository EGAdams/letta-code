import { describe, expect, test } from "bun:test";
import { ExpenseEditPanel } from "../implementation/expense-edit-panel.js";
import { FakeDocument } from "./_fake-dom.js";

function fakeHttp({ categories, fail = false } = {}) {
  const calls = [];
  return {
    calls,
    async getJSON(url) {
      calls.push(url);
      if (fail) throw new Error("network down");
      return { ok: true, categories: categories ?? [] };
    },
    async postJSON() {
      return { ok: true };
    },
  };
}

function setup(httpOpts, panelOpts = {}) {
  const doc = new FakeDocument();
  const root = doc.createElement("div");
  root.id = "expense-edit-root";
  doc.add(root);
  const http = fakeHttp(httpOpts);
  return {
    doc,
    root,
    http,
    panel: new ExpenseEditPanel({ http, root, doc, ...panelOpts }),
  };
}

function findButton(root, text) {
  const walk = (el) =>
    el.children.flatMap((c) => (c.tagName === "BUTTON" ? [c] : walk(c)));
  return walk(root).find((b) => b.textContent === text);
}

describe("mounting", () => {
  test("requires a root and an http client", () => {
    const doc = new FakeDocument();
    expect(() => new ExpenseEditPanel({ http: {}, root: null })).toThrow(
      TypeError,
    );
    expect(
      () =>
        new ExpenseEditPanel({ http: null, root: doc.createElement("div") }),
    ).toThrow(TypeError);
  });

  test("puts an Edit Expense button on the page with no entry form present", async () => {
    const { panel, root } = setup();
    await panel.mount();
    const button = findButton(root, "Edit Expense");
    expect(button).toBeDefined();
    expect(button.dataset.action).toBe("edit-expense");
  });

  test("the dialog mounts hidden and the button toggles it", async () => {
    const { panel, root } = setup();
    await panel.mount();
    const button = findButton(root, "Edit Expense");
    expect(panel.dialog.panel.style.display).toBe("none");
    button._listeners.click[0]();
    expect(panel.dialog.panel.style.display).toBe("");
    expect(button.classList.contains("is-pressed")).toBe(true);
    button._listeners.click[0]();
    expect(panel.dialog.panel.style.display).toBe("none");
    expect(button.classList.contains("is-pressed")).toBe(false);
  });

  test("the dialog is a sibling of the launcher, not nested inside it", async () => {
    const { panel, root } = setup();
    const launcher = await panel.mount();
    expect(panel.dialog.panel.parent).toBe(root);
    expect(launcher.children).not.toContain(panel.dialog.panel);
  });

  test("expanded mode shows the editor immediately without a launcher", async () => {
    const { panel, root } = setup({}, { expanded: true });
    const launcher = await panel.mount();
    expect(launcher).toBeNull();
    expect(findButton(root, "Edit Expense")).toBeUndefined();
    expect(panel.dialog.panel.style.display).toBe("");
  });
});

describe("category taxonomy", () => {
  test("loads the full expense category list and hands it to the dialog", async () => {
    const { panel, http } = setup({ categories: ["Office", "Rosemary"] });
    await panel.mount();
    expect(http.calls).toEqual(["/api/expense-categories"]);
    expect(panel.categoryNames).toEqual(["Office", "Rosemary"]);
    expect(panel.dialog._categoryNames()).toEqual(["Office", "Rosemary"]);
  });

  test("a failed fetch still leaves a usable panel", async () => {
    const { panel, root } = setup({ fail: true });
    await panel.mount();
    expect(panel.categoryNames).toEqual([]);
    expect(findButton(root, "Edit Expense")).toBeDefined();
  });
});

describe("expense deep links", () => {
  async function mountLink(search, records) {
    const { doc, root, http, panel } = setup(
      { categories: ["Office"] },
      { expanded: true },
    );
    doc.defaultView = { location: { search } };
    const calls = [];
    http.postJSON = async (url, body) => {
      calls.push({ url, body });
      return {
        ok: true,
        records: records.filter((r) => r.id === body.expense_id),
      };
    };
    await panel.mount();
    return { panel, root, calls };
  }
  const record = {
    id: 3414,
    transaction_date: "2025-01-01",
    total_amount: 26.79,
    description: "Meijer",
    category_name: "Office",
  };

  test("opens only the requested ID, even with a stale date in an old report", async () => {
    const { panel, root, calls } = await mountLink(
      "?expense_id=3414&date=2024-12-31",
      [record, { ...record, id: 461, total_amount: 408.85 }],
    );
    expect(calls).toHaveLength(1);
    expect(calls[0].body.expense_id).toBe(3414);
    expect(calls[0].body.date_from).toBe("");
    expect(calls[0].body.date_to).toBe("");
    expect(panel.dialog.selectedId).toBe(3414);
    expect(panel.dialog.editMerchantInput.value).toBe("Meijer");
    expect(panel.dialog.editAmountInput.value).toBe("26.79");
    expect(panel.dialog.resultsEl.children).toHaveLength(1);
    expect(root.querySelector("h2").textContent).toBe("Editing expense #3414");
    expect(panel.dialog.expenseIdInput.value).toBe("3414");
  });

  test("supports ID-only links and clearly identifies a missing expense", async () => {
    const found = await mountLink("?expense_id=3414", [record]);
    expect(found.panel.dialog.selectedId).toBe(3414);
    const missing = await mountLink("?expense_id=999999", []);
    expect(missing.panel.dialog.selectedId).toBeNull();
    expect(missing.root.querySelector("h2").textContent).toContain("999999");
    expect(missing.root.querySelector("h2").textContent).toContain("not found");
  });

  test("rejects malformed IDs without sending a search", async () => {
    for (const query of [
      "",
      "?expense_id=abc",
      "?expense_id=-5",
      "?expense_id=3414junk",
      "?expense_id=1.2",
    ]) {
      const { panel, calls } = await mountLink(query, [record]);
      expect(calls).toHaveLength(0);
      expect(panel.dialog.selectedId).toBeNull();
    }
  });
});

describe("exact expense categories", () => {
  test("selects and saves the stored leaf, rather than its reporting heading", async () => {
    const leaf = "Church / Utilities / Church Electric Bill [123]";
    const housing = "Housing / Housing Utilities / Housing Electric Bill [314]";
    const { doc, panel, http } = setup(
      {
        categories: [
          { id: 120, name: "Church / Utilities [120]" },
          { id: 123, name: leaf },
          { id: 314, name: housing },
          { id: 3, name: "Personal [3]" },
        ],
      },
      { expanded: true },
    );
    doc.defaultView = { location: { search: "?expense_id=3414" } };
    const row = {
      id: 3414,
      transaction_date: "2025-01-01",
      total_amount: 26.79,
      description: "Meijer",
      category_id: 123,
      category_name: "Church Utilities",
    };
    const saves = [];
    http.postJSON = async (url, body) => {
      if (url === "/api/expense-edit") {
        saves.push(body);
        return { ok: true, record: { ...row, category_id: 314 } };
      }
      return { ok: true, records: [row] };
    };
    await panel.mount();
    expect(panel.dialog.editCategorySelect.value).toBe(leaf);
    expect(
      panel.dialog.editCategorySelect.children.map((option) => option.value),
    ).toContain(housing);
    panel.dialog.editCategorySelect.value = housing;
    await panel.dialog._save();
    expect(saves).toHaveLength(1);
    expect(saves[0].category_name).toBe(housing);
    expect(panel.dialog.editCategorySelect.value).toBe(housing);
  });
});

test("a category-list outage never changes the stored category to unresolved", async () => {
  const { doc, panel, http } = setup({ fail: true }, { expanded: true });
  doc.defaultView = { location: { search: "?expense_id=3414" } };
  http.postJSON = async () => ({
    ok: true,
    records: [
      {
        id: 3414,
        transaction_date: "2025-01-01",
        total_amount: 26.79,
        description: "Meijer",
        category_id: 130,
        category_name: "Food & Hospitality",
      },
    ],
  });
  await panel.mount();
  expect(panel.dialog.editCategorySelect.value).toBe(
    "Current category unavailable [130]",
  );
  panel.dialog.toggle();
  panel.dialog.toggle();
  expect(panel.dialog.editCategorySelect.value).toBe(
    "Current category unavailable [130]",
  );
});
