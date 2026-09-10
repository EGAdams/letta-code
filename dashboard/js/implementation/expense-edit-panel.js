/**
 * Standalone mount for the "Edit Expense" panel (Recent Report page).
 *
 * The panel itself is ExpenseEditDialog, unchanged. This file exists only to
 * give it a home that does not depend on ManualEntryForm being on the page.
 *
 * Why it needed one: the Save-by-hand form is rendered only while a scan is
 * still needs_human_review, and the Edit Expense button lived inside that
 * form. So the button vanished the moment the scan was saved — the moment
 * correcting a stored row becomes the only thing left to do. Mounting the
 * dialog here, unconditionally (see finance/intake_report_page.py's
 * expense_edit_panel_html), makes it reachable on every report page without
 * putting Save All back on a document that has already been entered.
 *
 * ExpenseEditDialog needs a category list, which the entry form used to hand
 * it. Fetched here from the same endpoint, with the same fallback: dropdowns
 * are a convenience, and a failed fetch must not block an edit.
 */

import { readCategoriesResponse } from "../abstract/manual-entry.interface.js";
import { ExpenseEditDialog } from "./expense-edit-dialog.js";
import { FetchHttpClient } from "./fetch-http-client.js";

export class ExpenseEditPanel {
  /**
   * @param {{
   *   http: object,
   *   root: Element,
   *   doc?: Document,
   *   EditDialog?: typeof ExpenseEditDialog,
   *   expanded?: boolean,
   * }} opts
   */
  // `globalThis.document` rather than a bare `document`, matching
  // ExpenseEditDialog: bun's test environment has no DOM global, and a bare
  // default would throw before the constructor could check its arguments.
  constructor({
    http,
    root,
    doc = globalThis.document,
    EditDialog = ExpenseEditDialog,
    expanded = false,
  }) {
    if (!root) throw new TypeError("ExpenseEditPanel requires a mount element");
    if (!http) throw new TypeError("ExpenseEditPanel requires an http client");
    this.http = http;
    this.root = root;
    this.doc = doc;
    this._EditDialog = EditDialog;
    this.expanded = expanded;
    this.categoryNames = [];
  }

  /** Build the launcher, mount the dialog, then load the taxonomy. */
  async mount() {
    // The button gets its own .manual-entry-form box and the dialog is its
    // sibling, exactly as they sit inside the full entry form — the dialog
    // already carries that class itself, so nesting one inside the other
    // would double the Windows 98 border.
    let launcher = null;
    if (!this.expanded) {
      launcher = this._el("div", {
        className: "manual-entry-form expense-edit-launcher",
      });
      this.root.appendChild(launcher);
      const button = this._el("button", { text: "Edit Expense" });
      button.type = "button";
      button.dataset.action = "edit-expense";
      launcher.appendChild(button);
      this.toggleButton = button;
    }

    this.dialog = new this._EditDialog({
      http: this.http,
      root: this.root,
      doc: this.doc,
      // A getter, not a snapshot: the fetch below resolves after render().
      categoryNames: () => this.categoryNames,
    });
    this.dialog.render();
    if (this.toggleButton) {
      this.toggleButton.addEventListener("click", () => {
        this.toggleButton.classList.toggle("is-pressed", this.dialog.toggle());
      });
    } else {
      this.dialog.toggle();
    }

    await this._loadCategoryNames();
    // Categories must be loaded first: _select fills the category dropdown
    // from them, and an empty list would show the row as uncategorized.
    await this._openRequestedExpense();
    return launcher;
  }

  /**
   * Open one expense straight away when the URL names it, e.g.
   * `edit_expense.html?expense_id=2431&date=2025-07-14`.
   *
   * The 2025 daily spreadsheet links every description cell here, so a click
   * in Excel lands on that row with its fields populated and editable.
   *
   * `date` is required because /api/expense-search takes filing criteria, not
   * an id -- searchByDate loads that day, then the id picks the row out of it.
   * Callers that have the id have the date too, so this stays a link rather
   * than a new endpoint.
   */
  async _openRequestedExpense() {
    const params = this._requestedParams();
    if (!params) return;
    const { expenseId, date } = params;
    try {
      const records = await this.dialog.searchByDate(date);
      if (!records.some((record) => record.id === expenseId)) {
        this.dialog.setStatusMessage(
          `Expense #${expenseId} is not among the ${records.length} stored on ${date}. ` +
            "It may have been deleted, or the spreadsheet may be out of date.",
        );
        return;
      }
      this.dialog.selectStoredExpense(expenseId);
    } catch {
      // A failed deep link must still leave a usable panel to search by hand.
      this.dialog.setStatusMessage(`Could not load expense #${expenseId}.`);
    }
  }

  /** @returns {{expenseId: number, date: string} | null} */
  _requestedParams() {
    const search = this.doc?.defaultView?.location?.search;
    if (!search) return null;
    const query = new URLSearchParams(search);
    const expenseId = Number.parseInt(query.get("expense_id") ?? "", 10);
    const date = (query.get("date") ?? "").trim();
    if (!Number.isInteger(expenseId) || expenseId <= 0) return null;
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return null;
    return { expenseId, date };
  }

  async _loadCategoryNames() {
    try {
      this.categoryNames = readCategoriesResponse(
        await this.http.getJSON("/api/rol-finance-categories"),
      );
    } catch {
      // Same call and same fallback as the entry form's _loadDropdownOptions:
      // a failed fetch just leaves the category dropdown empty, which is a
      // worse edit, not a blocked one.
      this.categoryNames = [];
    }
  }

  _el(tag, { className, text } = {}) {
    const node = this.doc.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
}

// Guarded so importing this module (e.g. from a bun test) never touches the
// global `document` — bun's test environment has no DOM global at all,
// unlike a browser where this file is loaded via <script type="module">.
if (typeof document !== "undefined") {
  const root = document.getElementById("expense-edit-root");
  // ManualEntryForm builds its own Edit Expense button and its own dialog. On
  // a needs_human_review page both mount points are present, and mounting
  // here too would put two of each on the page.
  if (root && !document.getElementById("manual-entry-root")) {
    new ExpenseEditPanel({
      http: new FetchHttpClient(),
      root,
      expanded: root.dataset.expanded === "true",
    }).mount();
  }
}
