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
  test("loads the same list the entry form loads and hands it to the dialog", async () => {
    const { panel, http } = setup({ categories: ["Office", "Rosemary"] });
    await panel.mount();
    expect(http.calls).toEqual(["/api/rol-finance-categories"]);
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

describe("deep link from the daily spreadsheet", () => {
  // The 2025 workbook links every description cell to
  // edit_expense.html?expense_id=..&date=.., so a click in Excel must land on
  // that row already populated rather than on an empty search form.
  function fakeDialog(records, holder) {
    return class {
      constructor() {
        this.selected = null;
        this.status = null;
        this.searchedDate = null;
        holder.last = this;
      }
      render() {}
      toggle() {}
      async searchByDate(date) {
        this.searchedDate = date;
        return records;
      }
      selectStoredExpense(id) {
        this.selected = id;
      }
      setStatusMessage(text) {
        this.status = text;
      }
    };
  }

  function mountWith(search, records) {
    const { doc, root, http } = setup();
    doc.defaultView = { location: { search } };
    const holder = {};
    const panel = new ExpenseEditPanel({
      http,
      root,
      doc,
      EditDialog: fakeDialog(records, holder),
      expanded: true,
    });
    return { panel, holder };
  }

  test("selects the expense the URL names", async () => {
    const { panel, holder } = mountWith("?expense_id=2431&date=2025-07-14", [
      { id: 2431 },
      { id: 99 },
    ]);
    await panel.mount();
    expect(holder.last.searchedDate).toBe("2025-07-14");
    expect(holder.last.selected).toBe(2431);
  });

  test("explains itself when the id is not on that date", async () => {
    const { panel, holder } = mountWith("?expense_id=2431&date=2025-07-14", [
      { id: 99 },
    ]);
    await panel.mount();
    expect(holder.last.selected).toBeNull();
    expect(holder.last.status).toContain("2431");
  });

  test("ignores a malformed or absent link and stays a plain search form", async () => {
    for (const search of [
      "",
      "?expense_id=abc&date=2025-07-14",
      "?expense_id=2431",
      "?expense_id=2431&date=07/14/2025",
      "?expense_id=-5&date=2025-07-14",
    ]) {
      const { panel, holder } = mountWith(search, [{ id: 2431 }]);
      await panel.mount();
      expect(holder.last.searchedDate).toBeNull();
      expect(holder.last.selected).toBeNull();
    }
  });
});
