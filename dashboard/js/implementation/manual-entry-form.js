/**
 * The Save-by-hand / review dialog (Recent Report page).
 *
 * Mounts into #manual-entry-root (see finance/intake_report_page.py's
 * manual_entry_form_html) on every intake report, in either mode. It used to
 * appear only when MAZDA_DECISION_MODE=human_only had routed a scan/PDF to a
 * human — i.e. only while Mazda was switched off — so switching her back on
 * took the review dialog away with her. Those are separate questions: the
 * switch in this form's top row decides who READS the next document, and this
 * form is where a human CHECKS what was read. A document can hold more than one
 * expense (two receipts scanned together, a statement page) — Prev / Next /
 * Add Another Expense cycle through a list of line items, each independently
 * valid, submitted together by Save All.
 *
 * SEMI-AUTOMATIC exposes three explicit reading jobs: Circled Only calculates
 * marked rows, Total Only asks for the three form fields, and Several Expenses
 * invokes the forensic document parser. Each is a Command backed by an
 * injected server-side Strategy; nothing is stored until Save / Save All.
 *
 * All field/response validation lives in ../abstract/manual-entry.interface.js,
 * ../abstract/statement-breakup.interface.js and
 * ../abstract/receipt-read.interface.js so it is testable without a browser.
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
  buildEditPayload,
  describeEditResult,
  readEditResponse,
} from "../abstract/expense-edit.interface.js";
import {
  ARCHIVE_KIND,
  blankManualEntryFields,
  buildArchivePreviewPayload,
  buildSubmitPayload,
  defaultArchiveKind,
  formatAmountForDisplay,
  readArchivePreviewResponse,
  readCategoriesResponse,
  readStoredFindings,
  readSubmitResponse,
  readVendorKeysResponse,
  validateManualEntry,
} from "../abstract/manual-entry.interface.js";
import {
  buildMazdaModePayload,
  mazdaModeLabel,
  readMazdaModeDataset,
  readMazdaModeResponse,
  summarizeMazdaMode,
} from "../abstract/mazda-mode.interface.js";
import {
  manualEntryFormRegistry,
  verifiedTransactionRowsRegistry,
} from "../abstract/mounted-widget-registry.js";
import {
  buildReceiptReadPayload,
  FILL_SHAPE,
  RECEIPT_READ_INTENT,
  readReceiptReadResponse,
  receiptReadAction,
  receiptReadModelLabel,
  summarizeReceiptReread,
} from "../abstract/receipt-read.interface.js";
import {
  buildStatementEntryPayload,
  readStatementEntryResponse,
  summarizeExcludedStatementRows,
  summarizeStatementStore,
  validateStatementRow,
} from "../abstract/statement-breakup.interface.js";
import { indexAfterRemoval } from "../abstract/verified-transaction-actions.interface.js";
import { mountTerminal } from "./detail-renderers.js";
import { ExpenseEditDialog } from "./expense-edit-dialog.js";
import { FetchHttpClient } from "./fetch-http-client.js";
import { ReceiptReadControls } from "./receipt-read-controls.js";

const NEW_VENDOR_OPTION = "__new__";
const NO_CATEGORY_OPTION = "";

export class ManualEntryForm {
  /**
   * @param {{http: object, root: Element, doc?: Document, mountTerminal?: Function, delay?: Function}} opts
   */
  constructor({
    http,
    root,
    doc = document,
    mountTerminal: mountTerminalFn = mountTerminal,
    EditDialog = ExpenseEditDialog,
    delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
  }) {
    if (!root) throw new TypeError("ManualEntryForm requires a mount element");
    this.http = http;
    this.root = root;
    this.doc = doc;
    this._mountTerminal = mountTerminalFn;
    this._EditDialog = EditDialog;
    this._delay = delay;
    this.conversationId = root.dataset.conversationId || "";
    this.scannerKey = root.dataset.scannerKey || "";
    // Mazda's own findings for this document (STEP 8's stored rows, stamped
    // server-side onto the mount point) seed the review dialog on an
    // automatic scan instead of leaving it blank -- see
    // finance/intake_report_page.py's manual_entry_form_html docstring. No
    // findings (a human_only intake, or nothing stored yet) falls back to the
    // one blank item this form has always started with.
    const foundItems = readStoredFindings(root.dataset.mazdaFindings);
    this.items = foundItems.length ? foundItems : [blankManualEntryFields()];
    this.currentIndex = 0;
    // null = the ordinary receipt mode this form was built for. Set by "Break
    // Up Document", it holds the one bank/account identity every row on the
    // page shares, and switches Save All to the statement store -- rows off a
    // statement are not receipts and must not be filed as any.
    this.statementHeader = null;
    // Rows the extractor read but flagged as a payment/credit/$0.00 line, not
    // an expense -- never shown on Prev/Next, but still merged back into the
    // statement store submission (see buildStatementSubmitRows), because the
    // store needs the complete page to reach the same verdict itself.
    this.statementExcludedRows = [];
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

    this.receiptReadControls = new ReceiptReadControls({
      doc: this.doc,
      parent: imagePathWrap,
      createButton: (parent, label, action) =>
        this._button(parent, label, action),
      onRead: (intent) => this._readReceipt(intent),
      showImageButton: this.showImageButton,
      rightEdgeButton: () => this.removeButton,
      delay: this._delay,
    }).mount();
    this.mazdaModelSelect = this.receiptReadControls.modelSelect;
    // Compatibility names for the progress-animation tests and CSS. There is
    // deliberately no mazdaFillButton alias: that button no longer exists.
    this.mazdaFillProgressShell = this.receiptReadControls.progressShell;
    this.mazdaFillProgressBar = this.receiptReadControls.progressBar;

    // The Automatic / Semi-Automatic switch follows the reading controls and
    // answers whether the operator needs to choose one for the next scan.
    //
    // It decides who reads the NEXT scanned document — Mazda by herself, or
    // this form waiting for a human. It does nothing to the document already
    // on screen, which is why the status line says so out loud every time
    // (see summarizeMazdaMode): "Automatic" reads as retroactive, and an
    // operator who thinks the page in front of them is about to file itself
    // will wait for something that is never going to happen.
    //
    // The label IS the state — it reads "Mazda Automatic" when she is driving
    // and "Mazda Semi-Automatic" when she is not, rather than naming what a
    // click would do. A switch whose text changes to the thing you are about
    // to get is a switch nobody can read at a glance.
    this.mazdaMode = readMazdaModeDataset(this.root.dataset);
    const modeWrap = this._el("label", { className: "mazda-mode-switch" });
    this.mazdaModeCheckbox = this._el("input");
    this.mazdaModeCheckbox.type = "checkbox";
    this.mazdaModeCheckbox.dataset.field = "mazdaMode";
    this.mazdaModeCheckbox.checked = this.mazdaMode.automatic;
    modeWrap.appendChild(this.mazdaModeCheckbox);
    modeWrap.appendChild(this._el("span", { className: "mazda-mode-track" }));
    this.mazdaModeLabelEl = this._el("span", {
      className: "mazda-mode-label",
      text: this.mazdaMode.label,
    });
    modeWrap.appendChild(this.mazdaModeLabelEl);
    imagePathWrap.appendChild(modeWrap);
    this.mazdaModeCheckbox.addEventListener("change", () =>
      this._setMazdaMode(this.mazdaModeCheckbox.checked),
    );
    this.statementMetadataPrompt = this._el("div", {
      className: "manual-entry-field",
    });
    this.statementMetadataPrompt.style.display = "none";
    imagePathWrap.appendChild(this.statementMetadataPrompt);
    this.statementMetadataPrompt.appendChild(
      this._el("label", { text: "Bank name" }),
    );
    this.statementBankNameInput = this._el("input");
    this.statementBankNameInput.type = "text";
    this.statementMetadataPrompt.appendChild(this.statementBankNameInput);
    this.statementMetadataPrompt.appendChild(
      this._el("label", { text: "Account last 4 digits" }),
    );
    this.statementAccountLast4Input = this._el("input");
    this.statementAccountLast4Input.type = "text";
    this.statementMetadataPrompt.appendChild(this.statementAccountLast4Input);
    this.statementMetadataSubmit = this._button(
      this.statementMetadataPrompt,
      "Submit",
      "statement-metadata-submit",
    );
    // Only ever opened by a statement fill that read every transaction but
    // could not resolve WHOSE account they are. Submit re-runs the same fill
    // with the two typed values, with the same model -- there is one reading
    // flow now, so there is nothing for this to restart by mistake.
    this.statementMetadataSubmit.addEventListener("click", () =>
      this._readReceipt(RECEIPT_READ_INTENT.SEVERAL_EXPENSES, {
        bankName: this.statementBankNameInput.value,
        accountLast4: this.statementAccountLast4Input.value,
      }),
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
    // Breaking up a document produces rows the operator must be able to drop,
    // not just edit: the Choice Privileges page's "Interest Charge on
    // Purchases $0.00" is a real printed line and not an expense, and without
    // this the only ways past it were to invent an amount for it or abandon
    // the whole page.
    this.removeButton = this._button(
      nav,
      "− Remove This Expense",
      "remove-item",
    );
    this.removeButton.addEventListener("click", () => this._removeItem());

    const vendorWrap = this._el("div", { className: "manual-entry-field" });
    shell.appendChild(vendorWrap);
    vendorWrap.appendChild(this._el("label", { text: "Merchant / vendor" }));
    const vendorRow = this._el("div", { className: "manual-entry-vendor-row" });
    vendorWrap.appendChild(vendorRow);
    this.vendorSelect = this._el("select");
    this.vendorSelect.dataset.field = "vendorSelect";
    vendorRow.appendChild(this.vendorSelect);
    this.newVendorKeyWrap = this._el("span", {
      className: "manual-entry-new-vendor-key",
    });
    this.newVendorKeyWrap.appendChild(
      this._el("label", { text: "New Vendor Key" }),
    );
    this.newVendorKeyInput = this._el("input");
    this.newVendorKeyInput.type = "text";
    this.newVendorKeyInput.dataset.field = "newVendorKey";
    this.newVendorKeyWrap.appendChild(this.newVendorKeyInput);
    vendorRow.appendChild(this.newVendorKeyWrap);
    const descriptionWrap = this._el("div", {
      className: "manual-entry-field",
    });
    shell.appendChild(descriptionWrap);
    descriptionWrap.appendChild(this._el("label", { text: "Description" }));
    this.merchantNameInput = this._el("input");
    this.merchantNameInput.type = "text";
    this.merchantNameInput.dataset.field = "merchantName";
    this.merchantNameInput.className = "manual-entry-field-wide";
    descriptionWrap.appendChild(this.merchantNameInput);
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
      this.newVendorKeyInput,
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
    // Published last, when every field and the item list are real: the
    // Verified Transactions table's Edit / Delete buttons drive this form
    // through the three methods below, and handing them a half-built form
    // would let a click land before the inputs exist.
    manualEntryFormRegistry.publish(this);
  }

  /**
   * Show the item holding an already-stored expense, if this form has one.
   *
   * The Verified Transactions table's Edit button. The table's rows and this
   * form's items are two views of the same findings (see
   * intake_report_model.stored_findings), so "load row 2 into the dialog" is
   * really "walk Prev/Next to whichever item carries that expense id" -- the
   * readout between Prev and Next then says "Expense 2 of 3" by itself.
   *
   * @returns {boolean} whether the id was found on this page.
   */
  selectExpenseById(expenseId) {
    const id = Number(expenseId);
    const index = this.items.findIndex((item) => Number(item.expenseId) === id);
    if (index < 0) return false;
    this._captureCurrentItem();
    this.currentIndex = index;
    this._renderCurrentItem();
    this._updateArchivePathPreview();
    return true;
  }

  /**
   * Drop the item holding an already-stored expense, after the row it mirrors
   * has been deleted from the database.
   *
   * Prev/Next has to stay synchronised with what is actually left: a dialog
   * still offering "Expense 3 of 3" for a row that no longer exists would
   * save an edit to nothing. indexAfterRemoval decides where to land -- the
   * one rule here that is worth a unit test, so it lives in
   * ../abstract/verified-transaction-actions.interface.js.
   *
   * @returns {number} how many items remain on screen.
   */
  dropExpenseById(expenseId) {
    const id = Number(expenseId);
    const index = this.items.findIndex((item) => Number(item.expenseId) === id);
    if (index < 0) return this.items.length;
    if (index !== this.currentIndex) this._captureCurrentItem();
    this.items.splice(index, 1);
    const remaining = this.items.length;
    this.currentIndex = indexAfterRemoval(this.currentIndex, index, remaining);
    // Same floor _removeItem keeps: the list never empties, or the operator is
    // left with a form that has no fields and no way back.
    if (!remaining) {
      this.items = [blankManualEntryFields()];
      this.statementHeader = null;
      this.statementExcludedRows = [];
    }
    this._renderCurrentItem();
    this._updateArchivePathPreview();
    return remaining;
  }

  /**
   * Rewrite one item's amount after the server changed it underneath us.
   *
   * "Add 6%" writes through /api/expense-add-tax, so the stored row moves
   * while this form is holding the old figure. Without this, a later Save All
   * on that item would put the pre-tax amount back.
   */
  updateExpenseAmount(expenseId, totalAmount) {
    const id = Number(expenseId);
    const index = this.items.findIndex((item) => Number(item.expenseId) === id);
    if (index < 0) return false;
    if (index === this.currentIndex) this._captureCurrentItem();
    this.items[index] = {
      ...this.items[index],
      totalAmount: formatAmountForDisplay(totalAmount),
    };
    if (index === this.currentIndex) this._renderCurrentItem();
    return true;
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
      text: "Add new vendor",
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
    this._showNewVendorKey(value === NEW_VENDOR_OPTION);
    if (!value || value === NEW_VENDOR_OPTION) {
      this._captureCurrentItem();
      return;
    }
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
    this._showNewVendorKey(false);
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
    // expenseId is metadata about WHICH row this item is, not a typed
    // field -- carried forward from whatever is already in this slot, same
    // as _renderCurrentItem never renders it into an input. Losing it here
    // would silently turn an edit of a seeded (already-stored) finding back
    // into an insert the moment the operator typed anything.
    const expenseId = this.items[this.currentIndex]?.expenseId ?? null;
    this.items[this.currentIndex] = {
      merchantName: this.merchantNameInput.value,
      transactionDate: this.transactionDateInput.value,
      totalAmount: this.totalAmountInput.value,
      categoryName: this.categorySelect.value,
      knownVendorKey: this.vendorSelect.value,
      newVendorKey: this.newVendorKeyInput.value,
      expenseId,
    };
  }

  /**
   * Which vendorSelect option (if any) an item's own knownVendorKey or,
   * failing that, its merchantName text matches -- same precedence
   * _applyVendorMatch uses for an OCR prefill: a stored/duplicate-matched
   * finding already knows its REUSABLE vendor, if any (see
   * finance/intake_report_model.StoredFinding.known_vendor_key -- never the
   * per-transaction filing key every stored expense carries), so that is
   * checked first without touching the human-readable merchant text; a
   * hand-typed item that happens to equal a vendor_key slug still matches
   * the way it always has.
   */
  _knownVendorKeyFor(item) {
    if (
      item.knownVendorKey &&
      this.vendorOptions.some((opt) => opt.vendorKey === item.knownVendorKey)
    ) {
      return item.knownVendorKey;
    }
    return this.vendorOptions.some((opt) => opt.vendorKey === item.merchantName)
      ? item.merchantName
      : "";
  }

  _renderCurrentItem() {
    const item = this._currentItem();
    this.merchantNameInput.value = item.merchantName;
    this.transactionDateInput.value = item.transactionDate;
    this.totalAmountInput.value = formatAmountForDisplay(item.totalAmount);
    this.categorySelect.value = this.categoryNames.includes(item.categoryName)
      ? item.categoryName
      : NO_CATEGORY_OPTION;
    const knownVendorKey = this._knownVendorKeyFor(item);
    const isUnknownFinding = !knownVendorKey && Boolean(item.newVendorKey);
    this.vendorSelect.value = knownVendorKey
      ? knownVendorKey
      : isUnknownFinding
        ? NEW_VENDOR_OPTION
        : "";
    this.newVendorKeyInput.value = isUnknownFinding
      ? item.newVendorKey || ""
      : "";
    this._showNewVendorKey(isUnknownFinding && !knownVendorKey);
    this._positionEl.textContent = this._positionText();
    this._renderErrors({});
  }

  _showNewVendorKey(show) {
    this.newVendorKeyWrap.style.display = show ? "" : "none";
  }

  /**
   * The Prev/Next readout. In statement mode it also names the account every
   * row belongs to: five rows off one page are only meaningful as "five
   * transactions on Choice Privileges 5596", and the operator walking them
   * needs to see they are still on the same statement.
   */
  _positionText() {
    const position = `${this.currentIndex + 1} of ${this.items.length}`;
    if (!this.statementHeader) {
      const item = this._currentItem();
      // Names which endpoint Save All will use for THIS item (see
      // _saveOneItem) -- an operator correcting a seeded finding needs to
      // see it will update the stored row, not file a new one.
      const editing = item.expenseId
        ? ` (editing stored expense #${item.expenseId})`
        : "";
      return `Expense ${position}${editing}`;
    }
    const { bankName, accountLast4 } = this.statementHeader;
    const account = [bankName, accountLast4 ? `****${accountLast4}` : ""]
      .filter(Boolean)
      .join(" ");
    return `Transaction ${position}${account ? ` — ${account}` : ""}`;
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
    // Another expense entered here belongs to this same receipt. Its date is
    // therefore receipt metadata, not a second fact for the operator to type.
    // Prefer the row currently in view, then any dated sibling (the current
    // slot can be a newly-added blank row after a remove/add cycle).
    const receiptDate =
      this._currentItem()?.transactionDate ||
      this.items.find((item) => item.transactionDate)?.transactionDate ||
      "";
    this.items.push({
      ...blankManualEntryFields(),
      transactionDate: receiptDate,
    });
    this.currentIndex = this.items.length - 1;
    if (!this._archiveKindManuallySet) {
      this.archiveKind = defaultArchiveKind(this.items.length);
      this.archiveKindSelect.value = this.archiveKind;
    }
    this._renderCurrentItem();
    this._updateArchivePathPreview();
  }

  /**
   * Drop the row on screen. The list never empties: removing the last one
   * leaves a blank item (and, in statement mode, leaves statement mode) rather
   * than a form with no fields and no way back.
   */
  _removeItem() {
    const removedLabel = this.statementHeader ? "Transaction" : "Expense";
    const removedPosition = this.currentIndex + 1;
    const total = this.items.length;
    this.items.splice(this.currentIndex, 1);
    if (!this.items.length) {
      this.items = [blankManualEntryFields()];
      this.statementHeader = null;
      this.statementExcludedRows = [];
    }
    this.currentIndex = Math.min(this.currentIndex, this.items.length - 1);
    this._renderCurrentItem();
    this._setStatus(
      `Removed ${removedLabel.toLowerCase()} ${removedPosition} of ${total} —` +
        ` ${this.items.length} left to save.`,
    );
    this._updateArchivePathPreview();
  }

  /**
   * Move the switch: who reads the NEXT scanned document.
   *
   * The label follows the click immediately so the control feels like a
   * switch, then is replaced by the server's own label when it answers -- the
   * two agree by construction (MAZDA_MODE_LABELS is mirrored, and pinned by
   * tests/test_mazda_mode.py), so the swap is invisible when it works and
   * corrective when it does not.
   *
   * A failure puts the switch back where it was. A toggle left showing a mode
   * the server is not actually in is worse than one that visibly refused to
   * move: the operator would walk away believing Mazda is on.
   * @param {boolean} automatic
   */
  async _setMazdaMode(automatic) {
    this.mazdaModeCheckbox.disabled = true;
    this.mazdaModeLabelEl.textContent = mazdaModeLabel(automatic);
    try {
      const json = await this.http.postJSON(
        "/api/mazda-mode",
        buildMazdaModePayload(automatic),
      );
      const state = readMazdaModeResponse(json);
      if (state.ok) {
        this.mazdaMode = state;
        this.mazdaModeCheckbox.checked = state.automatic;
        this.mazdaModeLabelEl.textContent = state.label;
      } else {
        this.mazdaModeCheckbox.checked = this.mazdaMode.automatic;
        this.mazdaModeLabelEl.textContent = this.mazdaMode.label;
      }
      this._setStatus(summarizeMazdaMode(state));
    } catch (err) {
      this.mazdaModeCheckbox.checked = this.mazdaMode.automatic;
      this.mazdaModeLabelEl.textContent = this.mazdaMode.label;
      this._setStatus(
        `Could not change the mode: ${err && err.message ? err.message : err}. ` +
          "The switch was put back.",
      );
    } finally {
      this.mazdaModeCheckbox.disabled = false;
    }
  }

  /** Run one declared read Command; the server supplies its Strategy. */
  async _readReceipt(intent, statementMetadata) {
    const model = this.mazdaModelSelect.value;
    const modelLabel = receiptReadModelLabel(model);
    const action = receiptReadAction(intent);
    this.statementMetadataSubmit.disabled = true;
    this.receiptReadControls.begin(intent);
    this._setStatus(`${action.label} is reading this page with ${modelLabel}…`);
    let fillSucceeded = false;
    try {
      const json = await this.http.postJSON(
        "/api/receipt-read",
        buildReceiptReadPayload(
          { imagePath: this.imagePathInput.value },
          intent,
          model,
          statementMetadata,
        ),
        // fetch-http-client.js defaults to 30s. A vision read of a whole
        // statement page is the slowest call this form makes, and a classify
        // pass now runs ahead of it — aborting client-side while the server
        // is still reading would throw away work already paid for.
        { timeout: 180000 },
      );
      const result = readReceiptReadResponse(json);
      if (result.shape === FILL_SHAPE.MANY_EXPENSES) {
        this._applyStatementFill(result, modelLabel);
      } else {
        this._applyReceiptFill(result, modelLabel);
      }
      fillSucceeded = result.ok;
    } catch (err) {
      this._setStatus(
        `${action.label} failed: ${err && err.message ? err.message : err}`,
      );
    } finally {
      await this.receiptReadControls.finish(intent, fillSucceeded);
      this.statementMetadataSubmit.disabled = false;
    }
    // The archive path is built from vendor+date+amount — refresh it the
    // moment the fill has (or hasn't) filled those in, per EG's request,
    // rather than waiting for the operator to blur a field.
    await this._updateArchivePathPreview();
  }

  /** Mazda read ONE expense: fill the three fields and match the vendor. */
  _applyReceiptFill(result, modelLabel) {
    const prefill = result.prefill;
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
    this.statementMetadataPrompt.style.display = "none";
    this._setStatus(
      result.ok
        ? `${modelLabel} read this as ONE expense — check every field before` +
            " saving." +
            (vendorMatched ? " Vendor/category matched too." : "") +
            (needsVendorChoice
              ? " More than one stored vendor answers to this name, so no" +
                " vendor or category was guessed — pick one below."
              : "")
        : `${modelLabel} could not read this document (${
            result.error || "no result"
          }); fields left blank — type them in, or try the other model.`,
    );
  }

  /** Mazda read MANY expenses: hand Prev/Next one row per transaction. */
  _applyStatementFill(result, modelLabel) {
    // Rows first, error second: a needs-metadata answer still carries every
    // transaction, and showing them while the operator types the bank in is
    // the whole reason the response is shaped that way.
    if (result.items.length) this._loadStatementItems(result);
    if (result.needsStatementMetadata) {
      this.statementBankNameInput.value = result.header.bankName;
      this.statementAccountLast4Input.value = result.header.accountLast4;
      this.statementMetadataPrompt.style.display = "";
      this._setStatus(
        `${modelLabel} read ${result.items.length} transaction(s), but the` +
          " bank/account couldn't be resolved automatically (missing: " +
          `${result.missingFields.join(", ") || "bank/account"}) — fill in` +
          " the fields above and Submit before saving." +
          summarizeReceiptReread(result),
      );
      return;
    }
    this.statementMetadataPrompt.style.display = "none";
    if (!result.ok) {
      this._setStatus(
        `${modelLabel} could not break up this document: ${
          result.error || "unknown error"
        }.`,
      );
      return;
    }
    const excludedNote = summarizeExcludedStatementRows(
      this.statementExcludedRows,
    );
    this._setStatus(
      `${modelLabel} read this as MANY expenses — found ${this.items.length}` +
        " transaction(s). Walk them with Prev/Next, correct anything misread," +
        " then Save All. Categories are left to the store: statement rows" +
        " enter the New Records queue." +
        (excludedNote ? ` ${excludedNote}` : "") +
        // Said out loud when the server overruled its own classifier and read
        // the page a second time. Quietly answering a different question than
        // the one asked is how an operator stops trusting the button.
        summarizeReceiptReread(result),
    );
  }

  /**
   * Adopt an extraction's rows as the item list and remember the account.
   * @param {import("../abstract/manual-entry.interface.js").StatementBreakupResult} result
   */
  _loadStatementItems(result) {
    this.items = result.items;
    this.currentIndex = 0;
    this.statementHeader = result.header;
    this.statementExcludedRows = result.excludedRows;
    if (!this._archiveKindManuallySet) {
      // A statement is never "a receipt", whatever the item count says. The
      // statement store does its own archiving under bank_statements/, so this
      // only keeps the form's own preview from claiming a Receipts path.
      this.archiveKind = ARCHIVE_KIND.SCANNED_DOCUMENT;
      this.archiveKindSelect.value = this.archiveKind;
    }
    this._renderCurrentItem();
  }

  async _updateArchivePathPreview() {
    if (this.statementHeader) {
      // This preview answers "where would the Receipts archive file this?",
      // which is the wrong question for a statement: store_statement_
      // transactions.py files the page under the scanned-statement archive by
      // year itself. Showing a receipt path here would be a confident lie.
      this._archivePathEl.textContent =
        "(statement mode — the statement store files this page under the" +
        " bank-statements archive itself)";
      return;
    }
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

  /**
   * Save exactly one item through the right endpoint: an UPDATE
   * (/api/expense-edit) when it names an already-stored row (see
   * ManualEntryFields.expenseId), an INSERT (/api/manual-receipt-entry)
   * otherwise. This dialog's plain new items and Mazda's own seeded
   * findings both funnel through Save All, but only the first kind is safe
   * to insert -- the second names a row that already exists (see
   * finance/intake_report_model.StoredFinding's expense_id docstring), and
   * inserting it again is exactly how a vendor/category correction typed
   * onto a seeded finding used to silently vanish: the store's own dedup
   * check recognized the still-identical (date, amount) as the same
   * expense already on file and quietly reported it as a duplicate instead
   * of an error (EG, 2026-08-22).
   * @param {import("../abstract/manual-entry.interface.js").ManualEntryFields} item
   * @param {import("../abstract/manual-entry.interface.js").IntakeRef} intakeRef
   * @returns {Promise<{ok: boolean, error: ?string, isUpdate: boolean, vendorRemembered?: object}>}
   */
  async _saveOneItem(item, intakeRef) {
    if (item.expenseId) {
      const payload = buildEditPayload(item.expenseId, item);
      if (!payload) {
        return {
          ok: false,
          error: "Those values cannot be saved.",
          isUpdate: true,
        };
      }
      try {
        const result = readEditResponse(
          await this.http.postJSON("/api/expense-edit", payload),
        );
        return {
          ok: result.ok,
          error: result.ok ? null : describeEditResult(result),
          isUpdate: true,
          record: result.record,
          vendorRemembered: result.vendorRemembered,
        };
      } catch (err) {
        return {
          ok: false,
          error: err && err.message ? err.message : String(err),
          isUpdate: true,
        };
      }
    }
    try {
      const json = await this.http.postJSON(
        "/api/manual-receipt-entry",
        buildSubmitPayload(item, intakeRef),
      );
      return { ...readSubmitResponse(json), isUpdate: false };
    } catch (err) {
      return {
        ok: false,
        error: err && err.message ? err.message : String(err),
        isUpdate: false,
      };
    }
  }

  async _saveAll() {
    this._captureCurrentItem();
    // Which rules apply is decided by what the document IS, not by how many
    // rows are on screen: a statement's credits are legitimately negative and
    // its rows are stored by a different tool.
    const validate = this.statementHeader
      ? validateStatementRow
      : validateManualEntry;
    const label = this.statementHeader ? "transaction" : "expense";
    const invalidIndex = this.items.findIndex((item) => !validate(item).valid);
    if (invalidIndex !== -1) {
      this.currentIndex = invalidIndex;
      this._renderCurrentItem();
      this._renderErrors(validate(this.items[invalidIndex]).errors);
      this._setStatus(
        `Fix ${label} ${invalidIndex + 1} of ${this.items.length} before saving.`,
      );
      return;
    }
    if (this.statementHeader) {
      await this._saveStatement();
      return;
    }
    const intakeRef = {
      imagePath: this.imagePathInput.value,
      conversationId: this.conversationId,
    };
    const results = [];
    for (let i = 0; i < this.items.length; i++) {
      this._setStatus(`Saving ${i + 1} of ${this.items.length}…`);
      const result = await this._saveOneItem(this.items[i], intakeRef);
      results.push(result);
      // Save All may run again after the operator moves to another item.
      // Promote a successful insert (including a duplicate match that names
      // its existing row) to stored-item state immediately, so that later
      // saves UPDATE that expense rather than feeding it through the insert
      // pipeline a second time.
      if (result.ok && result.expenseId) {
        this.items[i].expenseId = result.expenseId;
      }
      if (result.ok && result.record) {
        const item = this.items[i];
        const vendorKey =
          item.knownVendorKey === NEW_VENDOR_OPTION
            ? item.newVendorKey
            : item.knownVendorKey;
        if (result.isUpdate) {
          verifiedTransactionRowsRegistry.current?.updateExpense(
            result.record,
            vendorKey,
          );
        } else {
          verifiedTransactionRowsRegistry.current?.addExpense(
            result.record,
            vendorKey,
          );
        }
      }
      if (
        result.ok &&
        result.vendorRemembered?.remembered &&
        result.vendorRemembered.vendorKey
      ) {
        this.items[i].knownVendorKey = result.vendorRemembered.vendorKey;
        this.items[i].newVendorKey = "";
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
    const updatedCount = results.filter((r) => r.isUpdate).length;
    const insertedCount = results.length - updatedCount;
    let statusText;
    if (updatedCount && insertedCount) {
      statusText = `${insertedCount} expense(s) saved, ${updatedCount} updated.`;
    } else if (updatedCount) {
      statusText = `${updatedCount} expense(s) updated.`;
    } else {
      statusText = `All ${results.length} expense(s) saved.`;
    }
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
    this._showReloadButton();
  }

  /**
   * Save All, in statement mode: every corrected row in one call.
   *
   * The counts reported back are the store's own -- it is the thing that knows
   * a "PAYMENT - THANK YOU" line is not an expense and that two of these rows
   * are already on file from their receipts. Reporting anything the form
   * computed itself would be a second, weaker opinion about the same rows.
   */
  async _saveStatement() {
    this._setStatus(
      `Storing ${this.items.length} transaction(s) through the statement store…`,
    );
    let result;
    try {
      const json = await this.http.postJSON(
        "/api/manual-statement-entry",
        buildStatementEntryPayload(
          // The store's split_expenses_and_credits needs the WHOLE page's
          // signs to classify a borderline row correctly -- submitting only
          // the reviewable rows would change a mixed-sign page into an
          // all-negative one and could flip its verdict on a row that was
          // never touched. The excluded rows ride along unedited; the store
          // reaches the same "not an expense" verdict on them either way and
          // reports them back as skipped_credits.
          [...this.items, ...this.statementExcludedRows],
          {
            imagePath: this.imagePathInput.value,
            conversationId: this.conversationId,
          },
          this.statementHeader,
        ),
        // Duplicate-checking, vendor resolution and the archive move for a
        // whole page run inside one request.
        { timeout: 180000 },
      );
      result = readStatementEntryResponse(json);
    } catch (err) {
      this._setStatus(
        `Statement save failed: ${err && err.message ? err.message : err}`,
      );
      return;
    }
    const summary = summarizeStatementStore(result);
    if (!result.ok) {
      this._setStatus(
        `Statement not stored: ${result.error || "unknown error"} (${summary})` +
          (result.problems.length ? ` ${result.problems.join("; ")}` : ""),
      );
      return;
    }
    this._setStatus(
      `${summary}${
        result.problems.length ? ` Notes: ${result.problems.join("; ")}` : ""
      }`,
    );
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
