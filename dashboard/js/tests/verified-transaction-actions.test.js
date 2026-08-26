import { describe, expect, test } from "bun:test";
import { verifiedTransactionRowsRegistry } from "../abstract/mounted-widget-registry.js";
import {
  buildAddTaxPayload,
  buildDeletePayload,
  deleteConfirmMessage,
  indexAfterRemoval,
  readRowActionResponse,
  signedAmountAfterTax,
} from "../abstract/verified-transaction-actions.interface.js";
import { VerifiedTransactionRows } from "../implementation/verified-transaction-rows.js";
import { FakeDocument } from "./_fake-dom.js";

describe("Verified Transactions row rules", () => {
  test("names the selected description in the Delete prompt", () => {
    expect(deleteConfirmMessage("Kroger")).toBe("Delete Expense Kroger?");
  });

  test("posts only the selected expense id", () => {
    expect(buildDeletePayload("42")).toEqual({ expense_id: 42 });
    expect(buildAddTaxPayload("42")).toEqual({ expense_id: 42 });
  });

  test("keeps the current expense valid after every removal position", () => {
    expect(indexAfterRemoval(1, 2, 2)).toBe(1); // Expense 2 of 3 -> 2 of 2
    expect(indexAfterRemoval(1, 0, 2)).toBe(0); // same expense shifted left
    expect(indexAfterRemoval(2, 2, 2)).toBe(1); // deleted last -> previous
    expect(indexAfterRemoval(0, 0, 0)).toBe(0);
  });

  test("keeps an expense's displayed sign after adding tax", () => {
    expect(signedAmountAfterTax("-28.73", 30.45)).toBe("-30.45");
    expect(signedAmountAfterTax("28.73", 30.45)).toBe("30.45");
  });

  test("fails closed when a successful response omits its record", () => {
    const result = readRowActionResponse({ ok: true });
    expect(result.ok).toBe(true);
    expect(result.record).toBeNull();
  });

  test("a saved edit repaints every displayed transaction value", () => {
    const doc = new FakeDocument();
    const panel = doc.createElement("div");
    const table = doc.createElement("table");
    const row = doc.createElement("tr");
    row.dataset.expenseId = "2246";
    row.dataset.description = "Old Merchant";
    row.dataset.date = "2025-07-13";
    row.dataset.vendorKey = "old_vendor";
    row.dataset.signedAmount = "-26.49";
    const description = doc.createElement("td");
    const amount = doc.createElement("td");
    amount.className = "number";
    const date = doc.createElement("td");
    date.className = "vt-date";
    const category = doc.createElement("td");
    category.className = "category-cell";
    row.append(description, amount, date, category);
    table.appendChild(row);
    panel.appendChild(table);

    const controller = new VerifiedTransactionRows({
      http: {},
      table,
      doc,
    }).mount();
    expect(
      controller.updateExpense(
        {
          id: 2246,
          description: "Meijer",
          transactionDate: "2025-07-14",
          totalAmount: 26.5,
          categoryName: "Food",
        },
        "meijer",
      ),
    ).toBe(true);

    expect(description.textContent).toBe("Meijer");
    expect(amount.textContent).toBe("-26.50");
    expect(date.textContent).toBe("2025-07-14");
    expect(category.textContent).toBe("Food");
    expect(row.dataset.vendorKey).toBe("meijer");
    expect(row.dataset.signedAmount).toBe("-26.50");
    verifiedTransactionRowsRegistry.reset();
  });

  test("a saved insert appends a complete actionable transaction row", () => {
    const doc = new FakeDocument();
    const panel = doc.createElement("div");
    const table = doc.createElement("table");
    const body = doc.createElement("tbody");
    table.appendChild(body);
    panel.appendChild(table);
    const controller = new VerifiedTransactionRows({
      http: {},
      table,
      doc,
    }).mount();

    expect(
      controller.addExpense(
        {
          id: 2301,
          description: "Meijer",
          transactionDate: "2025-07-14",
          totalAmount: 11.25,
          idLight: "meijer_07_14_25_11_25",
          categoryName: "Food",
        },
        "meijer",
      ),
    ).toBe(true);

    const row = body.querySelector("tr[data-expense-id]");
    expect(row.dataset.expenseId).toBe("2301");
    expect(row.dataset.signedAmount).toBe("11.25");
    expect(row.querySelector("td").textContent).toBe("Meijer");
    expect(row.querySelectorAll("[data-vt-action]")).toHaveLength(3);
    expect(controller.addExpense({ id: 2301 }, "meijer")).toBe(false);
    verifiedTransactionRowsRegistry.reset();
  });
});
