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
 * SEMI-AUTOMATIC, one button. "Mazda Fill" asks the server to classify the
 * page and read it with the cheap model chosen beside it, then drops the
 * result into these fields for a human to check and Save. Both branches run
 * the tools Mazda herself runs — parse_and_categorize.py for one expense,
 * parse_statement_scan.py for many, and Save All stores through
 * parse_and_categorize.py or store_statement_transactions.py to match. This
 * form is how a human runs Mazda's own pipeline a page at a time — the point
 * of Semi-Automatic, where no agent will do it for them.
 *
 * It replaced five reading buttons and a "which group do I press?" group box
 * on 2026-08-19 (see ../abstract/mazda-fill.interface.js): every one of them
 * required the operator to know the document's shape before pressing
 * anything, and the local-OCR heuristic added to guess it for them read the
 * DTE gas bill as a single $28.07 expense.
 *
 * All field/response validation lives in ../abstract/manual-entry.interface.js,
 * ../abstract/statement-breakup.interface.js and
 * ../abstract/mazda-fill.interface.js so it is testable without a browser.
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
  buildSubmitPayload,
  defaultArchiveKind,
  formatAmountForDisplay,
  readArchivePreviewResponse,
  readCategoriesResponse,
  readSubmitResponse,
  readVendorKeysResponse,
  validateManualEntry,
} from "../abstract/manual-entry.interface.js";
import {
  buildMazdaFillPayload,
  DEFAULT_MAZDA_FILL_MODEL,
  FILL_SHAPE,
  MAZDA_FILL_MODEL_OPTIONS,
  mazdaFillModelLabel,
  readMazdaFillResponse,
  summarizeMazdaReread,
} from "../abstract/mazda-fill.interface.js";
import {
  buildMazdaModePayload,
  mazdaModeLabel,
  readMazdaModeDataset,
  readMazdaModeResponse,
  summarizeMazdaMode,
} from "../abstract/mazda-mode.interface.js";
import {
  buildStatementEntryPayload,
  readStatementEntryResponse,
  summarizeExcludedStatementRows,
  summarizeStatementStore,
  validateStatementRow,
} from "../abstract/statement-breakup.interface.js";
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

    // "Mazda Fill" — the form's ONE reading button (2026-08-19; it replaced
    // five). The operator no longer answers "is this one expense or several?"
    // before pressing anything: the server runs the same deterministic
    // classify the automatic pipeline runs (mazda_intake.py), then hands the
    // page to the reader built for whatever it turned out to be, using the
    // cheap model chosen beside this button. The answer lands in these fields
    // for review — nothing is stored until the human presses Save. That is
    // the whole of "semi-automatic": Mazda reads, a human decides.
    this.mazdaFillButton = this._button(
      imagePathWrap,
      "Mazda Fill",
      "mazda-fill",
    );
    this.mazdaFillButton.addEventListener("click", () => this._mazdaFill());
    // Model, not engine: the operator is choosing who reads the page, and both
    // choices are cheap on purpose (see MAZDA_FILL_MODEL_OPTIONS). Driven off
    // that one list so adding a model never means editing markup.
    this.mazdaModelSelect = this._el("select");
    this.mazdaModelSelect.dataset.field = "mazdaModel";
    for (const { model, label } of MAZDA_FILL_MODEL_OPTIONS) {
      const option = this._el("option", { text: label });
      option.value = model;
      this.mazdaModelSelect.appendChild(option);
    }
    this.mazdaModelSelect.value = DEFAULT_MAZDA_FILL_MODEL;
    imagePathWrap.appendChild(this.mazdaModelSelect);

    // The Automatic / Semi-Automatic switch, immediately right of the model
    // dropdown, because it answers the question the two controls beside it
    // raise: "do I have to press Mazda Fill at all?"
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
      this._mazdaFill({
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
    const removeButton = this._button(
      nav,
      "− Remove This Expense",
      "remove-item",
    );
    removeButton.addEventListener("click", () => this._removeItem());

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
    this._positionEl.textContent = this._positionText();
    this._renderErrors({});
  }

  /**
   * The Prev/Next readout. In statement mode it also names the account every
   * row belongs to: five rows off one page are only meaningful as "five
   * transactions on Choice Privileges 5596", and the operator walking them
   * needs to see they are still on the same statement.
   */
  _positionText() {
    const position = `${this.currentIndex + 1} of ${this.items.length}`;
    if (!this.statementHeader) return `Expense ${position}`;
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

  /**
   * "Mazda Fill" — read this page with the chosen cheap model, then show the
   * operator what it found.
   *
   * One handler for both document kinds because the operator now makes one
   * decision, not two. The server classifies first (the same mazda_intake.py
   * facade the automatic pipeline runs) and answers with the shape it FOUND:
   * a receipt fills the three fields and resolves the vendor/category exactly
   * as the old fill buttons did; a statement replaces the item list with one
   * row per transaction, exactly as the old Break Up Document buttons did.
   * Nothing is stored — Save/Save All is still the human's, which is the
   * whole point of running Mazda semi-automatically.
   *
   * @param {?{bankName: string, accountLast4: string}} [statementMetadata]
   *   omitted on the first press; sent back from the inline prompt after a
   *   statement fill read every transaction but could not resolve whose
   *   account they belong to. The model is NOT re-chosen on that retry — the
   *   dropdown still holds whatever the operator picked.
   */
  async _mazdaFill(statementMetadata) {
    const model = this.mazdaModelSelect.value;
    const modelLabel = mazdaFillModelLabel(model);
    this.mazdaFillButton.disabled = true;
    this.mazdaFillButton.classList.add("is-pressed");
    this.statementMetadataSubmit.disabled = true;
    this._setStatus(`Mazda is reading this page with ${modelLabel}…`);
    try {
      const json = await this.http.postJSON(
        "/api/mazda-fill",
        buildMazdaFillPayload(
          { imagePath: this.imagePathInput.value },
          model,
          statementMetadata,
        ),
        // fetch-http-client.js defaults to 30s. A vision read of a whole
        // statement page is the slowest call this form makes, and a classify
        // pass now runs ahead of it — aborting client-side while the server
        // is still reading would throw away work already paid for.
        { timeout: 180000 },
      );
      const result = readMazdaFillResponse(json);
      if (result.shape === FILL_SHAPE.MANY_EXPENSES) {
        this._applyStatementFill(result, modelLabel);
      } else {
        this._applyReceiptFill(result, modelLabel);
      }
    } catch (err) {
      this._setStatus(
        `Mazda Fill failed: ${err && err.message ? err.message : err}`,
      );
    } finally {
      this.mazdaFillButton.disabled = false;
      this.mazdaFillButton.classList.remove("is-pressed");
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
          summarizeMazdaReread(result),
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
        summarizeMazdaReread(result),
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
