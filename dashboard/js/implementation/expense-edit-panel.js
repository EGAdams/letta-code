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
  }) {
    if (!root) throw new TypeError("ExpenseEditPanel requires a mount element");
    if (!http) throw new TypeError("ExpenseEditPanel requires an http client");
    this.http = http;
    this.root = root;
    this.doc = doc;
    this._EditDialog = EditDialog;
    this.categoryNames = [];
  }

  /** Build the launcher, mount the dialog, then load the taxonomy. */
  async mount() {
    // The button gets its own .manual-entry-form box and the dialog is its
    // sibling, exactly as they sit inside the full entry form — the dialog
    // already carries that class itself, so nesting one inside the other
    // would double the Windows 98 border.
    const launcher = this._el("div", {
      className: "manual-entry-form expense-edit-launcher",
    });
    this.root.appendChild(launcher);
    const button = this._el("button", { text: "Edit Expense" });
    button.type = "button";
    button.dataset.action = "edit-expense";
    launcher.appendChild(button);
    this.toggleButton = button;

    this.dialog = new this._EditDialog({
      http: this.http,
      root: this.root,
      doc: this.doc,
      // A getter, not a snapshot: the fetch below resolves after render().
      categoryNames: () => this.categoryNames,
    });
    this.dialog.render();
    button.addEventListener("click", () => {
      button.classList.toggle("is-pressed", this.dialog.toggle());
    });

    await this._loadCategoryNames();
    return launcher;
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
    new ExpenseEditPanel({ http: new FetchHttpClient(), root }).mount();
  }
}
