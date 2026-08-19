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
 * Two documents, two tools, one form. A receipt fills one row and Save All
 * stores it through parse_and_categorize.py. A STATEMENT page carries several
 * expenses at once, so "Break Up Document" reads them all with
 * parse_statement_scan.py, hands Prev/Next one item per transaction, and Save
 * All stores the whole page through store_statement_transactions.py. Both are
 * the tools Mazda herself runs — this form is how a human runs them while
 * MAZDA_DECISION_MODE=human_only means no agent will.
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
import {
  buildStatementBreakupPayload,
  buildStatementEntryPayload,
  buildStatementRoutePayload,
  POSSIBLE_STATEMENT_INFO_MESSAGE,
  readStatementBreakupResponse,
  readStatementEntryResponse,
  readStatementRouteResponse,
  STATEMENT_ENGINE_OPTIONS,
  summarizeExcludedStatementRows,
  summarizeStatementStore,
  validateStatementRow,
} from "../abstract/statement-breakup.interface.js";
import { mountTerminal } from "./detail-renderers.js";
import { ExpenseEditDialog } from "./expense-edit-dialog.js";
import { FetchHttpClient } from "./fetch-http-client.js";
import { InfoDialog } from "./info-dialog.js";

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
    // Which STATEMENT_ENGINE the operator's button chose -- set on the first
    // Read with Gemini/Haiku click, reused by the bank/account resubmit
    // continuation so Submit re-reads with the SAME provider, never a silent
    // switch to the other one.
    this._statementBreakupEngine = null;
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

    // Escape hatch for a document Mazda would classify as doc_kind='statement'
    // (found 2026-08-17: a bank statement page and a check/account-summary
    // screenshot both landed in a receipt scanner's queue and Gemini Flash
    // Fill confidently mis-extracted a single "expense" from each). Mazda's
    // own classify step is a paid vision call this button skips -- the
    // operator has already looked via Show Image, so re-deriving "is this a
    // statement" would just spend a token MAZDA_DECISION_MODE=human_only
    // exists to avoid. Routes into the SAME statement-preflight pipeline a
    // normal auto-classified statement scan uses (server.py's
    // process_scanned_document/run_statement_preflight) via
    // doc_kind_override, not a separate reimplementation.
    this.statementButton = this._button(
      imagePathWrap,
      "Not a receipt — process as statement",
      "route-as-statement",
    );
    this.statementButton.disabled = !this.scannerKey;
    this.statementButton.addEventListener("click", () =>
      this._routeAsStatement(),
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
      "route-as-statement-submit",
    );
    // Two different flows can ask for the bank/last-four -- routing the page to
    // Mazda, and breaking it up here by hand -- and both ask for exactly the
    // same two values. One prompt serves both: whichever flow opened it sets
    // the resubmit handler, so Submit continues the flow the operator is
    // actually in rather than silently restarting the other one.
    this._resubmitWithStatementMetadata = (metadata) =>
      this._routeAsStatement(metadata);
    this.statementMetadataSubmit.addEventListener("click", () =>
      this._resubmitWithStatementMetadata({
        bankName: this.statementBankNameInput.value,
        accountLast4: this.statementAccountLast4Input.value,
      }),
    );

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

    // Same opt-in posture as Gemini Flash Fill: spends a Claude Haiku call
    // through this box's own Claude Code subscription OAuth session (never
    // a metered ANTHROPIC_API_KEY -- see claude_oauth_client.py), so it's a
    // separate button rather than an automatic fallback. Primarily useful
    // once Gemini's free-tier 20-requests/day-per-model quota is exhausted.
    this.haikuFillButton = this._button(shell, "Fill with Haiku", "haiku-fill");
    this.haikuFillButton.addEventListener("click", () =>
      this._prefill(
        PREVIEW_ENGINE.HAIKU_ONLY,
        this.haikuFillButton,
        "Claude Haiku",
      ),
    );

    // The fill buttons above all ask the RECEIPT parser, which answers with one
    // merchant/date/amount because a receipt has one -- so a statement page
    // holding five transactions filled a single row and left Prev/Next with
    // nothing to walk (2026-08-19, the Choice Privileges page on the Last
    // Window Scan). These buttons ask the statement parser instead: the same
    // parse_statement_scan.py preflight the automatic pipeline runs, which is
    // the tool that knows how to break one page into many expenses. Two
    // buttons, not one -- gemini-only/haiku-only name a single provider with
    // no fallback (see STATEMENT_ENGINE_OPTIONS), so an operator who picks a
    // provider gets exactly that one, not a silent swap to the other on
    // failure. A <fieldset> (98.css's own thin-groove-line "group box") makes
    // the pair read as one labeled unit rather than two loose buttons.
    const breakUpFieldset = this._el("fieldset", {
      className: "manual-entry-breakup-fieldset",
    });
    shell.appendChild(breakUpFieldset);
    breakUpFieldset.appendChild(
      this._el("legend", { text: "Break up Document into separate expenses" }),
    );
    // engine -> its button, so the click handler and the finally-block
    // disable/pressed reset can both address "whichever button is in
    // flight" without an if/else per engine.
    this.breakUpButtons = {};
    for (const { engine, label } of STATEMENT_ENGINE_OPTIONS) {
      const button = this._button(
        breakUpFieldset,
        label,
        `break-up-document-${engine}`,
      );
      button.addEventListener("click", () =>
        this._breakUpDocument(undefined, engine),
      );
      this.breakUpButtons[engine] = button;
    }

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

    // One shared Info box for the whole form -- see _prefill's
    // possibleStatement check, the only trigger today.
    this._infoDialog = new InfoDialog({ root: this.root, doc: this.doc });

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
      this._statementBreakupEngine = null;
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
        // fetch-http-client.js's default fetch timeout is 30s. Gemini Flash
        // Fill's server side (finance/manual_entry.py's
        // MANUAL_ENTRY_TIMEOUT_SEC) allows up to 90s -- a real call through
        // GeminiReceiptEngine's model fallback chain (each retired/blocked
        // model has to fail before the next is tried) measured at 18-25s on
        // its own, close enough to 30s that a slightly larger image aborted
        // client-side with nothing to show for it while the server was still
        // working. Haiku's own OAuth-authenticated call gets the same
        // server-side allowance and the same generous client timeout --
        // an expired ~/.claude/.credentials.json triggers a refresh (one
        // extra network round-trip, occasionally a `claude -p "ok"`
        // subprocess call) before the real Messages API request even
        // starts. Local OCR never leaves this box, so it keeps the default.
        engine === PREVIEW_ENGINE.GEMINI_ONLY ||
          engine === PREVIEW_ENGINE.HAIKU_ONLY
          ? { timeout: 95000 }
          : undefined,
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
      // Zero extra cost: this reads the SAME raw OCR text every fill engine
      // already produced, just checked for a statement's shape (multiple
      // dated rows) instead of one receipt's. Shown regardless of whether the
      // receipt-shaped fields above happened to come back readable -- a
      // statement's own merchant/date/total rarely mean anything as "the"
      // expense, so the nudge matters most exactly when prefill looks thin.
      if (prefill.possibleStatement) {
        this._infoDialog.show(POSSIBLE_STATEMENT_INFO_MESSAGE);
      }
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

  /**
   * "Read with Gemini" / "Read with Haiku" button/resubmit handler.
   *
   * Replaces the item list wholesale with one item per transaction found on
   * the page, so Prev/Next walk the real expenses instead of the single row a
   * receipt-shaped fill leaves behind. The rows are read by the same
   * parse_statement_scan.py preflight the automatic pipeline uses, and Save All
   * hands them to the same store_statement_transactions.py Mazda would -- being
   * Mazda by hand, not a second implementation of her.
   *
   * @param {?{bankName: string, accountLast4: string}} [statementMetadata]
   *   omitted on the first click; passed back in from the inline prompt once
   *   the server reports it could not resolve the bank/account on its own
   * @param {string} [engine] one of STATEMENT_ENGINE's values -- required on
   *   the first (button) call; omitted on the resubmit continuation, which
   *   reuses whichever engine that first call recorded, so Submit reads with
   *   the SAME provider the operator originally chose
   */
  async _breakUpDocument(statementMetadata, engine) {
    if (engine) this._statementBreakupEngine = engine;
    const button = this.breakUpButtons[this._statementBreakupEngine];
    button.disabled = true;
    button.classList.add("is-pressed");
    this.statementMetadataSubmit.disabled = true;
    this._setStatus("Reading every transaction off this document…");
    try {
      const json = await this.http.postJSON(
        "/api/manual-statement-breakup",
        buildStatementBreakupPayload(
          { imagePath: this.imagePathInput.value },
          statementMetadata,
          this._statementBreakupEngine,
        ),
        // Vision extraction of a whole statement page is the slowest call this
        // form makes -- give it the same generous allowance the Gemini/Haiku
        // fills get rather than aborting client-side on a page the server is
        // still reading.
        { timeout: 180000 },
      );
      const result = readStatementBreakupResponse(json);
      // Rows first, error second: a needs-metadata answer still carries every
      // transaction, and showing them while the operator types the bank in is
      // the whole reason this response is shaped that way.
      if (result.items.length) this._loadStatementItems(result);
      if (result.needsStatementMetadata) {
        this._resubmitWithStatementMetadata = (metadata) =>
          this._breakUpDocument(metadata);
        this.statementBankNameInput.value = result.header.bankName;
        this.statementAccountLast4Input.value = result.header.accountLast4;
        this.statementMetadataPrompt.style.display = "";
        this._setStatus(
          `Read ${result.items.length} transaction(s), but the bank/account` +
            ` couldn't be resolved automatically (missing: ${
              result.missingFields.join(", ") || "bank/account"
            }) — fill in the fields above and Submit before saving.`,
        );
        return;
      }
      this.statementMetadataPrompt.style.display = "none";
      this._resubmitWithStatementMetadata = (metadata) =>
        this._routeAsStatement(metadata);
      if (!result.ok) {
        this._setStatus(
          `Could not break up this document: ${result.error || "unknown error"}.`,
        );
        return;
      }
      const excludedNote = summarizeExcludedStatementRows(
        this.statementExcludedRows,
      );
      this._setStatus(
        `Found ${this.items.length} transaction(s) — walk them with Prev/Next,` +
          " correct anything misread, then Save All. Categories are left to" +
          " the store: statement rows enter the New Records queue." +
          (excludedNote ? ` ${excludedNote}` : ""),
      );
    } catch (err) {
      this._setStatus(
        `Break Up Document failed: ${err && err.message ? err.message : err}`,
      );
    } finally {
      button.disabled = false;
      button.classList.remove("is-pressed");
      this.statementMetadataSubmit.disabled = false;
    }
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

  /**
   * "Not a receipt — process as statement" button/resubmit handler.
   * @param {?{bankName: string, accountLast4: string}} [statementMetadata]
   *   omitted on the first click; passed back in from the inline prompt once
   *   the server reports it couldn't resolve the bank/account on its own
   */
  async _routeAsStatement(statementMetadata) {
    if (!this.scannerKey) return;
    this.statementButton.disabled = true;
    this.statementButton.classList.add("is-pressed");
    this.statementMetadataSubmit.disabled = true;
    this._setStatus("Routing to statement intake…");
    try {
      const json = await this.http.postJSON(
        "/api/process-document",
        buildStatementRoutePayload(this.scannerKey, statementMetadata),
      );
      const result = readStatementRouteResponse(json);
      if (result.needsStatementMetadata) {
        this.statementMetadataPrompt.style.display = "";
        this._setStatus(
          "This is a statement, but the bank/account couldn't be resolved" +
            ` automatically (missing: ${result.missingFields.join(", ") || "bank/account"})` +
            " — fill in the fields below and Submit.",
        );
        return;
      }
      this.statementMetadataPrompt.style.display = "none";
      if (result.rejected) {
        this._setStatus(
          `Statement rejected: ${result.error || "unknown reason"}.`,
        );
        return;
      }
      this._setStatus(
        result.ok
          ? "Routed to statement intake." +
              (result.mazdaDispatched
                ? " Mazda will investigate/categorize/store it."
                : ` ${result.error || "Mazda was not dispatched."}`)
          : `Could not route as a statement: ${result.error || "unknown error"}.`,
      );
    } catch (err) {
      this._setStatus(
        `Statement routing request failed: ${err && err.message ? err.message : err}`,
      );
    } finally {
      this.statementButton.disabled = false;
      this.statementButton.classList.remove("is-pressed");
      this.statementMetadataSubmit.disabled = false;
    }
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
