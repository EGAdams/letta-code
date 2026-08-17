/**
 * The needs_human_review Save-by-hand form (Recent Report page).
 *
 * Mounts into #manual-entry-root (see finance/intake_report_page.py's
 * manual_entry_form_html) whenever MAZDA_DECISION_MODE=human_only routed a
 * scan/PDF to a human instead of Mazda. "Prefill from OCR" runs the same
 * local-only OCR pass parse_and_categorize.py always runs before saving, so
 * the operator edits/confirms rather than typing from a blank page; Save
 * stores through the identical tool Mazda's own pipeline uses. A document
 * can hold more than one expense (e.g. two receipts scanned together) — Prev
 * / Next / Add Another Expense cycle through a list of line items, each
 * independently valid, submitted together by Save All.
 *
 * All field/response validation lives in
 * ../abstract/manual-entry.interface.js so it is testable without a browser.
 * This class builds its DOM via createElement/appendChild rather than an
 * innerHTML template string — matching statement-review-dialog.js's house
 * style — specifically so it stays unit-testable against js/tests/_fake-dom.js,
 * whose innerHTML setter (correctly) does not parse markup into a queryable
 * tree the way a real browser does.
 */

import {
  buildArchiveVerifyCommand,
  readArchivePathResponse,
} from "../abstract/archive-verify-command.js";
import {
  ARCHIVE_KIND,
  blankManualEntryFields,
  buildArchivePreviewPayload,
  buildPreviewPayload,
  buildSubmitPayload,
  defaultArchiveKind,
  formatAmountForDisplay,
  PREVIEW_ENGINE,
  readArchivePreviewResponse,
  readCategoriesResponse,
  readPrefillResponse,
  readSubmitResponse,
  readVendorKeysResponse,
  validateManualEntry,
} from "../abstract/manual-entry.interface.js";
import { mountTerminal } from "./detail-renderers.js";
import { ExpenseEditDialog } from "./expense-edit-dialog.js";
import { FetchHttpClient } from "./fetch-http-client.js";

const NEW_VENDOR_OPTION = "__new__";
const NO_CATEGORY_OPTION = "";

export class ManualEntryForm {
  /**
   * @param {{http: object, root: Element, doc?: Document, mountTerminal?: Function}} opts
   */
  constructor({
    http,
    root,
    doc = document,
    mountTerminal: mountTerminalFn = mountTerminal,
    EditDialog = ExpenseEditDialog,
  }) {
    if (!root) throw new TypeError("ManualEntryForm requires a mount element");
    this.http = http;
    this.root = root;
    this.doc = doc;
    this._mountTerminal = mountTerminalFn;
    this._EditDialog = EditDialog;
    this.conversationId = root.dataset.conversationId || "";
    this.scannerKey = root.dataset.scannerKey || "";
    this.items = [blankManualEntryFields()];
    this.currentIndex = 0;
    this.vendorOptions = [];
    this.categoryNames = [];
    this.archiveKind = defaultArchiveKind(this.items.length);
    this._archiveKindManuallySet = false;
    this.customArchiveRoot = "";
  }

  async mount() {
    this.root.innerHTML = "";
    const shell = this.doc.createElement("div");
    shell.className = "manual-entry-form";

    const imagePathWrap = this._el("div", { className: "manual-entry-field" });
    shell.appendChild(imagePathWrap);
    imagePathWrap.appendChild(this._el("label", { text: "Image path" }));
    this.imagePathInput = this._el("input");
    this.imagePathInput.type = "text";
    // Full-width like .manual-entry-archive-path (a path is exactly the kind
    // of value the 320px cap on ordinary fields was too narrow for).
    this.imagePathInput.classList.add("manual-entry-field-wide");
    this.imagePathInput.placeholder =
      "/home/adamsl/rol_finances/tools/receipt_scanning_tools/incoming_scans";
    this.imagePathInput.value = this.root.dataset.imagePath || "";
    imagePathWrap.appendChild(this.imagePathInput);
    this.showImageButton = this._button(
      imagePathWrap,
      "Show Image",
      "show-image",
    );
    // Auto-detected means "from this scanner's own staged scan" -- there's no
    // scanner for a PDF-kind intake (scannerKey is "" there, see
    // manual_entry_form_html's docstring), so there's nothing this button can
    // open.
    this.showImageButton.disabled = !this.scannerKey;
    this.showImageButton.addEventListener("click", () => {
      const win = this.doc.defaultView || globalThis;
      win.open(
        `/api/intake-document?scanner=${encodeURIComponent(this.scannerKey)}`,
        "_blank",
      );
    });

    this.prefillButton = this._button(shell, "Prefill from OCR", "prefill");
    this.prefillButton.addEventListener("click", () =>
      this._prefill(PREVIEW_ENGINE.LOCAL, this.prefillButton, "local OCR"),
    );

    // Opt-in only -- unlike "Prefill from OCR" (zero-token, always safe to
    // run automatically), this spends a Gemini Flash free-tier call, so it
    // stays a separate button the operator chooses per EG's request rather
    // than folding into the local pass.
    this.geminiFillButton = this._button(
      shell,
      "Gemini Flash Fill",
      "gemini-fill",
    );
    this.geminiFillButton.addEventListener("click", () =>
      this._prefill(
        PREVIEW_ENGINE.GEMINI_ONLY,
        this.geminiFillButton,
        "Gemini Flash",
      ),
    );

    const nav = this._el("div", { className: "manual-entry-item-nav" });
    shell.appendChild(nav);
    const prevButton = this._button(nav, "← Prev", "prev");
    prevButton.addEventListener("click", () => this._navigate(-1));
    this._positionEl = this._el("span", { text: "" });
    nav.appendChild(this._positionEl);
    const nextButton = this._button(nav, "Next →", "next");
    nextButton.addEventListener("click", () => this._navigate(1));
    const addButton = this._button(nav, "+ Add Another Expense", "add-item");
    addButton.addEventListener("click", () => this._addItem());

    const vendorWrap = this._el("div", { className: "manual-entry-field" });
    shell.appendChild(vendorWrap);
    vendorWrap.appendChild(this._el("label", { text: "Merchant / vendor" }));
    this.vendorSelect = this._el("select");
    this.vendorSelect.dataset.field = "vendorSelect";
    vendorWrap.appendChild(this.vendorSelect);
    this.merchantNameInput = this._el("input");
    this.merchantNameInput.type = "text";
    this.merchantNameInput.placeholder = "Type or pick above";
    this.merchantNameInput.dataset.field = "merchantName";
    vendorWrap.appendChild(this.merchantNameInput);
    // Shown only when OCR's merchant name matched several stored vendors that
    // disagree about the category. Nothing is prefilled in that case, so this
    // is how the operator resolves it -- see readVendorCandidates.
    this._vendorCandidatesEl = this._el("div", {
      className: "manual-entry-vendor-candidates",
    });
    this._vendorCandidatesEl.style.display = "none";
    vendorWrap.appendChild(this._vendorCandidatesEl);

    this.transactionDateInput = this._labeledInput(shell, "Date", {
      type: "date",
    });
    this.totalAmountInput = this._labeledInput(shell, "Amount", {
      type: "text",
    });

    const categoryWrap = this._el("div", { className: "manual-entry-field" });
    shell.appendChild(categoryWrap);
    categoryWrap.appendChild(this._el("label", { text: "Category" }));
    this.categorySelect = this._el("select");
    this.categorySelect.dataset.field = "categoryName";
    categoryWrap.appendChild(this.categorySelect);

    const archiveKindWrap = this._el("div", {
      className: "manual-entry-field",
    });
    shell.appendChild(archiveKindWrap);
    archiveKindWrap.appendChild(this._el("label", { text: "File as" }));
    this.archiveKindSelect = this._el("select");
    for (const [value, text] of [
      [ARCHIVE_KIND.RECEIPT, "Receipt"],
      [ARCHIVE_KIND.SCANNED_DOCUMENT, "Scanned Documents"],
      [ARCHIVE_KIND.OTHER, "Other folder (type below)"],
    ]) {
      const opt = this._el("option", { text });
      opt.value = value;
      this.archiveKindSelect.appendChild(opt);
    }
    archiveKindWrap.appendChild(this.archiveKindSelect);
    this.customArchiveRootInput = this._el("input");
    this.customArchiveRootInput.type = "text";
    this.customArchiveRootInput.placeholder = "/path/to/folder";
    this.customArchiveRootInput.style.display = "none";
    archiveKindWrap.appendChild(this.customArchiveRootInput);

    const archivePreviewWrap = this._el("div", {
      className: "manual-entry-field",
    });
    shell.appendChild(archivePreviewWrap);
    archivePreviewWrap.appendChild(
      this._el("label", { text: "Will be filed as" }),
    );
    this._archivePathEl = this._el("div", {
      className: "manual-entry-archive-path",
    });
    archivePreviewWrap.appendChild(this._archivePathEl);

    this._errorsEl = this._el("div", { className: "manual-entry-errors" });
    shell.appendChild(this._errorsEl);
    const saveButton = this._button(shell, "Save All", "save-all");
    saveButton.addEventListener("click", () => this._saveAll());
    // Save All only ever inserts. Editing an already-saved row is a different
    // job, so it gets its own panel (ExpenseEditDialog) rather than a mode
    // switch inside this form's save path.
    const editButton = this._button(shell, "Edit Expense", "edit-expense");
    editButton.addEventListener("click", () => {
      editButton.classList.toggle("is-pressed", this.editDialog.toggle());
    });

    // Quick expense lookup, next to Edit Expense: shows the number of
    // whichever stored expense is currently loaded in the Edit panel (if
    // any), or -- via the date search -- swaps that number box for a
    // dropdown of that date's expense numbers. Picking one loads it into
    // the Edit panel the same way clicking a search result there does.
    const expenseLookupWrap = this._el("div", {
      className: "manual-entry-item-nav",
    });
    shell.appendChild(expenseLookupWrap);
    expenseLookupWrap.appendChild(this._el("label", { text: "Expense #" }));
    this.currentExpenseInput = this._el("input");
    this.currentExpenseInput.type = "text";
    this.currentExpenseInput.readOnly = true;
    expenseLookupWrap.appendChild(this.currentExpenseInput);
    this.expenseDateResultsSelect = this._el("select");
    this.expenseDateResultsSelect.style.display = "none";
    expenseLookupWrap.appendChild(this.expenseDateResultsSelect);
    expenseLookupWrap.appendChild(
      this._el("label", { text: "Search by date" }),
    );
    this.expenseDateSearchInput = this._el("input");
    this.expenseDateSearchInput.type = "date";
    expenseLookupWrap.appendChild(this.expenseDateSearchInput);

    this.expenseDateSearchInput.addEventListener("change", () =>
      this._searchExpensesByDate(),
    );
    this.expenseDateResultsSelect.addEventListener("change", () => {
      const id = Number(this.expenseDateResultsSelect.value);
      if (id) this.editDialog.selectStoredExpense(id);
      this.expenseDateSearchInput.value = "";
      this._showCurrentExpenseNumber();
    });

    this._statusEl = this._el("div", { className: "manual-entry-status" });
    shell.appendChild(this._statusEl);
    this._archiveTerminalEl = this._el("div");
    shell.appendChild(this._archiveTerminalEl);

    this.vendorSelect.addEventListener("change", () => {
      this._applyVendorSelection();
      this._updateArchivePathPreview();
    });
    for (const input of [
      this.merchantNameInput,
      this.transactionDateInput,
      this.totalAmountInput,
    ]) {
      input.addEventListener("input", () => this._captureCurrentItem());
      input.addEventListener("blur", () => this._updateArchivePathPreview());
    }
    // Two decimal places on blur, not on every keystroke -- reformatting
    // "12.5" to "12.50" while the operator is still typing "12.50" would
    // fight them for the cursor.
    this.totalAmountInput.addEventListener("blur", () => {
      this.totalAmountInput.value = formatAmountForDisplay(
        this.totalAmountInput.value,
      );
      this._captureCurrentItem();
    });
    this.categorySelect.addEventListener("change", () =>
      this._captureCurrentItem(),
    );
    this.archiveKindSelect.addEventListener("change", () => {
      this.archiveKind = this.archiveKindSelect.value;
      this._archiveKindManuallySet = true;
      this.customArchiveRootInput.style.display =
        this.archiveKind === ARCHIVE_KIND.OTHER ? "" : "none";
      this._updateArchivePathPreview();
    });
    this.customArchiveRootInput.addEventListener("blur", () => {
      this.customArchiveRoot = this.customArchiveRootInput.value;
      this._updateArchivePathPreview();
    });

    this.archiveKindSelect.value = this.archiveKind;
    this.root.appendChild(shell);

    // Constructed here, not in the constructor, so it mounts into the same
    // root and reads the taxonomy this form loads below -- one fetch of
    // /api/rol-finance-categories serves both panels.
    this.editDialog = new this._EditDialog({
      http: this.http,
      root: this.root,
      doc: this.doc,
      categoryNames: () => this.categoryNames,
      onSelected: () => this._showCurrentExpenseNumber(),
    });
    this.editDialog.render();
    this._showCurrentExpenseNumber();

    await this._loadDropdownOptions();
    this._renderCurrentItem();
  }

  async _searchExpensesByDate() {
    const date = this.expenseDateSearchInput.value;
    if (!date) {
      this._showCurrentExpenseNumber();
      return;
    }
    const records = await this.editDialog.searchByDate(date);
    this._renderExpenseDateResults(records);
  }

  _renderExpenseDateResults(records) {
    this.expenseDateResultsSelect.innerHTML = "";
    if (!records.length) {
      const opt = this._el("option", { text: "No expenses on that date" });
      opt.value = "";
      this.expenseDateResultsSelect.appendChild(opt);
    } else {
      for (const record of records) {
        const opt = this._el("option", { text: `#${record.id}` });
        opt.value = String(record.id);
        this.expenseDateResultsSelect.appendChild(opt);
      }
    }
    this.currentExpenseInput.style.display = "none";
    this.expenseDateResultsSelect.style.display = "";
  }

  _showCurrentExpenseNumber() {
    this.expenseDateResultsSelect.style.display = "none";
    this.currentExpenseInput.style.display = "";
    this.currentExpenseInput.value = this.editDialog.selectedId
      ? `#${this.editDialog.selectedId}`
      : "";
  }

  _el(tag, { className, text } = {}) {
    const node = this.doc.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  _labeledInput(parent, labelText, { type }) {
    const wrap = this._el("div", { className: "manual-entry-field" });
    parent.appendChild(wrap);
    const label = this._el("label", { text: labelText });
    wrap.appendChild(label);
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

  async _loadDropdownOptions() {
    try {
      const [vendorJson, categoryJson] = await Promise.all([
        this.http.getJSON("/api/vendor-keys"),
        this.http.getJSON("/api/rol-finance-categories"),
      ]);
      this.vendorOptions = readVendorKeysResponse(vendorJson);
      this.categoryNames = readCategoriesResponse(categoryJson);
    } catch {
      // Dropdowns are a convenience; a failed fetch just leaves the operator
      // typing the merchant name and category by hand, same as before.
      this.vendorOptions = [];
      this.categoryNames = [];
    }
    this._renderVendorOptions();
    this._renderCategoryOptions();
  }

  _renderVendorOptions() {
    this.vendorSelect.innerHTML = "";
    const blank = this._el("option", { text: "— pick a known vendor —" });
    blank.value = "";
    this.vendorSelect.appendChild(blank);
    for (const opt of this.vendorOptions) {
      const el = this._el("option", { text: opt.vendorKey });
      el.value = opt.vendorKey;
      this.vendorSelect.appendChild(el);
    }
    const addNew = this._el("option", {
      text: "+ Add new vendor (type below)",
    });
    addNew.value = NEW_VENDOR_OPTION;
    this.vendorSelect.appendChild(addNew);
  }

  _renderCategoryOptions() {
    this.categorySelect.innerHTML = "";
    const blank = this._el("option", { text: "— leave unresolved —" });
    blank.value = NO_CATEGORY_OPTION;
    this.categorySelect.appendChild(blank);
    for (const name of this.categoryNames) {
      const el = this._el("option", { text: name });
      el.value = name;
      this.categorySelect.appendChild(el);
    }
  }

  _applyVendorSelection() {
    const value = this.vendorSelect.value;
    if (!value || value === NEW_VENDOR_OPTION) return;
    this.merchantNameInput.value = value;
    const match = this.vendorOptions.find((opt) => opt.vendorKey === value);
    if (
      match &&
      match.categoryName &&
      this.categoryNames.includes(match.categoryName)
    ) {
      this.categorySelect.value = match.categoryName;
    }
    this._captureCurrentItem();
  }

  /**
   * Preselect the vendor dropdown/category from an OCR prefill's vendor
   * match, without touching merchantNameInput -- unlike _applyVendorSelection
   * (a manual dropdown pick), OCR already put a human-readable name there
   * ("Consumers Energy"), which reads better than overwriting it with the
   * vendor_key slug.
   * @param {import("../abstract/manual-entry.interface.js").ManualEntryPrefill} prefill
   * @returns {boolean} whether anything was matched
   */
  _applyVendorMatch(prefill) {
    let matched = false;
    if (
      prefill.vendorKey &&
      this.vendorOptions.some((opt) => opt.vendorKey === prefill.vendorKey)
    ) {
      this.vendorSelect.value = prefill.vendorKey;
      matched = true;
    }
    if (
      prefill.categoryName &&
      this.categoryNames.includes(prefill.categoryName)
    ) {
      this.categorySelect.value = prefill.categoryName;
      matched = true;
    }
    return matched;
  }

  /**
   * Render the "which of these vendors is it?" choices for an ambiguous
   * prefill, or clear them. Returns whether any were shown.
   * @param {import("../abstract/manual-entry.interface.js").ManualEntryPrefill} prefill
   * @returns {boolean}
   */
  _renderVendorCandidates(prefill) {
    this._vendorCandidatesEl.innerHTML = "";
    const candidates = prefill.vendorCandidates || [];
    if (!prefill.vendorAmbiguous || !candidates.length) {
      this._vendorCandidatesEl.style.display = "none";
      return false;
    }
    this._vendorCandidatesEl.style.display = "";
    this._vendorCandidatesEl.appendChild(
      this._el("label", {
        text: `"${prefill.merchantName || "This vendor"}" matches ${candidates.length} stored vendors — pick the right one:`,
      }),
    );
    for (const candidate of candidates) {
      const button = this._el("button", {
        text: `${candidate.vendorKey} — ${candidate.categoryName || "Uncategorized"}`,
      });
      button.type = "button";
      button.dataset.action = "vendor-candidate";
      button.dataset.vendorKey = candidate.vendorKey;
      button.addEventListener("click", () =>
        this._chooseVendorCandidate(candidate),
      );
      this._vendorCandidatesEl.appendChild(button);
    }
    return true;
  }

  /**
   * Apply one operator-chosen candidate. This is the only path that resolves
   * an ambiguous vendor -- the server deliberately refuses to pick one, so a
   * human choice is what turns it into a real answer.
   * @param {import("../abstract/manual-entry.interface.js").VendorOption} candidate
   */
  _chooseVendorCandidate(candidate) {
    if (
      this.vendorOptions.some((opt) => opt.vendorKey === candidate.vendorKey)
    ) {
      this.vendorSelect.value = candidate.vendorKey;
    }
    this.merchantNameInput.value = candidate.vendorKey;
    if (
      candidate.categoryName &&
      this.categoryNames.includes(candidate.categoryName)
    ) {
      this.categorySelect.value = candidate.categoryName;
    }
    this._captureCurrentItem();
    this._renderVendorCandidates({ vendorAmbiguous: false });
    this._setStatus(
      `Vendor set to ${candidate.vendorKey}${candidate.categoryName ? ` (${candidate.categoryName})` : ""}.`,
    );
    this._updateArchivePathPreview();
  }

  _currentItem() {
    return this.items[this.currentIndex];
  }

  _captureCurrentItem() {
    this.items[this.currentIndex] = {
      merchantName: this.merchantNameInput.value,
      transactionDate: this.transactionDateInput.value,
      totalAmount: this.totalAmountInput.value,
      categoryName: this.categorySelect.value,
    };
  }

  _renderCurrentItem() {
    const item = this._currentItem();
    this.merchantNameInput.value = item.merchantName;
    this.transactionDateInput.value = item.transactionDate;
    this.totalAmountInput.value = formatAmountForDisplay(item.totalAmount);
    this.categorySelect.value = this.categoryNames.includes(item.categoryName)
      ? item.categoryName
      : NO_CATEGORY_OPTION;
    this.vendorSelect.value = this.vendorOptions.some(
      (opt) => opt.vendorKey === item.merchantName,
    )
      ? item.merchantName
      : "";
    this._positionEl.textContent = `Expense ${this.currentIndex + 1} of ${this.items.length}`;
    this._renderErrors({});
  }

  _navigate(delta) {
    this._captureCurrentItem();
    const next = this.currentIndex + delta;
    if (next < 0 || next >= this.items.length) return;
    this.currentIndex = next;
    this._renderCurrentItem();
    this._updateArchivePathPreview();
  }

  _addItem() {
    this._captureCurrentItem();
    this.items.push(blankManualEntryFields());
    this.currentIndex = this.items.length - 1;
    if (!this._archiveKindManuallySet) {
      this.archiveKind = defaultArchiveKind(this.items.length);
      this.archiveKindSelect.value = this.archiveKind;
    }
    this._renderCurrentItem();
    this._updateArchivePathPreview();
  }

  /**
   * @param {string} engine one of PREVIEW_ENGINE's values
   * @param {HTMLButtonElement} button the button that triggered this pass,
   *   for the pressed/disabled state -- so the *other* prefill button stays
   *   clickable while this one is in flight
   * @param {string} sourceLabel human-readable name for status messages
   */
  async _prefill(
    engine = PREVIEW_ENGINE.LOCAL,
    button = this.prefillButton,
    sourceLabel = "local OCR",
  ) {
    button.disabled = true;
    button.classList.add("is-pressed");
    this._setStatus(`Reading with ${sourceLabel}…`);
    try {
      const json = await this.http.postJSON(
        "/api/manual-receipt-entry-preview",
        buildPreviewPayload({ imagePath: this.imagePathInput.value }, engine),
      );
      const prefill = readPrefillResponse(json);
      if (prefill.merchantName)
        this.merchantNameInput.value = prefill.merchantName;
      if (prefill.transactionDate)
        this.transactionDateInput.value = prefill.transactionDate;
      if (prefill.totalAmount !== null)
        this.totalAmountInput.value = formatAmountForDisplay(
          String(prefill.totalAmount),
        );
      const vendorMatched = this._applyVendorMatch(prefill);
      const needsVendorChoice = this._renderVendorCandidates(prefill);
      this._captureCurrentItem();
      this._setStatus(
        prefill.ok
          ? `Prefilled from ${sourceLabel} — check every field before saving.` +
              (vendorMatched ? " Vendor/category matched too." : "") +
              (needsVendorChoice
                ? " More than one stored vendor answers to this name, so no" +
                  " vendor or category was guessed — pick one below."
                : "")
          : `${sourceLabel} could not read this document (${prefill.error || "no result"}); fields left blank.`,
      );
    } catch (err) {
      this._setStatus(
        `Prefill request failed: ${err && err.message ? err.message : err}`,
      );
    } finally {
      button.disabled = false;
      button.classList.remove("is-pressed");
    }
    // The archive path is built from vendor+date+amount -- refresh it the
    // moment OCR has (or hasn't) filled those in, per EG's request, rather
    // than waiting for the operator to blur a field.
    await this._updateArchivePathPreview();
  }

  async _updateArchivePathPreview() {
    const intakeRef = {
      imagePath: this.imagePathInput.value,
      conversationId: this.conversationId,
    };
    const payload = buildArchivePreviewPayload(
      this._currentItem(),
      intakeRef,
      this.archiveKind,
      this.customArchiveRoot,
    );
    if (!payload) {
      this._archivePathEl.textContent =
        "(pick a vendor, date, and amount to preview)";
      return;
    }
    try {
      const json = await this.http.postJSON(
        "/api/manual-receipt-entry-archive-preview",
        payload,
      );
      const result = readArchivePreviewResponse(json);
      if (!result.ok) {
        this._archivePathEl.textContent = `Could not compute a path: ${result.error}`;
        return;
      }
      this._archivePathEl.textContent = result.isRealDestination
        ? result.path
        : `${result.path} (preview only — Save always files under the Receipts archive today)`;
    } catch (err) {
      this._archivePathEl.textContent = `Path preview failed: ${err && err.message ? err.message : err}`;
    }
  }

  async _saveAll() {
    this._captureCurrentItem();
    const invalidIndex = this.items.findIndex(
      (item) => !validateManualEntry(item).valid,
    );
    if (invalidIndex !== -1) {
      this.currentIndex = invalidIndex;
      this._renderCurrentItem();
      this._renderErrors(validateManualEntry(this.items[invalidIndex]).errors);
      this._setStatus(
        `Fix expense ${invalidIndex + 1} of ${this.items.length} before saving.`,
      );
      return;
    }
    const intakeRef = {
      imagePath: this.imagePathInput.value,
      conversationId: this.conversationId,
    };
    const results = [];
    for (let i = 0; i < this.items.length; i++) {
      this._setStatus(`Saving ${i + 1} of ${this.items.length}…`);
      try {
        const json = await this.http.postJSON(
          "/api/manual-receipt-entry",
          buildSubmitPayload(this.items[i], intakeRef),
        );
        results.push(readSubmitResponse(json));
      } catch (err) {
        results.push({
          ok: false,
          error: err && err.message ? err.message : String(err),
        });
      }
    }
    const failed = results.filter((r) => !r.ok);
    if (failed.length) {
      this._setStatus(
        `${results.length - failed.length} of ${results.length} saved; ` +
          `${failed.length} failed: ${failed.map((f) => f.error).join("; ")}`,
      );
      return;
    }
    let statusText = `All ${results.length} expense(s) saved.`;
    const newVendorKeys = results
      .map((r) => r.vendorRemembered)
      .filter((v) => v && v.remembered && v.vendorKey)
      .map((v) => v.vendorKey);
    if (newVendorKeys.length) {
      statusText += ` Remembered new vendor(s): ${newVendorKeys.join(", ")}.`;
      // The dropdown was built from the /api/vendor-keys snapshot at mount
      // time, before this save added to vendor_category.yaml -- reload it
      // now so the vendor just typed is immediately pickable, not just on
      // the next page load.
      await this._loadDropdownOptions();
      this._renderCurrentItem();
    }
    this._setStatus(statusText);
    await this._showArchiveVerification();
    this._showReloadButton();
  }

  _showReloadButton() {
    const button = this._el("button", {
      text: "Reload page (shows in Verified Transactions)",
    });
    button.type = "button";
    button.addEventListener("click", () => this.doc.location.reload());
    this._statusEl.appendChild(this.doc.createElement("br"));
    this._statusEl.appendChild(button);
  }

  async _showArchiveVerification() {
    if (!this.scannerKey) return;
    try {
      const json = await this.http.postJSON("/api/scanner-archive-path", {
        scanner: this.scannerKey,
      });
      const result = readArchivePathResponse(json);
      if (!result.ok) return;
      this._archiveTerminalEl.innerHTML = "";
      this._archiveTerminalEl.appendChild(
        this._el("h3", {
          text: `Archive Verification (${result.archivePath})`,
        }),
      );
      const hostEl = this._el("div", { className: "terminal-host" });
      this._archiveTerminalEl.appendChild(hostEl);
      const session = await this._mountTerminal({
        hostEl,
        doc: this.doc,
        onStatus: () => {},
      });
      if (session && session.sendLine) {
        session.sendLine(
          buildArchiveVerifyCommand(result.archivePath, result.archiveName),
        );
      }
    } catch {
      // Archive verification is a confirmation nicety on top of an already
      // successful save -- a failure here must never look like the save failed.
    }
  }

  _renderErrors(errors) {
    this._errorsEl.textContent = Object.values(errors).join(" ");
  }

  _setStatus(text) {
    this._statusEl.textContent = text;
  }
}

// Guarded so importing this module (e.g. from a bun test) never touches the
// global `document` — bun's test environment has no DOM global at all,
// unlike a browser where this file is loaded directly via <script type="module">.
if (typeof document !== "undefined") {
  const root = document.getElementById("manual-entry-root");
  if (root) {
    new ManualEntryForm({ http: new FetchHttpClient(), root }).mount();
  }
}
