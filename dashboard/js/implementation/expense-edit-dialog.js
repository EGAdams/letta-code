/**
 * The "Edit Expense" panel that sits beside Save All on the Recent Report page.
 *
 * Save All inserts; this corrects. Search for an already-stored row (by
 * merchant, date range, or amount), pick it, fix the fields, save. It is a
 * separate piece rather than a mode bolted onto ManualEntryForm on purpose:
 * the insert path is the one that must not regress, and "add new behaviour as
 * a new part instead of re-opening working code" is the rule this project
 * follows.
 *
 * Every decision — what counts as a searchable criteria set, what a response
 * is allowed to contain, whether an edit is submittable — lives in
 * ../abstract/expense-edit.interface.js. This class is DOM + injected HTTP
 * only, and builds its tree with createElement so it stays testable against
 * js/tests/_fake-dom.js.
 */

import {
  blankSearchCriteria,
  buildEditPayload,
  buildSearchPayload,
  describeEditResult,
  formatRecordLabel,
  readEditResponse,
  readSearchResponse,
  recordToFields,
  validateSearchCriteria,
} from "../abstract/expense-edit.interface.js";
import {
  formatAmountForDisplay,
  validateManualEntry,
} from "../abstract/manual-entry.interface.js";

const NO_CATEGORY_OPTION = "";

export class ExpenseEditDialog {
  /**
   * @param {{
   *   http: object,
   *   root: Element,
   *   doc?: Document,
   *   categoryNames?: () => string[],
   *   onSaved?: (result: object) => void,
   *   onSelected?: (expenseId: number) => void,
   * }} opts
   */
  // `globalThis.document` rather than a bare `document`: bun's test
  // environment has no DOM global at all, and a bare default would be a
  // ReferenceError before the constructor could reject its arguments.
  constructor({
    http,
    root,
    doc = globalThis.document,
    categoryNames,
    onSaved,
    onSelected,
  }) {
    if (!root)
      throw new TypeError("ExpenseEditDialog requires a mount element");
    if (!http) throw new TypeError("ExpenseEditDialog requires an http client");
    this.http = http;
    this.root = root;
    this.doc = doc;
    // A getter, not a snapshot: the form reloads its taxonomy after a save
    // that remembered a new vendor, and this panel must see the same list.
    this._categoryNames = categoryNames || (() => []);
    this._onSaved = onSaved || (() => {});
    // Lets an outside quick-lookup (the manual-entry form's "Expense #" box)
    // stay in sync when a record is picked from this panel's own search
    // results, not just when picked through the outside caller's own UI.
    this._onSelected = onSelected || (() => {});
    this.records = [];
    this.selectedId = null;
    this.isOpen = false;
  }

  /** Build the (initially hidden) panel. Safe to call once, at mount time. */
  render() {
    this.panel = this._el("div", {
      className: "manual-entry-form expense-edit-panel",
    });
    this.panel.style.display = "none";
    this.panel.appendChild(this._el("h2", { text: "Edit a saved expense" }));

    const search = this._el("div", { className: "manual-entry-item-nav" });
    this.panel.appendChild(search);
    this.merchantInput = this._field(search, "Merchant contains", "text");
    this.dateFromInput = this._field(search, "From date", "date");
    this.dateToInput = this._field(search, "To date", "date");
    this.amountInput = this._field(search, "Amount", "text");
    this.searchButton = this._button(search, "Search", "expense-search");
    this.searchButton.addEventListener("click", () => this._search());

    this.resultsEl = this._el("div", { className: "expense-edit-results" });
    this.panel.appendChild(this.resultsEl);

    this.editEl = this._el("div", { className: "expense-edit-fields" });
    this.editEl.style.display = "none";
    this.panel.appendChild(this.editEl);
    this.editMerchantInput = this._field(
      this.editEl,
      "Merchant / description",
      "text",
    );
    this.editDateInput = this._field(this.editEl, "Date", "date");
    this.editAmountInput = this._field(this.editEl, "Amount", "text");

    const categoryWrap = this._el("div", { className: "manual-entry-field" });
    this.editEl.appendChild(categoryWrap);
    categoryWrap.appendChild(this._el("label", { text: "Category" }));
    this.editCategorySelect = this._el("select");
    this.editCategorySelect.dataset.field = "editCategoryName";
    categoryWrap.appendChild(this.editCategorySelect);

    this.editAmountInput.addEventListener("blur", () => {
      this.editAmountInput.value = formatAmountForDisplay(
        this.editAmountInput.value,
      );
    });

    this.errorsEl = this._el("div", { className: "manual-entry-errors" });
    this.editEl.appendChild(this.errorsEl);
    this.saveButton = this._button(
      this.editEl,
      "Save Changes",
      "expense-edit-save",
    );
    this.saveButton.addEventListener("click", () => this._save());

    this.statusEl = this._el("div", { className: "manual-entry-status" });
    this.panel.appendChild(this.statusEl);
    this.root.appendChild(this.panel);
    return this.panel;
  }

  /** Show/hide the panel — what the "Edit Expense" button is wired to. */
  toggle() {
    this.isOpen = !this.isOpen;
    this.panel.style.display = this.isOpen ? "" : "none";
    if (this.isOpen) this._renderCategoryOptions();
    return this.isOpen;
  }

  _readCriteria() {
    return {
      ...blankSearchCriteria(),
      merchant: this.merchantInput.value,
      dateFrom: this.dateFromInput.value,
      dateTo: this.dateToInput.value,
      amount: this.amountInput.value,
    };
  }

  async _search() {
    const criteria = this._readCriteria();
    const check = validateSearchCriteria(criteria);
    if (!check.valid) {
      this._setStatus(Object.values(check.errors).join(" "));
      return;
    }
    this.searchButton.disabled = true;
    this.searchButton.classList.add("is-pressed");
    this._setStatus("Searching…");
    try {
      const json = await this.http.postJSON(
        "/api/expense-search",
        buildSearchPayload(criteria),
      );
      const result = readSearchResponse(json);
      if (!result.ok) {
        this._setStatus(`Search failed: ${result.error}`);
        return;
      }
      this._setRecords(result.records);
      this._setStatus(
        result.records.length
          ? `${result.records.length} match(es). Pick one to edit.`
          : "No stored expenses matched those criteria.",
      );
    } catch (err) {
      this._setStatus(`Search request failed: ${this._message(err)}`);
    } finally {
      this.searchButton.disabled = false;
      this.searchButton.classList.remove("is-pressed");
    }
  }

  /**
   * Replace the result list, dropping a selection the new results no longer
   * contain. Both search paths go through here: leaving a stale selectedId
   * behind meant the edit fields kept showing the previously-picked row after
   * a fresh search, so Save would silently correct a row the operator was no
   * longer looking at. A row still present in the new results stays selected,
   * since re-finding what you are editing is not a surprise.
   * @param {import("../abstract/expense-edit.interface.js").ExpenseRecord[]} records
   */
  _setRecords(records) {
    this.records = records;
    if (
      this.selectedId !== null &&
      !records.some((r) => r.id === this.selectedId)
    ) {
      this.selectedId = null;
      this.editEl.style.display = "none";
      this.errorsEl.textContent = "";
    }
    this._renderResults();
  }

  /**
   * Search by a single date (dateFrom === dateTo), for callers outside this
   * panel's own search form -- the manual-entry form's quick "Expense #"
   * lookup reuses this rather than duplicating the search/response handling.
   * Updates this.records/this.resultsEl the same as the panel's own Search
   * button, so the two stay in sync. Returns the matched records.
   * @param {string} date ISO yyyy-mm-dd
   * @returns {Promise<import("../abstract/expense-edit.interface.js").ExpenseRecord[]>}
   */
  async searchByDate(date) {
    const criteria = { ...blankSearchCriteria(), dateFrom: date, dateTo: date };
    if (!validateSearchCriteria(criteria).valid) return [];
    try {
      const result = readSearchResponse(
        await this.http.postJSON(
          "/api/expense-search",
          buildSearchPayload(criteria),
        ),
      );
      if (!result.ok) return [];
      this._setRecords(result.records);
      return result.records;
    } catch {
      return [];
    }
  }

  /** Public alias for _select -- the entry point for a caller outside this
   * panel (the manual-entry form's date-search dropdown) picking a record
   * that is already in this.records. */
  selectStoredExpense(expenseId) {
    this._select(expenseId);
  }

  _renderResults() {
    this.resultsEl.innerHTML = "";
    for (const record of this.records) {
      const button = this._el("button", { text: formatRecordLabel(record) });
      button.type = "button";
      button.dataset.action = "expense-pick";
      button.dataset.expenseId = String(record.id);
      button.addEventListener("click", () => this._select(record.id));
      this.resultsEl.appendChild(button);
    }
  }

  _select(expenseId) {
    const record = this.records.find((r) => r.id === expenseId);
    if (!record) return;
    this.selectedId = record.id;
    const fields = recordToFields(record);
    this.editMerchantInput.value = fields.merchantName;
    this.editDateInput.value = fields.transactionDate;
    this.editAmountInput.value = fields.totalAmount;
    this._renderCategoryOptions();
    this.editCategorySelect.value = this._categoryNames().includes(
      fields.categoryName,
    )
      ? fields.categoryName
      : NO_CATEGORY_OPTION;
    this.editEl.style.display = "";
    this.errorsEl.textContent = "";
    this._setStatus(`Editing expense #${record.id}.`);
    this._onSelected(record.id);
  }

  _editedFields() {
    return {
      merchantName: this.editMerchantInput.value,
      transactionDate: this.editDateInput.value,
      totalAmount: this.editAmountInput.value,
      categoryName: this.editCategorySelect.value,
    };
  }

  async _save() {
    if (this.selectedId === null) {
      this._setStatus("Pick a row from the search results first.");
      return;
    }
    const fields = this._editedFields();
    const check = validateManualEntry(fields);
    if (!check.valid) {
      this.errorsEl.textContent = Object.values(check.errors).join(" ");
      return;
    }
    this.errorsEl.textContent = "";
    const payload = buildEditPayload(this.selectedId, fields);
    if (!payload) {
      this._setStatus("Those values cannot be saved.");
      return;
    }
    this.saveButton.disabled = true;
    this.saveButton.classList.add("is-pressed");
    this._setStatus("Saving changes…");
    try {
      const result = readEditResponse(
        await this.http.postJSON("/api/expense-edit", payload),
      );
      this._setStatus(
        [describeEditResult(result), ...result.warnings].join(" "),
      );
      if (result.ok) {
        // The list still shows the pre-edit values; refreshing it from the
        // saved record keeps a second edit of the same row honest.
        if (result.record) {
          this.records = this.records.map((r) =>
            r.id === result.record.id ? result.record : r,
          );
          this._renderResults();
        }
        this._onSaved(result);
      }
    } catch (err) {
      this._setStatus(`Edit request failed: ${this._message(err)}`);
    } finally {
      this.saveButton.disabled = false;
      this.saveButton.classList.remove("is-pressed");
    }
  }

  _renderCategoryOptions() {
    const selected = this.editCategorySelect.value;
    this.editCategorySelect.innerHTML = "";
    const blank = this._el("option", { text: "— leave unresolved —" });
    blank.value = NO_CATEGORY_OPTION;
    this.editCategorySelect.appendChild(blank);
    for (const name of this._categoryNames()) {
      const option = this._el("option", { text: name });
      option.value = name;
      this.editCategorySelect.appendChild(option);
    }
    this.editCategorySelect.value = selected;
  }

  _field(parent, labelText, type) {
    const wrap = this._el("div", { className: "manual-entry-field" });
    parent.appendChild(wrap);
    wrap.appendChild(this._el("label", { text: labelText }));
    const input = this._el("input");
    input.type = type;
    wrap.appendChild(input);
    return input;
  }

  _button(parent, text, action) {
    const button = this._el("button", { text });
    button.type = "button";
    button.dataset.action = action;
    parent.appendChild(button);
    return button;
  }

  _el(tag, { className, text } = {}) {
    const node = this.doc.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  _message(err) {
    return err && err.message ? err.message : String(err);
  }

  _setStatus(text) {
    this.statusEl.textContent = text;
  }
}
