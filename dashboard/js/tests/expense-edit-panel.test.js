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

function setup(httpOpts) {
  const doc = new FakeDocument();
  const root = doc.createElement("div");
  root.id = "expense-edit-root";
  doc.add(root);
  const http = fakeHttp(httpOpts);
  return { doc, root, http, panel: new ExpenseEditPanel({ http, root, doc }) };
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
