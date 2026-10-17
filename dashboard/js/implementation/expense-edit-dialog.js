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
  buildNeighborPayload,
  buildSearchPayload,
  describeEditResult,
  formatRecordLabel,
  readEditResponse,
  readNeighborResponse,
  readSearchResponse,
  recordToFields,
  validateSearchCriteria,
} from "../abstract/expense-edit.interface.js";
import {
  formatAmountForDisplay,
  validateManualEntry,
} from "../abstract/manual-entry.interface.js";
import {
  buildDeletePayload,
  deleteConfirmMessage,
  readRowActionResponse,
} from "../abstract/verified-transaction-actions.interface.js";
import { ExpenseCategoryPicker } from "./expense-category-picker.js";

const NO_CATEGORY_OPTION = "";

export class ExpenseEditDialog {
  /**
   * @param {{
   *   http: object,
   *   root: Element,
   *   doc?: Document,
   *   categoryNames?: () => string[],
   *   categoryNameForId?: (id: number | null) => string,
   *   onSaved?: (result: object) => void,
   *   onSelected?: (expenseId: number) => void,
   *   onDeleted?: (expenseId: number) => void,
   *   confirm?: (message: string) => boolean,
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
    categoryNameForId = () => "",
    onSaved,
    onSelected,
    onDeleted,
    confirm = (message) => globalThis.confirm(message),
    alert = (message) => globalThis.alert(message),
    openUrl = (url) => globalThis.open?.(url, "_blank", "noopener,noreferrer"),
  }) {
    if (!root)
      throw new TypeError("ExpenseEditDialog requires a mount element");
    if (!http) throw new TypeError("ExpenseEditDialog requires an http client");
    this.http = http;
    this.root = root;
    this.doc = doc;
    this._openUrl = openUrl;
    // A getter, not a snapshot: the form reloads its taxonomy after a save
    // that remembered a new vendor, and this panel must see the same list.
    this._categoryNames = categoryNames || (() => []);
    this._categoryNameForId = categoryNameForId;
    this._onSaved = onSaved || (() => {});
    // Lets an outside quick-lookup (the manual-entry form's "Expense #" box)
    // stay in sync when a record is picked from this panel's own search
    // results, not just when picked through the outside caller's own UI.
    this._onSelected = onSelected || (() => {});
    this._onDeleted = onDeleted || (() => {});
    this._confirm = confirm;
    this._alert = alert;
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
    this.expenseIdInput = this._field(search, "Expense ID", "text");
    this.dateFromInput = this._field(search, "From date", "date");
    this.dateToInput = this._field(search, "To date", "date");
    this.amountInput = this._field(search, "Amount", "text");
    this.searchButton = this._button(search, "Search", "expense-search");
    this.searchButton.addEventListener("click", () => this._search());

    // Enter in any search field acts like pressing Search, same as a normal
    // browser form submit -- but these inputs aren't inside a <form>, so that
    // behaviour has to be wired explicitly.
    for (const input of [
      this.merchantInput,
      this.expenseIdInput,
      this.dateFromInput,
      this.dateToInput,
      this.amountInput,
    ]) {
      input.addEventListener("keydown", (event) => {
        if (event.key !== "Enter") return;
        event.preventDefault();
        this._search();
      });
    }

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

    // Mazda-captured, not operator-editable: no ExpenseEdit field carries a
    // correction for these back to the server, so this is display only. The
    // map link itself is a same-size "Show Map" button rather than a text
    // link -- it opens in a new tab on click, same destination as before.
    const mileageWrap = this._el("div", {
      className: "manual-entry-field expense-edit-mileage-row",
    });
    this.editEl.appendChild(mileageWrap);
    this.showMapButton = this._button(
      mileageWrap,
      "Show Map",
      "expense-edit-show-map",
    );
    this.showMapButton.classList.add("expense-edit-fixed-size-button");
    this.showMapButton.addEventListener("click", () => this._showMap());

    const distanceWrap = this._el("div", { className: "manual-entry-field" });
    mileageWrap.appendChild(distanceWrap);
    distanceWrap.appendChild(this._el("label", { text: "Distance" }));
    this.editDistanceEl = this._el("input");
    this.editDistanceEl.type = "number";
    this.editDistanceEl.step = "0.1";
    this.editDistanceEl.min = "0";
    distanceWrap.appendChild(this.editDistanceEl);
    // Mileage is always 2x Distance -- never a separate thing to type in.
    this.editDistanceEl.addEventListener("input", () =>
      this._recomputeMileage(),
    );

    const mileageValueWrap = this._el("div", {
      className: "manual-entry-field",
    });
    mileageWrap.appendChild(mileageValueWrap);
    mileageValueWrap.appendChild(this._el("label", { text: "Mileage" }));
    this.editMileageValueEl = this._el("input", {
      className: "expense-edit-mileage-value",
    });
    this.editMileageValueEl.type = "text";
    this.editMileageValueEl.readOnly = true;
    mileageValueWrap.appendChild(this.editMileageValueEl);

    // Also Mazda-captured today, but unlike Address/Distance this one *is*
    // operator-editable -- a wrong or missing map link should be fixable
    // without re-running intake. Saved through Save Changes like Distance.
    const mapLinkWrap = this._el("div", { className: "manual-entry-field" });
    this.editEl.appendChild(mapLinkWrap);
    mapLinkWrap.appendChild(this._el("label", { text: "Map Link" }));
    this.editMapLinkInput = this._el("input");
    this.editMapLinkInput.type = "text";
    this.editMapLinkInput.className = "manual-entry-field-wide";
    mapLinkWrap.appendChild(this.editMapLinkInput);

    const categoryWrap = this._el("div", { className: "manual-entry-field" });
    this.editEl.appendChild(categoryWrap);
    categoryWrap.appendChild(this._el("label", { text: "Category" }));
    this.editCategorySelect = this._el("select");
    this.editCategorySelect.dataset.field = "editCategoryName";
    categoryWrap.appendChild(this.editCategorySelect);
    this.categoryPicker = new ExpenseCategoryPicker({
      http: this.http,
      doc: this.doc,
      root: categoryWrap,
      select: this.editCategorySelect,
      categoryNames: this._categoryNames,
      description: () => this.editMerchantInput.value,
    });

    // Same purpose as the Add Expense page's Notes field, and the same
    // /api/save-expense-notes endpoint -- but this row is already stored, so
    // _select preloads whatever is already on the record (see ExpenseRecord's
    // `notes` field), and Save only re-POSTs it when the box no longer
    // matches what was loaded.
    const notesWrap = this._el("div", { className: "manual-entry-field" });
    this.editEl.appendChild(notesWrap);
    notesWrap.appendChild(this._el("label", { text: "Notes" }));
    this.editNotesInput = this._el("textarea");
    this.editNotesInput.dataset.field = "editNotes";
    this.editNotesInput.rows = 3;
    this.editNotesInput.className = "manual-entry-field-wide";
    notesWrap.appendChild(this.editNotesInput);

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
    this.saveButton.classList.add("expense-edit-fixed-size-button");
    this.saveButton.addEventListener("click", () => this._save());
    this.deleteButton = this._button(
      this.editEl,
      "Delete Expense",
      "expense-edit-delete",
    );
    this.deleteButton.addEventListener("click", () => this._delete());

    // Walks the whole `expenses` table by id, not the current search
    // results -- these labels say "Record", not "Match", on purpose.
    const editNav = this._el("div", { className: "expense-edit-nav" });
    this.editEl.appendChild(editNav);
    this.prevButton = this._button(editNav, "Prev Record", "expense-edit-prev");
    this.prevButton.addEventListener("click", () => this._navigate("prev"));
    this.nextButton = this._button(editNav, "Next Record", "expense-edit-next");
    this.nextButton.addEventListener("click", () => this._navigate("next"));

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
      expenseId: this.expenseIdInput.value,
      merchant: this.merchantInput.value,
      dateFrom: this.dateFromInput.value,
      dateTo: this.dateToInput.value,
      amount: this.amountInput.value,
    };
  }

  /** Open an exact ID through the same validated search used by the form. */
  async searchById(expenseId) {
    this.expenseIdInput.value = String(expenseId);
    for (const input of [
      this.merchantInput,
      this.dateFromInput,
      this.dateToInput,
      this.amountInput,
    ]) {
      input.value = "";
    }
    await this._search({ alertMissing: false });
    return this.selectedId === expenseId;
  }

  async _search({ alertMissing = true } = {}) {
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
      const wantedId = Number.parseInt(criteria.expenseId, 10);
      if (Number.isInteger(wantedId) && wantedId > 0) {
        const match = result.records.find((r) => r.id === wantedId);
        if (match) {
          this._select(match.id);
          return;
        }
        this._setStatus("Expense not found.");
        if (alertMissing) this._alert("Expense not found.");
        return;
      }
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

  /** Public alias for _setStatus -- lets a caller outside this panel explain
   * why it could not select a record, in the same line the panel uses for its
   * own messages (the deep link from the daily spreadsheet). */
  setStatusMessage(text) {
    this._setStatus(text);
  }

  /** Same ordering _renderResults draws on screen -- the one list Prev/Next
   * and the results panel must agree on. */
  _sortedRecords() {
    return [...this.records].sort((a, b) => b.totalAmount - a.totalAmount);
  }

  /**
   * Step to the previous or next row across the *whole* expenses table, by
   * id -- not the current search results. Each click is a fresh lookup, so
   * this keeps working past the edge of whatever this.records happens to
   * hold.
   * @param {"prev"|"next"} direction
   */
  async _navigate(direction) {
    if (this.selectedId === null) {
      this._setStatus("Pick a row from the search results first.");
      return;
    }
    const button = direction === "prev" ? this.prevButton : this.nextButton;
    button.disabled = true;
    button.classList.add("is-pressed");
    try {
      const json = await this.http.postJSON(
        "/api/expense-neighbor",
        buildNeighborPayload(this.selectedId, direction),
      );
      const result = readNeighborResponse(json);
      if (!result.ok) {
        this._setStatus(
          direction === "prev"
            ? "Already at the first record."
            : "Already at the last record.",
        );
        return;
      }
      if (!this.records.some((r) => r.id === result.record.id)) {
        this.records = [...this.records, result.record];
      }
      this._select(result.record.id);
    } catch (err) {
      this._setStatus(`Navigation request failed: ${this._message(err)}`);
    } finally {
      button.disabled = false;
      button.classList.remove("is-pressed");
    }
  }

  _renderResults() {
    this.resultsEl.innerHTML = "";
    const sorted = this._sortedRecords();
    for (const record of sorted) {
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
    this.categoryPicker.close();
    const fields = recordToFields(record);
    this.editMerchantInput.value = fields.merchantName;
    this.editDateInput.value = fields.transactionDate;
    this.editAmountInput.value = fields.totalAmount;
    this._renderMileageDetail(record);
    this.editMapLinkInput.value = record.mapLink || "";
    this._renderCategoryOptions();
    const exactName =
      this.categoryPicker.nameForId(record.categoryId) ||
      this._categoryNameForId(record.categoryId);
    const categoryName = exactName || fields.categoryName;
    if (
      exactName &&
      !Array.from(this.editCategorySelect.children).some(
        (option) => option.value === exactName,
      )
    ) {
      const unavailable = this._el("option", { text: exactName });
      unavailable.value = exactName;
      this.editCategorySelect.appendChild(unavailable);
    }
    this.categoryPicker.setValue(
      exactName || this.categoryPicker.names().includes(categoryName)
        ? categoryName
        : NO_CATEGORY_OPTION,
    );
    this.editNotesInput.value = record.notes;
    // The baseline Save compares the box against, so re-saving without
    // touching Notes never fires a spurious write, but clearing it out is
    // still recognized as a real change to save.
    this._loadedNotes = record.notes;
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
      distanceMiles: this.editDistanceEl.value,
      mapLink: this.editMapLinkInput.value,
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
    let editSucceeded = false;
    try {
      const result = readEditResponse(
        await this.http.postJSON("/api/expense-edit", payload),
      );
      this._setStatus(
        [describeEditResult(result), ...result.warnings].join(" "),
      );
      if (result.ok) {
        editSucceeded = true;
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
      return;
    } finally {
      this.saveButton.disabled = false;
      this.saveButton.classList.remove("is-pressed");
    }
    const notes = this.editNotesInput.value.trim();
    if (editSucceeded && notes !== this._loadedNotes) {
      await this._saveNotes(this.selectedId, notes);
      this._loadedNotes = notes;
    }
  }

  /** Best-effort: the corrected expense itself is already saved either way. */
  async _saveNotes(expenseId, notes) {
    try {
      await this.http.postJSON("/api/save-expense-notes", {
        expense_id: expenseId,
        notes,
      });
    } catch {
      // Same posture as ManualEntryForm's own _saveNotes on the Add Expense
      // page -- a confirmation nicety on top of an already-successful save.
    }
  }

  /** Delete the currently-picked row — the dialog's other write path. */
  async _delete() {
    if (this.selectedId === null) {
      this._setStatus("Pick a row from the search results first.");
      return;
    }
    const record = this.records.find((r) => r.id === this.selectedId);
    const description = record ? record.description : "";
    if (!this._confirm(deleteConfirmMessage(description))) return;
    const expenseId = this.selectedId;
    this.deleteButton.disabled = true;
    this.deleteButton.classList.add("is-pressed");
    this._setStatus("Deleting…");
    try {
      const result = readRowActionResponse(
        await this.http.postJSON(
          "/api/expense-delete",
          buildDeletePayload(expenseId),
        ),
      );
      if (!result.ok) {
        this._setStatus(`Could not delete: ${result.error}`);
        return;
      }
      this.records = this.records.filter((r) => r.id !== expenseId);
      this.selectedId = null;
      this.editEl.style.display = "none";
      this.errorsEl.textContent = "";
      this._renderResults();
      this._setStatus(`Deleted ${description || `expense #${expenseId}`}.`);
      this._onDeleted(expenseId);
    } catch (err) {
      this._setStatus(`Delete request failed: ${this._message(err)}`);
    } finally {
      this.deleteButton.disabled = false;
      this.deleteButton.classList.remove("is-pressed");
    }
  }

  _renderCategoryOptions() {
    this.categoryPicker.renderOptions();
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

  /**
   * Fills the Show Map button, Distance, and Mileage controls. The address
   * itself is no longer shown -- the button is self-explanatory. Distance is
   * operator-editable and saved through Save Changes; Mileage is always
   * derived from it (one leg vs. the IRS's round-trip figure), never typed in.
   */
  _renderMileageDetail(record) {
    this._mapLink = record.mapLink || null;
    this.showMapButton.disabled = !this._mapLink;
    this.editDistanceEl.value =
      record.distanceMiles === null ? "" : record.distanceMiles.toFixed(1);
    this._recomputeMileage();
  }

  _recomputeMileage() {
    const distance = Number(this.editDistanceEl.value);
    this.editMileageValueEl.value =
      this.editDistanceEl.value !== "" && Number.isFinite(distance)
        ? `${(distance * 2).toFixed(1)} mi`
        : "";
  }

  _showMap() {
    if (!this._mapLink) return;
    this._openUrl(this._mapLink);
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
