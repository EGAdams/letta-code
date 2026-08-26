/**
 * The Edit / Delete / Add 6% buttons on each Verified Transactions row.
 *
 * The table itself is server-rendered (finance/intake_report_page.py's
 * transactions_table_html) and stays that way: Python emits the row, its
 * data-* attributes, and three inert buttons; this file is the only thing that
 * knows what pressing one means. That is the same split the manual entry form
 * and the category picker already use on this page.
 *
 * What each button does, and why it does it there rather than here:
 *
 *   Edit    — hands the row to the review dialog already on the page
 *             (ManualEntryForm), which walks its Prev/Next list to that
 *             expense and reads out "Expense 2 of 3". Nothing is duplicated:
 *             the table's rows and that dialog's items are two views of the
 *             same findings, keyed on the stored expense id.
 *   Delete  — confirms by name, then POSTs /api/expense-delete. The row leaves
 *             the table AND the dialog's list in the same step, so the count
 *             between Prev and Next can never outlive the rows behind it.
 *   Add 6%  — POSTs /api/expense-add-tax and takes the new amount from the
 *             answer. The rate and the arithmetic belong to
 *             finance/sales_tax.py; a rate hard-coded in a browser script is a
 *             rate that quietly stops matching the one the reports used.
 *
 * Every rule worth testing without a browser lives in
 * ../abstract/verified-transaction-actions.interface.js.
 */

import {
  manualEntryFormRegistry,
  verifiedTransactionRowsRegistry,
} from "../abstract/mounted-widget-registry.js";
import {
  buildAddTaxPayload,
  buildDeletePayload,
  deleteConfirmMessage,
  readRowActionResponse,
  signedAmountAfterTax,
} from "../abstract/verified-transaction-actions.interface.js";
import { FetchHttpClient } from "./fetch-http-client.js";

/** Below this many rows the review dialog is already showing the only row. */
const EDIT_NEEDS_SIBLINGS = 2;

/** How long Edit waits for the review dialog to finish mounting. */
const FORM_MOUNT_TIMEOUT_MS = 5000;

export class VerifiedTransactionRows {
  /**
   * @param {{
   *   http: object,
   *   table: Element,
   *   doc?: Document,
   *   formRegistry?: object,
   *   confirm?: (message: string) => Promise<boolean>,
   * }} opts
   */
  constructor({
    http,
    table,
    doc = globalThis.document,
    formRegistry = manualEntryFormRegistry,
    confirm = null,
  }) {
    if (!table) throw new TypeError("VerifiedTransactionRows requires a table");
    if (!http)
      throw new TypeError("VerifiedTransactionRows requires an http client");
    this.http = http;
    this.table = table;
    this.doc = doc;
    this._formRegistry = formRegistry;
    this._confirm = confirm || ((message) => this._askConfirmation(message));
  }

  /** Bind every row's buttons and hang a status line under the table. */
  mount() {
    this._statusEl = this.doc.createElement("div");
    this._statusEl.className = "manual-entry-status vt-row-status";
    this.table.parentElement?.appendChild(this._statusEl);
    for (const button of this.table.querySelectorAll("[data-vt-action]")) {
      // Bound on the button, not delegated from the table: the <tr> carries an
      // inline onclick that opens the category picker, and a delegated handler
      // would run after it had already fired.
      button.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        this._run(button.dataset.vtAction, button.closest("tr"));
      });
    }
    this._syncEditVisibility();
    verifiedTransactionRowsRegistry.publish(this);
    return this;
  }

  /** Repaint every value a successful Save All may have changed. */
  updateExpense(record, vendorKey = "") {
    const row = this._rows().find(
      (candidate) => this._expenseId(candidate) === Number(record?.id),
    );
    if (!row || !record) return false;
    const signedAmount = signedAmountAfterTax(
      row.dataset.signedAmount,
      record.totalAmount,
    );
    row.dataset.description = record.description || "";
    row.dataset.date = record.transactionDate || "";
    row.dataset.vendorKey = vendorKey || row.dataset.vendorKey || "";
    row.dataset.signedAmount = signedAmount;
    const descriptionCell = row.querySelector("td");
    const amountCell = row.querySelector("td.number");
    const dateCell = row.querySelector("td.vt-date");
    const categoryCell = row.querySelector("td.category-cell");
    if (descriptionCell) descriptionCell.textContent = record.description || "";
    if (amountCell) amountCell.textContent = signedAmount;
    if (dateCell) dateCell.textContent = record.transactionDate || "";
    if (categoryCell)
      categoryCell.textContent = record.categoryName || "Uncategorized";
    return true;
  }

  /** Append a newly stored expense to the table without reloading the page. */
  addExpense(record, vendorKey = "") {
    if (
      !record ||
      this._rows().some((row) => this._expenseId(row) === Number(record.id))
    )
      return false;
    const body = this.table.querySelector("tbody");
    if (!body) return false;
    const row = this.doc.createElement("tr");
    const amount = Number(record.totalAmount).toFixed(2);
    Object.assign(row.dataset, {
      expenseId: String(record.id),
      vendorKey: vendorKey || "",
      idLight: record.idLight || "",
      description: record.description || "",
      signedAmount: amount,
      date: record.transactionDate || "",
    });
    row.title = "Click row to set category / view receipt";
    row.addEventListener("click", () => globalThis.openCategoryPicker?.(row));
    const cells = [
      [record.description || "", ""],
      [amount, "number"],
      [record.transactionDate || "", "vt-date"],
      [record.categoryName || "Uncategorized", "category-cell"],
    ];
    for (const [text, className] of cells) {
      const cell = this.doc.createElement("td");
      cell.textContent = text;
      cell.className = className;
      if (className === "category-cell") cell.dataset.categoryCell = "true";
      row.appendChild(cell);
    }
    const actions = this.doc.createElement("td");
    actions.className = "vt-actions";
    const group = this.doc.createElement("div");
    group.className = "vt-action-group";
    for (const [action, label] of [
      ["edit", "Edit"],
      ["delete", "Delete"],
      ["add-tax", "Add 6%"],
    ]) {
      const button = this.doc.createElement("button");
      button.type = "button";
      button.className = "vt-action";
      button.dataset.vtAction = action;
      button.textContent = label;
      button.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        this._run(action, row);
      });
      group.appendChild(button);
    }
    actions.appendChild(group);
    row.appendChild(actions);
    body.querySelector("tr:not([data-expense-id])")?.remove();
    body.appendChild(row);
    this._syncEditVisibility();
    return true;
  }

  _run(action, row) {
    if (!row) return;
    if (action === "edit") return this._edit(row);
    if (action === "delete") return this._delete(row);
    if (action === "add-tax") return this._addTax(row);
  }

  _expenseId(row) {
    return Number(row.dataset.expenseId);
  }

  /** Rows still on the page, in the order they are drawn. */
  _rows() {
    // Every body row carries the id and no header row does, so the attribute
    // alone identifies them -- no descendant selector needed.
    return Array.from(this.table.querySelectorAll("tr[data-expense-id]"));
  }

  /**
   * Edit disappears when a single transaction is left -- the review dialog is
   * already showing it, so the button would be a verb that does nothing. Run
   * on mount and again after every deletion, because a three-row page becomes
   * a one-row page by deleting two.
   */
  _syncEditVisibility() {
    const enough = this._rows().length >= EDIT_NEEDS_SIBLINGS;
    for (const button of this.table.querySelectorAll(
      '[data-vt-action="edit"]',
    )) {
      button.style.display = enough ? "" : "none";
    }
  }

  async _edit(row) {
    const form = await this._formRegistry.whenMounted({
      timeoutMs: FORM_MOUNT_TIMEOUT_MS,
    });
    if (!form) {
      this._setStatus("The expense dialog is not on this page.");
      return;
    }
    if (!form.selectExpenseById(this._expenseId(row))) {
      // A row the dialog never seeded -- e.g. one stored by an earlier
      // document. Say so rather than silently leaving the dialog where it was.
      this._setStatus(
        `Expense #${this._expenseId(row)} is not one of this document's ` +
          "findings, so the dialog cannot walk to it.",
      );
      return;
    }
    this._setStatus("");
    form.root?.scrollIntoView?.({ behavior: "smooth", block: "start" });
  }

  async _delete(row) {
    const description = row.dataset.description || "";
    if (!(await this._confirm(deleteConfirmMessage(description)))) return;
    const expenseId = this._expenseId(row);
    const result = readRowActionResponse(
      await this._post("/api/expense-delete", buildDeletePayload(expenseId)),
    );
    if (!result.ok) {
      this._setStatus(`Could not delete: ${result.error}`);
      return;
    }
    // The table and the dialog drop the row together. Doing one without the
    // other is what leaves "Expense 3 of 3" pointing at nothing.
    row.remove();
    const form =
      this._formRegistry.current ||
      (await this._formRegistry.whenMounted({
        timeoutMs: FORM_MOUNT_TIMEOUT_MS,
      }));
    form?.dropExpenseById(expenseId);
    this._syncEditVisibility();
    // The table is the count that matters here: it is what the operator can
    // see, and the dialog only ever holds the subset it was seeded with.
    this._setStatus(
      `Deleted ${description || `expense #${expenseId}`} — ` +
        `${this._rows().length} left.`,
    );
  }

  async _addTax(row) {
    const expenseId = this._expenseId(row);
    const result = readRowActionResponse(
      await this._post("/api/expense-add-tax", buildAddTaxPayload(expenseId)),
    );
    if (!result.ok) {
      this._setStatus(`Could not add sales tax: ${result.error}`);
      return;
    }
    const amount = signedAmountAfterTax(
      row.dataset.signedAmount,
      result.record?.total_amount,
    );
    if (amount) {
      // Both the visible cell and the attribute the category picker reads:
      // they are the same number twice, and letting them disagree is how a
      // later receipt lookup stops matching its own row.
      const cell = row.querySelector("td.number");
      if (cell) cell.textContent = amount;
      row.dataset.signedAmount = amount;
      this._formRegistry.current?.updateExpenseAmount(
        expenseId,
        result.record?.total_amount,
      );
    }
    const tax = result.taxAdded;
    this._setStatus(
      tax === null
        ? "Added Michigan sales tax."
        : `Added ${tax.toFixed(2)} Michigan sales tax — now ${amount}.`,
    );
  }

  async _post(url, payload) {
    try {
      return await this.http.postJSON(url, payload);
    } catch (err) {
      // readRowActionResponse turns anything that is not {ok:true} into a
      // refusal, which is the fail-closed answer a dead connection deserves.
      return { ok: false, error: String(err?.message || err) };
    }
  }

  /**
   * "Delete Expense {Description}?" with Yes / Cancel.
   *
   * Not window.confirm(): its buttons say OK and Cancel, cannot be relabelled,
   * and look nothing like the rest of this dialog. Cancel takes focus because
   * the other button cannot be undone.
   */
  _askConfirmation(message) {
    return new Promise((resolve) => {
      const backdrop = this._el("div", { className: "vt-confirm-backdrop" });
      const window_ = this._el("div", { className: "window" });
      backdrop.appendChild(window_);
      const titleBar = this._el("div", { className: "title-bar" });
      titleBar.appendChild(
        this._el("div", {
          className: "title-bar-text",
          text: "Confirm Delete",
        }),
      );
      window_.appendChild(titleBar);
      const body = this._el("div", { className: "window-body" });
      window_.appendChild(body);
      body.appendChild(
        this._el("p", { className: "vt-confirm-message", text: message }),
      );
      const buttons = this._el("div", { className: "vt-confirm-buttons" });
      body.appendChild(buttons);

      let settled = false;
      const close = (answer) => {
        if (settled) return;
        settled = true;
        backdrop.remove();
        resolve(answer);
      };
      const yes = this._el("button", { text: "Yes" });
      yes.type = "button";
      yes.dataset.action = "confirm-yes";
      yes.addEventListener("click", () => close(true));
      buttons.appendChild(yes);
      const cancel = this._el("button", { text: "Cancel" });
      cancel.type = "button";
      cancel.dataset.action = "confirm-cancel";
      cancel.addEventListener("click", () => close(false));
      buttons.appendChild(cancel);
      backdrop.addEventListener("keydown", (event) => {
        if (event.key === "Escape") close(false);
      });

      this.doc.body.appendChild(backdrop);
      cancel.focus?.();
    });
  }

  _setStatus(text) {
    if (this._statusEl) this._statusEl.textContent = text;
  }

  _el(tag, { className, text } = {}) {
    const node = this.doc.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
}

// Guarded so importing this module (e.g. from a bun test) never touches the
// global `document` — bun's test environment has no DOM global at all, unlike
// a browser where this file is loaded via <script type="module">.
if (typeof document !== "undefined") {
  const table = document.getElementById("verified-transactions");
  if (table) {
    new VerifiedTransactionRows({ http: new FetchHttpClient(), table }).mount();
  }
}
