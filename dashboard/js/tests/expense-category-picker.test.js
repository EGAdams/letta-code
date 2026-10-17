import { describe, expect, test } from "bun:test";
import { ADD_CATEGORY_VENDOR } from "../abstract/category-creation.interface.js";
import { ExpenseEditDialog } from "../implementation/expense-edit-dialog.js";
import { FakeDocument } from "./_fake-dom.js";

const categories = ["Church [1]", "Church / Office [140]", "Personal [3]"];
const category = { id: 999, name: "Church / Office / Printer ink [999]" };

function setup(result = { ok: true, category, vendor_key: "ink_store" }) {
  const calls = [];
  const http = {
    async getJSON() {
      return { ok: true, categories };
    },
    async postJSON(url, data) {
      calls.push([url, data]);
      return result;
    },
  };
  const doc = new FakeDocument();
  const dialog = new ExpenseEditDialog({
    http,
    doc,
    root: doc.createElement("div"),
    categoryNames: () => categories,
  });
  dialog.render();
  dialog.records = [
    {
      id: 501,
      transactionDate: "2025-01-01",
      totalAmount: 12,
      description: "Ink Store",
      categoryName: categories[1],
      categoryId: 140,
      notes: "",
      distanceMiles: null,
      mapLink: "",
    },
  ];
  dialog._select(501);
  return { picker: dialog.categoryPicker, dialog, calls };
}

async function fill(picker) {
  await picker.open();
  picker.parentSelect.value = categories[1];
  picker.nameInput.value = "Printer ink";
  picker.vendorInput.value = "ink_store";
  picker.descriptionInput.value = "Ink Store";
}

describe("editor category creation", () => {
  const conflict = {
    ok: false,
    code: "vendor_category_conflict",
    conflict: {
      vendor_key: "ink_store",
      current_category: { id: 140, name: categories[1] },
      proposed_category_name: "Church / Office / Printer ink",
    },
  };

  test("existing vendor shows both categories and moves only after explicit confirmation", async () => {
    const { picker, dialog, calls } = setup(conflict);
    await fill(picker);
    const before = dialog.editCategorySelect.value;
    await picker.save();
    expect(picker.status.textContent).toContain(categories[1]);
    expect(picker.status.textContent).toContain(
      "Church / Office / Printer ink",
    );
    expect(picker.moveButton.style.display).toBe("");
    expect(dialog.editCategorySelect.value).toBe(before);
    expect(calls[0][1].expected_vendor_category_id).toBeUndefined();
    picker.http.postJSON = async (url, data) => {
      calls.push([url, data]);
      return { ok: true, category, vendor_key: "ink_store" };
    };
    await picker.save(true);
    expect(calls[1][1].expected_vendor_category_id).toBe(140);
    expect(dialog.editCategorySelect.value).toBe(category.name);
    expect(picker.form.style.display).toBe("none");
    expect(calls.every(([url]) => url === "/api/expense-category-vendor")).toBe(
      true,
    );
  });

  test("editing the proposal invalidates a previously offered move", async () => {
    const { picker, calls } = setup(conflict);
    await fill(picker);
    await picker.save();
    picker.nameInput.value = "Different child";
    await picker.save(true);
    expect(calls[1][1].expected_vendor_category_id).toBeUndefined();
  });

  test("canceling the move makes no second request and clears approval", async () => {
    const { picker, calls } = setup(conflict);
    await fill(picker);
    await picker.save();
    picker.cancelButton.click();
    expect(calls).toHaveLength(1);
    expect(picker.pendingMove).toBeNull();
    expect(picker.moveButton.style.display).toBe("none");
  });

  test("action is first, opens the form and cancellation keeps the selected category", async () => {
    const { picker, dialog, calls } = setup();
    expect(dialog.editCategorySelect.children[0].textContent).toBe(
      "Add a new category and vendor key…",
    );
    const before = dialog.editCategorySelect.value;
    dialog.editCategorySelect.value = ADD_CATEGORY_VENDOR;
    dialog.editCategorySelect.dispatch("change");
    await Promise.resolve();
    expect(picker.form.style.display).toBe("");
    expect(dialog.editCategorySelect.value).toBe(before);
    expect(picker.descriptionInput.value).toBe("Ink Store");
    picker.cancelButton.click();
    expect(picker.form.style.display).toBe("none");
    expect(dialog.editCategorySelect.value).toBe(before);
    expect(calls).toEqual([]);
  });

  test("creation selects the returned exact category without saving an expense", async () => {
    const { picker, dialog, calls } = setup();
    await fill(picker);
    await picker.save();
    expect(calls).toEqual([
      [
        "/api/expense-category-vendor",
        {
          parent_id: 140,
          name: "Printer ink",
          vendor_key: "ink_store",
          description: "Ink Store",
        },
      ],
    ]);
    expect(dialog.editCategorySelect.value).toBe(category.name);
    expect(dialog._editedFields().categoryName).toBe(category.name);
    dialog.records[0].categoryId = 999;
    dialog.records[0].categoryName = "Office";
    dialog._select(501);
    expect(dialog.editCategorySelect.value).toBe(category.name);
    expect(dialog.editCategorySelect.children[0].value).toBe(
      ADD_CATEGORY_VENDOR,
    );
  });

  test("failure stays visible, retains the category choice and permits retry", async () => {
    const { picker, dialog } = setup({
      ok: false,
      error: "That vendor key already belongs to another category.",
    });
    const before = dialog.editCategorySelect.value;
    await fill(picker);
    await picker.save();
    expect(picker.status.textContent).toContain("already belongs");
    expect(picker.form.style.display).toBe("");
    expect(dialog.editCategorySelect.value).toBe(before);
    expect(picker.saveButton.disabled).toBe(false);
  });

  test("invalid vendor key never crosses the HTTP boundary", async () => {
    const { picker, calls } = setup();
    await fill(picker);
    picker.vendorInput.value = "Not a key!";
    await picker.save();
    expect(calls).toEqual([]);
    expect(picker.status.textContent).toContain("lowercase");
  });
});
