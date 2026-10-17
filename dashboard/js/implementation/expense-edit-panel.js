/**
 * Standalone mount for the "Edit Expense" panel (Recent Report page).
 *
 * The panel itself is ExpenseEditDialog. This file exists only to
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
 * it. Fetched here from the full expense taxonomy, rather than the condensed
 * reporting palette. Exact IDs keep leaf categories intact while editing.
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
    this.categoryNamesById = new Map();
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
      categoryNameForId: (id) =>
        this.categoryNamesById.get(id) ||
        (id ? `Current category unavailable [${id}]` : ""),
      onSelected: (expenseId) => {
        const heading = this.root.querySelector("h2");
        if (heading) heading.textContent = `Editing expense #${expenseId}`;
      },
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

  /** Old spreadsheet/report dates remain accepted, but the ID owns the lookup. */
  async _openRequestedExpense() {
    const expenseId = this._requestedId();
    if (expenseId === null) return;
    const heading = this.root.querySelector("h2");
    if (heading) heading.textContent = `Opening expense #${expenseId}…`;
    try {
      const found = await this.dialog.searchById(expenseId);
      if (heading)
        heading.textContent = found
          ? `Editing expense #${expenseId}`
          : `Expense #${expenseId} not found or could not be loaded. Use Search to try again.`;
    } catch {
      if (heading)
        heading.textContent = `Could not load expense #${expenseId}. Use Search to try again.`;
      this.dialog.setStatusMessage(`Could not load expense #${expenseId}.`);
    }
  }

  _requestedId() {
    const query = new URLSearchParams(
      this.doc?.defaultView?.location?.search || "",
    );
    const value = query.get("expense_id") || "";
    const expenseId = Number(value);
    return /^[1-9]\d*$/.test(value) && Number.isSafeInteger(expenseId)
      ? expenseId
      : null;
  }

  async _loadCategoryNames() {
    try {
      const response = await this.http.getJSON("/api/expense-categories");
      this.categoryNames = readCategoriesResponse(response);
      this.categoryNamesById = new Map(
        (response.categories || [])
          .filter(
            (row) =>
              Number.isSafeInteger(row.id) && typeof row.name === "string",
          )
          .map((row) => [row.id, row.name]),
      );
    } catch {
      // The current ID gets an unavailable option in the dialog, so an
      // outage never silently turns a precise category into unresolved.
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
