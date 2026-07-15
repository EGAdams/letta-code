import { TextUtils } from "../abstract/text-utils.js";
import { describePipelineStage } from "./document-pipeline-controller.js";

/**
 * RolFinanceReportsController — builds the Project Plans → ROL Finance →
 * Reports tabs. The reports are grouped by month/year: a row of "month tabs"
 * (January 2025, February 2025, …) is injected once, and selecting a month
 * fetches that month's report list (cached per month) and (re)builds one
 * report tab + one <section> per document below it.
 *
 * Each document section contains:
 *   1. A reprocess bar (button + inline status) so the user can re-run the
 *      full Mazda intake pipeline on the underlying source document at any time.
 *   2. An iframe loading the report.html, collapsed to the Verified Transactions
 *      card via showOnlyVerifiedTransactions on load.
 *
 * The controller polls GET /api/expense-stored-events every 15 s (when polling
 * is enabled by injecting setInterval / clearInterval). When Mazda stores a new
 * expense after a scan, she POSTs /api/expense-stored (STEP 8 in the scan
 * message); any open report iframe is reloaded so receipt markers auto-refresh.
 *
 * Programs to interfaces, not implementations:
 *   - HttpClient (http) — all network calls go through http.getJSON / postJSON.
 *   - Timer strategy (setInterval / clearInterval) — injected; null disables polling.
 *   - Document factory (doc) — all DOM creation goes through doc.createElement.
 *   - View callbacks (activateView, setActiveTab) — injected by the boot file.
 */
export class RolFinanceReportsController {
  constructor({
    http,
    nav,
    viewsContainer,
    doc = globalThis.document,
    activateView = () => {},
    setActiveTab = () => {},
    endpoint = "/api/rol-finance-reports",
    reprocessEndpoint = "/api/reprocess-report",
    expenseEventsEndpoint = "/api/expense-stored-events",
    monthStatusEndpoint = "/api/rol-finance-month-status",
    recentScansEndpoint = "/api/rol-finance-recent-scans",
    categoriesEndpoint = "/api/rol-finance-categories",
    recategorizeEndpoint = "/api/recategorize-expense",
    receiptLookupEndpoint = "/api/receipt-lookup",
    recentScansLimit = 5,
    recentReportUrl = "/recent_report.html",
    mazdaAgentId = "agent-6b536cf4-ec88-4290-b595-fed21d14bd8e",
    months = [
      { key: "jan-2025", label: "January 2025" },
      { key: "feb-2025", label: "February 2025" },
    ],
    setInterval: _setInterval = null,
    clearInterval: _clearInterval = null,
    openUrl = (url) => globalThis.open?.(url, "_blank", "noopener,noreferrer"),
  }) {
    if (!http || !nav || !viewsContainer) {
      throw new Error(
        "RolFinanceReportsController requires { http, nav, viewsContainer }",
      );
    }
    this._http = http;
    this._nav = nav;
    this._viewsContainer = viewsContainer;
    this._doc = doc;
    this._activateView = activateView;
    this._setActiveTab = setActiveTab;
    this._endpoint = endpoint;
    this._reprocessEndpoint = reprocessEndpoint;
    this._expenseEventsEndpoint = expenseEventsEndpoint;
    this._monthStatusEndpoint = monthStatusEndpoint;
    this._recentScansEndpoint = recentScansEndpoint;
    this._categoriesEndpoint = categoriesEndpoint;
    this._recategorizeEndpoint = recategorizeEndpoint;
    this._receiptLookupEndpoint = receiptLookupEndpoint;
    this._recentScansLimit = recentScansLimit;
    this._recentReportUrl = recentReportUrl;
    this._mazdaAgentId = mazdaAgentId;
    this._openUrl = openUrl;
    this._months = months;
    this._setInterval = _setInterval;
    this._clearInterval = _clearInterval;
    this._monthsBuilt = false;
    this._activeMonthKey = null;
    this._reportsByMonth = new Map();
    this._recentPanel = null;
    this._pickerDialog = null;
    this._categories = null;
    this._activeCard = null;
    this.reports = null;
    this._pollTimer = null;
    this._lastEventTs = 0;
  }

  /**
   * Inject the Recent Report + month tabs (once), preload the first month's
   * document tabs, then land on the Recent Report view — the Verified
   * Transactions of the most recently processed document.
   */
  async openReports() {
    if (!this._monthsBuilt) {
      this.buildRecentReportTab();
      this.buildMonthTabs();
      this._monthsBuilt = true;
    }
    const first = this._months[0];
    if (first) await this.openMonth(first.key);
    this.openRecentReport();
    this.startPolling();
  }

  /** Inject the "Recent Report" tab (once), ahead of the month tabs. */
  buildRecentReportTab() {
    const tab = this._doc.createElement("button");
    tab.type = "button";
    tab.className = "tab recent-report-tab";
    tab.dataset.recentReport = "1";
    tab.textContent = "Recent Report";
    this._nav.appendChild(tab);
  }

  /**
   * Open the Recent Report view: an iframe over /recent_report.html — the
   * server dynamically serves whichever report.html belongs to the most
   * recently processed document — collapsed to its Verified Transactions card
   * on load. The report's own Set Category dialog rides along (same-origin
   * iframe), so recategorizing works exactly as on a month's document tab.
   * The view is rebuilt on every open: openMonth wipes the views container,
   * and a fresh iframe makes the server re-resolve "most recent".
   */
  openRecentReport() {
    this._nav
      .querySelectorAll(".tab[data-month-key], .tab[data-report-key]")
      .forEach((t) => {
        t.classList.remove("active");
      });
    this._nav.querySelectorAll(".tab[data-recent-report]").forEach((t) => {
      t.classList.add("active");
    });

    const stale = this._viewsContainer.querySelector(
      "#rol-finance-report-recent",
    );
    if (stale) stale.remove();
    const view = this._doc.createElement("section");
    view.id = "rol-finance-report-recent";
    view.className = "view";
    view.insertAdjacentHTML(
      "beforeend",
      `<iframe class="plan-frame" src="${TextUtils.esc(this._recentReportUrl)}"></iframe>`,
    );
    const iframe = view.querySelector("iframe");
    if (iframe) {
      iframe.addEventListener("load", () =>
        this.showOnlyVerifiedTransactions(iframe),
      );
    }
    this._viewsContainer.appendChild(view);
    this._activateView("rol-finance-report-recent");
  }

  /**
   * Refresh the two live signals that sit on top of the static reports:
   *  - month-tab green/yellow completion status, and
   *  - the "recently scanned" viewing area (up to N still-uncategorized rows).
   * Safe to call on a poll: each half fails closed (leaves the last state) so a
   * transient DB/endpoint hiccup never blanks the UI.
   */
  async refreshStatus() {
    await Promise.all([this._refreshMonthStatus(), this._refreshRecentScans()]);
  }

  /**
   * Color each month tab green (caught up) or yellow (its most-recently-scanned
   * expense is still uncategorized), from /api/rol-finance-month-status.
   */
  async _refreshMonthStatus() {
    let data;
    try {
      data = await this._http.getJSON(this._monthStatusEndpoint);
    } catch {
      return; // keep prior colors on a transient failure
    }
    // The endpoint fails soft (HTTP 200 + {error}) on a DB hiccup, so a throw is
    // not the only failure signal — treat a missing/error payload as "keep prior
    // colors" too, rather than stripping every tab's status.
    if (!data || data.error || !Array.isArray(data.months)) return;
    const byKey = new Map(data.months.map((m) => [m.month_key, m]));
    this._nav.querySelectorAll(".tab.month-tab").forEach((t) => {
      const m = byKey.get(t.dataset.monthKey);
      t.classList.remove("status-green", "status-yellow");
      if (!m) return;
      t.classList.add(m.status === "yellow" ? "status-yellow" : "status-green");
      t.title =
        m.status === "yellow"
          ? `${m.uncategorized_count || 0} expense(s) need a category`
          : "All scanned expenses categorized";
    });
  }

  /**
   * Render the "New Records" viewing area from /api/rol-finance-recent-scans.
   * The endpoint returns only up to N still-uncategorized rows (newest first),
   * so as each is categorized it drops out and the next backfills. Each card
   * carries the data the Set Category dialog needs and opens that dialog on
   * click (NOT a full report page) — see _openPicker.
   */
  async _refreshRecentScans() {
    const panel = this._ensureRecentPanel();
    let data;
    try {
      const month = this._activeMonthKey
        ? `&month=${encodeURIComponent(this._activeMonthKey)}`
        : "";
      data = await this._http.getJSON(
        `${this._recentScansEndpoint}?limit=${this._recentScansLimit}${month}`,
      );
    } catch {
      return; // keep prior contents on a transient failure
    }
    // Fail soft like month-status: a missing/error payload keeps the prior
    // cards rather than falsely rendering "all caught up" on a DB hiccup.
    if (!data || data.error || !Array.isArray(data.rows)) return;
    const rows = data.rows;
    const total = data.queue_total || 0;
    const catClass = (cat) => {
      if (!cat) return "cat-uncategorized";
      return (
        "cat-" +
        cat
          .toLowerCase()
          .replace(/,\s*/g, "-")
          .replace(/[\s/]+/g, "-")
          .replace(/[^a-z0-9-]/g, "")
      );
    };
    const body = rows.length
      ? rows
          .map((r) => {
            const cls =
              catClass(r.reporting_category) +
              (r.receipt_present ? " has-receipt" : "");
            return (
              `<tr class="${cls}" role="button" tabindex="0"` +
              ` title="Click to set a category or ask Mazda"` +
              ` data-expense-id="${TextUtils.esc(String(r.id))}"` +
              ` data-vendor-key="${TextUtils.esc(r.vendor_key || "")}"` +
              ` data-description="${TextUtils.esc(r.description || r.vendor_key || r.id_light || "—")}"` +
              ` data-signed-amount="${TextUtils.esc(r.amount || "")}"` +
              ` data-date="${TextUtils.esc(r.expense_date || "")}"` +
              ` data-reason="${TextUtils.esc(r.reason || "")}"` +
              ` data-receipt-present="${r.receipt_present ? "1" : "0"}">` +
              `<td>${TextUtils.esc(r.expense_date || "")}</td>` +
              `<td>${TextUtils.esc(r.description || r.vendor_key || r.id_light || "—")}</td>` +
              `<td style="text-align:right">$${TextUtils.esc(r.amount || "")}</td>` +
              `<td>${TextUtils.esc(r.reporting_category || "Uncategorized")}</td>` +
              `</tr>`
            );
          })
          .join("")
      : "";
    panel.innerHTML =
      `<h3 class="rol-recent-title">New Records${total ? ` — ${total} waiting` : ""}</h3>` +
      (rows.length
        ? `<table class="rol-recent-table"><thead><tr>` +
          `<th>Date</th><th>Description</th><th>Amount</th><th>Category</th>` +
          `</tr></thead><tbody>${body}</tbody></table>`
        : `<p class="rol-recent-empty">Nothing waiting — all scanned receipts are categorized.</p>`);
  }

  /**
   * Create the New Records panel once, as a sibling ABOVE the views container
   * (so openMonth's `viewsContainer.innerHTML = ""` never wipes it). One
   * delegated click/Enter handler opens the Set Category dialog for a card.
   */
  _ensureRecentPanel() {
    if (this._recentPanel) return this._recentPanel;
    const panel = this._doc.createElement("section");
    panel.id = "rol-finance-recent-scans";
    panel.className = "rol-recent-scans";
    const onActivate = (e) => {
      const card = e.target.closest?.("tr[data-expense-id]");
      if (!card) return;
      if (e.type === "keydown" && e.key !== "Enter" && e.key !== " ") return;
      this._openPicker(card);
    };
    panel.addEventListener("click", onActivate);
    panel.addEventListener("keydown", onActivate);
    // Insert as a sibling ABOVE viewsContainer so openMonth's innerHTML="" never
    // wipes it. safeActivateView() in dashboard-boot.js toggles panel.hidden
    // to keep it visible only on ROL Finance views.
    const parent = this._viewsContainer.parentElement;
    if (parent?.insertBefore) parent.insertBefore(panel, this._viewsContainer);
    else this._viewsContainer.appendChild(panel);
    this._recentPanel = panel;
    return panel;
  }

  /** Fetch the reporting-category list (name + colors) once and cache it. */
  async _loadCategories() {
    if (this._categories) return this._categories;
    const data = await this._http.getJSON(this._categoriesEndpoint);
    this._categories = data?.categories || [];
    return this._categories;
  }

  /**
   * Build the New Records "Set Category" dialog once. It mirrors the Verified
   * Transactions row dialog (target line → category grid → footer buttons) and
   * reuses the same `/api/recategorize-expense` endpoint, but adds a "reason it
   * needs attention" block between the target line and the category grid, and
   * lives natively in the dashboard (no report iframe / full page).
   */
  _ensurePickerDialog() {
    if (this._pickerDialog) return this._pickerDialog;
    const mk = (tag, cls, text) => {
      const e = this._doc.createElement(tag);
      if (cls) e.className = cls;
      if (text != null) e.textContent = text;
      return e;
    };
    const modal = mk("div", "cp-modal");
    modal.id = "rol-newrec-picker";
    const panel = mk("div", "cp-panel");
    const head = mk("div", "cp-head");
    const target = mk("p", "cp-target");
    head.appendChild(mk("h3", null, "Set Category"));
    head.appendChild(target);
    const reason = mk("div", "cp-reason");
    const list = mk("div", "cp-list");
    const foot = mk("div", "cp-foot");
    const msg = mk("span", "cp-msg");
    const actions = mk("div", "cp-actions");
    const askMazdaBtn = mk("button", "cp-ask-mazda", "Ask Mazda");
    const viewReceiptBtn = mk("button", "cp-view-receipt", "View Receipt");
    const closeBtn = mk("button", "cp-close", "Close");
    askMazdaBtn.type = "button";
    viewReceiptBtn.type = "button";
    closeBtn.type = "button";
    actions.appendChild(askMazdaBtn);
    actions.appendChild(viewReceiptBtn);
    actions.appendChild(closeBtn);
    foot.appendChild(msg);
    foot.appendChild(actions);
    panel.appendChild(head);
    panel.appendChild(reason);
    panel.appendChild(list);
    panel.appendChild(foot);
    modal.appendChild(panel);

    closeBtn.addEventListener("click", () => this._closePicker());
    modal.addEventListener("click", (e) => {
      if (e.target === modal) this._closePicker();
    });
    viewReceiptBtn.addEventListener("click", () => this._viewReceipt());
    askMazdaBtn.addEventListener("click", () => this._askMazda());

    const parent = this._viewsContainer.parentElement || this._viewsContainer;
    (parent.appendChild ? parent : this._viewsContainer).appendChild(modal);
    this._pickerDialog = {
      modal,
      target,
      reason,
      list,
      msg,
      viewReceiptBtn,
      askMazdaBtn,
    };
    return this._pickerDialog;
  }

  /** Open the Set Category dialog for one New Records card. */
  async _openPicker(card) {
    const d = card.dataset;
    this._activeCard = card;
    const pk = this._ensurePickerDialog();
    pk.msg.textContent = "";
    pk.msg.style.color = "";
    pk.target.textContent = `${d.description || ""}  •  ${d.signedAmount || ""}  •  ${d.date || ""}`;
    // The reason this record failed to auto-process — shown so mom can fix it
    // here or tell Mazda what to do.
    pk.reason.textContent = d.reason
      ? `Why it needs attention: ${d.reason}`
      : "";
    pk.reason.style.display = d.reason ? "" : "none";
    pk.viewReceiptBtn.style.display = d.receiptPresent === "1" ? "" : "none";
    pk.modal.classList.add("open");

    let cats;
    try {
      cats = await this._loadCategories();
    } catch {
      pk.msg.style.color = "#b91c1c";
      pk.msg.textContent = "Could not load categories.";
      return;
    }
    pk.list.innerHTML = "";
    for (const c of cats) {
      const sq = this._doc.createElement("div");
      sq.className = `cp-square${c.cls === "cat-uncategorized" ? " current" : ""}`;
      sq.style.background = c.bg;
      sq.style.color = c.fg;
      sq.textContent = c.name;
      sq.addEventListener("click", () => this._pickCategory(c.name));
      pk.list.appendChild(sq);
    }
  }

  _closePicker() {
    if (this._pickerDialog) this._pickerDialog.modal.classList.remove("open");
    this._activeCard = null;
  }

  /** Write the chosen category, then close + refresh so the card backfills. */
  async _pickCategory(categoryName) {
    const card = this._activeCard;
    const pk = this._pickerDialog;
    if (!card || !pk) return;
    const d = card.dataset;
    pk.msg.style.color = "#6b7280";
    pk.msg.textContent = "Saving…";
    let res;
    try {
      res = await this._http.postJSON(this._recategorizeEndpoint, {
        vendor_key: d.vendorKey || "",
        description: d.description || "",
        signed_amount: d.signedAmount || "",
        date: d.date || "",
        reporting_category: categoryName,
        // No report_path → the server searches every report.html for the matching
        // row itself (report vendor_keys often diverge from the DB's) and recolors
        // it there too when found; DB-only when the record has no static row at all.
      });
    } catch (err) {
      pk.msg.style.color = "#b91c1c";
      pk.msg.textContent = `Save failed: ${err.message}`;
      return;
    }
    if (!res || res.ok === false) {
      pk.msg.style.color = "#b91c1c";
      pk.msg.textContent = res?.error || "Save failed.";
      return;
    }
    this._closePicker();
    await this.refreshStatus();
  }

  /** Reuse /api/receipt-lookup to open the stored receipt (if any). */
  async _viewReceipt() {
    const card = this._activeCard;
    const pk = this._pickerDialog;
    if (!card || !pk) return;
    const d = card.dataset;
    pk.msg.style.color = "#6b7280";
    pk.msg.textContent = "Finding receipt…";
    let res;
    try {
      res = await this._http.postJSON(this._receiptLookupEndpoint, {
        vendor_key: d.vendorKey || "",
        description: d.description || "",
        signed_amount: d.signedAmount || "",
        date: d.date || "",
      });
    } catch (err) {
      pk.msg.style.color = "#b91c1c";
      pk.msg.textContent = `Receipt lookup failed: ${err.message}`;
      return;
    }
    if (res?.ok && res.receipt_url) {
      pk.msg.textContent = "";
      globalThis.open?.(res.receipt_url, "_blank", "noopener,noreferrer");
    } else {
      pk.msg.style.color = "#b91c1c";
      pk.msg.textContent = res?.error || "No receipt on file.";
    }
  }

  /**
   * "Ask Mazda" — reuse the dashboard's InputOptionsRenderer (the same module
   * the Agents tab uses) to hand Mazda this record + its failure reason so mom
   * can tell her how to fix it. Best-effort: degrades to a message on failure.
   */
  async _askMazda() {
    const card = this._activeCard;
    const pk = this._pickerDialog;
    if (!card || !pk) return;
    const d = card.dataset;
    pk.msg.style.color = "#6b7280";
    pk.msg.textContent = "Opening Mazda…";
    try {
      const box = this._ensureMazdaBox();
      this._buildHeadlessMazdaUI(box, d);
      pk.msg.textContent = "";
      this._mazdaDialog.classList.add("open");
    } catch (err) {
      pk.msg.style.color = "#b91c1c";
      pk.msg.textContent = `Could not open Mazda: ${err.message}`;
    }
  }

  /** Build a clean, headless "Ask Mazda" UI using /api/headless-prompt. */
  _buildHeadlessMazdaUI(box, cardData) {
    box.innerHTML = "";
    const mk = (tag, cls, text) => {
      const e = this._doc.createElement(tag);
      if (cls) e.className = cls;
      if (text != null) e.textContent = text;
      return e;
    };

    // Pre-filled prompt with the card context
    const defaultPrompt =
      `# Goal\nFix this New Record so it categorizes\n\n# Record\n${cardData.description || ""} • ${cardData.signedAmount || ""} • ${cardData.date || ""}\n\n` +
      `# Expense id\n${cardData.expenseId || ""}\n\n# Why it failed\n${cardData.reason || "(uncategorized)"}\n\n# What to do\n`;

    // Layout: heading, textarea, send button, response area
    const container = mk("div");
    container.style.cssText = "display:flex;flex-direction:column;gap:10px;";

    const heading = mk("p");
    heading.innerHTML = "<strong>Ask Mazda about this record:</strong>";
    heading.style.cssText = "margin:0;font-size:0.9rem;color:#666;";

    const textarea = mk("textarea");
    textarea.value = defaultPrompt;
    textarea.style.cssText =
      "min-height:120px;padding:8px;border:1px solid #bbb;border-radius:4px;font-family:monospace;font-size:0.85rem;resize:vertical;";

    const buttonRow = mk("div");
    buttonRow.style.cssText = "display:flex;gap:8px;";

    const sendBtn = mk("button", null, "Send to Mazda");
    sendBtn.type = "button";
    sendBtn.style.cssText =
      "flex:1;padding:8px 12px;background:#4c6ef5;color:#fff;border:0;border-radius:4px;cursor:pointer;font-weight:600;";

    const clearBtn = mk("button", null, "Clear");
    clearBtn.type = "button";
    clearBtn.style.cssText =
      "flex:1;padding:8px 12px;background:#6c757d;color:#fff;border:0;border-radius:4px;cursor:pointer;";

    buttonRow.appendChild(sendBtn);
    buttonRow.appendChild(clearBtn);

    const status = mk("div");
    status.style.cssText = "min-height:1.4em;font-size:0.85rem;color:#555;";

    const responseArea = mk("div");
    responseArea.style.cssText =
      "border-top:1px solid #ddd;padding-top:10px;max-height:300px;overflow-y:auto;font-size:0.85rem;line-height:1.5;";

    clearBtn.addEventListener("click", () => {
      textarea.value = defaultPrompt;
      responseArea.innerHTML = "";
      status.textContent = "";
      textarea.focus();
    });

    sendBtn.addEventListener("click", async () => {
      const prompt = textarea.value.trim();
      if (!prompt) {
        status.style.color = "#b91c1c";
        status.textContent = "Nothing to send.";
        return;
      }
      sendBtn.disabled = true;
      status.style.color = "#6b7280";
      status.textContent = "Sending to Mazda…";
      responseArea.innerHTML = "";

      try {
        const res = await this._http.postJSON("/api/headless-prompt", {
          agent: this._mazdaAgentId,
          prompt,
        });
        sendBtn.disabled = false;

        if (res?.ok) {
          status.style.color = "#059669";
          status.textContent = "✓ Mazda replied:";
          responseArea.innerHTML = `<div style="white-space:pre-wrap;background:#f5f5f5;padding:8px;border-radius:4px;border-left:3px solid #059669;">${this._escapeHtml(res.output || "(no response)")}</div>`;
        } else {
          status.style.color = "#b91c1c";
          status.textContent = `Error: ${res?.error || "Unknown error"}`;
          responseArea.innerHTML = "";
        }
      } catch (err) {
        sendBtn.disabled = false;
        status.style.color = "#b91c1c";
        status.textContent = `Request failed: ${err.message}`;
        responseArea.innerHTML = "";
      }
    });

    container.appendChild(heading);
    container.appendChild(textarea);
    container.appendChild(buttonRow);
    container.appendChild(status);
    container.appendChild(responseArea);
    box.appendChild(container);

    textarea.focus();
  }

  _escapeHtml(text) {
    const div = this._doc.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  /** Lazily build the Ask Mazda sub-dialog that hosts the InputOptions box. */
  _ensureMazdaBox() {
    if (this._mazdaBox) return this._mazdaBox;
    const mk = (tag, cls, text) => {
      const e = this._doc.createElement(tag);
      if (cls) e.className = cls;
      if (text != null) e.textContent = text;
      return e;
    };
    const modal = mk("div", "mz-modal");
    modal.id = "rol-newrec-mazda";
    const panel = mk("div", "mz-panel");
    const head = mk("div", "mz-head");
    head.appendChild(mk("h3", null, "Ask Mazda"));
    const body = mk("div", "mz-body");
    const box = mk("div", null);
    box.id = "rol-newrec-mazda-box";
    body.appendChild(box);
    const foot = mk("div", "mz-foot");
    const back = mk("button", "mz-back", "Back");
    back.type = "button";
    back.addEventListener("click", () => modal.classList.remove("open"));
    foot.appendChild(back);
    panel.appendChild(head);
    panel.appendChild(body);
    panel.appendChild(foot);
    modal.appendChild(panel);
    modal.addEventListener("click", (e) => {
      if (e.target === modal) modal.classList.remove("open");
    });
    const parent = this._viewsContainer.parentElement || this._viewsContainer;
    (parent.appendChild ? parent : this._viewsContainer).appendChild(modal);
    this._mazdaDialog = modal;
    this._mazdaBox = box;
    return box;
  }

  /** Inject one month tab per configured month (once). */
  buildMonthTabs() {
    for (const m of this._months) {
      const tab = this._doc.createElement("button");
      tab.type = "button";
      tab.className = "tab month-tab";
      tab.dataset.monthKey = m.key;
      tab.textContent = m.label;
      this._nav.appendChild(tab);
    }
  }

  /**
   * Select a month: highlight its tab, fetch its report list (cached per
   * month key), and (re)build its document tabs/views.
   */
  async openMonth(monthKey) {
    const month = this._months.find((m) => m.key === monthKey);
    if (!month) return;
    this._activeMonthKey = monthKey;

    this._nav.querySelectorAll(".tab[data-month-key]").forEach((t) => {
      t.classList.toggle("active", t.dataset.monthKey === monthKey);
    });
    this._nav.querySelectorAll(".tab[data-recent-report]").forEach((t) => {
      t.classList.remove("active");
    });

    let reports = this._reportsByMonth.get(monthKey);
    if (!reports) {
      try {
        reports = await this._http.getJSON(
          `${this._endpoint}?month=${encodeURIComponent(monthKey)}`,
        );
        this._reportsByMonth.set(monthKey, reports);
      } catch (e) {
        this._nav.querySelectorAll(".tab[data-report-key]").forEach((t) => {
          t.remove();
        });
        this._viewsContainer.innerHTML = `<section id="rol-finance-reports-error" class="view active"><p class="am-warn">Failed to load reports: ${TextUtils.esc(e.message)}</p></section>`;
        return;
      }
    }
    this.reports = reports;

    this._nav.querySelectorAll(".tab[data-report-key]").forEach((t) => {
      t.remove();
    });
    this._viewsContainer.innerHTML = "";
    this.buildOverview(reports, month);
    this.buildTabsAndViews(reports);
    this.openOverview();
  }

  /** Map a report's status to a CSS class + human label for the overview row. */
  static statusInfo(status) {
    switch (status) {
      case "pass":
        return { cls: "rol-status-pass", label: "Finished" };
      case "review":
        return { cls: "rol-status-review", label: "In progress" };
      case "missing":
        return { cls: "rol-status-fail", label: "Not started" };
      case "fail":
        return { cls: "rol-status-fail", label: "Failed" };
      default:
        return null;
    }
  }

  /**
   * Build the month-level landing view: one color-coded row per document.
   * Skips reports with no `status` (e.g. the synthetic Receipt Only tab).
   */
  buildOverview(reports, month) {
    const view = this._doc.createElement("section");
    view.id = "rol-finance-reports-overview";
    view.className = "view";

    const rows = reports
      .map((r) => ({
        r,
        info: RolFinanceReportsController.statusInfo(r.status),
      }))
      .filter(({ info }) => info)
      .map(
        ({ r, info }) =>
          `<tr class="${info.cls}" data-report-key="${TextUtils.esc(r.key)}"><td>${TextUtils.esc(r.label)}</td><td>${TextUtils.esc(info.label)}</td></tr>`,
      )
      .join("");

    view.insertAdjacentHTML(
      "beforeend",
      `<h2>${TextUtils.esc(month.label)} — Document Status</h2>
      <table class="rol-overview-table">
        <thead><tr><th>Document</th><th>Status</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>`,
    );

    view.querySelectorAll("tr[data-report-key]").forEach((row) => {
      row.addEventListener("click", () =>
        this.selectReport(row.dataset.reportKey),
      );
    });

    this._viewsContainer.appendChild(view);
  }

  openOverview() {
    this._activateView("rol-finance-reports-overview");
  }

  /**
   * Pure view method: render the "New Records" markup from a
   * GET /api/rol-finance-recent-reports payload ({ latest, items }).
   * The latest-processed report is always shown (prepended ahead of
   * `items` if not already present), then the rest of `items` fills the
   * remaining slots — `items` is already sorted needs-attention-first by
   * the server, so a verified (now-passing) report naturally drops toward
   * the end and the next queued report takes its place. Capped at 5 rows
   * total so "up to 5 rows show at all times" holds regardless of how many
   * candidates exist. Rows are styled/behave like Verified Transactions
   * rows (whole row clickable, color-coded by status) rather than as
   * plain text links, so a human can scan/verify faster.
   */
  renderRecentReportsHtml({ latest, items = [] } = {}) {
    const dedupeKey = (r) => `${r.key}__${r.month_key}`;
    const seen = new Set();
    const combined = [];
    for (const r of latest ? [latest, ...items] : items) {
      const k = dedupeKey(r);
      if (seen.has(k)) continue;
      seen.add(k);
      combined.push(r);
    }

    const rows = combined
      .slice(0, 5)
      .map((r) => {
        const info = RolFinanceReportsController.statusInfo(r.status) || {
          cls: "",
          label: "",
        };
        const monthLabel =
          this._months.find((m) => m.key === r.month_key)?.label || r.month_key;
        const attentionCls = r.needs_attention
          ? " rol-recent-needs-attention"
          : "";
        return `<tr class="${info.cls}${attentionCls}" data-recent-url="${TextUtils.esc(r.url)}" title="Click to open report.html"><td>${TextUtils.esc(r.label)} — ${TextUtils.esc(monthLabel)}</td><td>${TextUtils.esc(info.label)}</td></tr>`;
      })
      .join("");

    if (!rows) {
      return `<h3>New Records</h3><p class="rol-recent-empty">No records processed yet.</p>`;
    }
    return `
      <h3>New Records</h3>
      <table class="rol-overview-table rol-recent-table">
        <tbody>${rows}</tbody>
      </table>`;
  }

  /**
   * Inject one tab + one view per report.
   * Existing reports get a reprocess bar above the iframe.
   * Missing reports get a red tab + placeholder.
   */
  buildTabsAndViews(reports) {
    for (const r of reports) {
      const missing = !r.exists;
      const tab = this._doc.createElement("button");
      tab.type = "button";
      tab.className = `tab${missing ? " report-missing" : ""}`;
      tab.dataset.reportKey = r.key;
      tab.textContent = r.label;
      this._nav.appendChild(tab);

      const view = this._doc.createElement("section");
      view.id = `rol-finance-report-${r.key}`;
      view.className = "view";
      if (r.exists) {
        const bar = this.buildReprocessBar(r);
        view.appendChild(bar);
        // Keep the iframe in innerHTML so querySelectorAll on the view
        // can find it in the real DOM while the bar stays queryable via
        // the children tree (the FakeElement pattern this codebase uses).
        view.insertAdjacentHTML(
          "beforeend",
          `<iframe class="plan-frame" src="${TextUtils.esc(r.url)}"></iframe>`,
        );
        const iframe = view.querySelector("iframe");
        if (iframe) {
          iframe.addEventListener("load", () =>
            this.showOnlyVerifiedTransactions(iframe),
          );
        }
      } else {
        view.innerHTML = "<p>Missing report.html for this report.</p>";
      }
      this._viewsContainer.appendChild(view);
    }
  }

  /**
   * Build the reprocess action bar for one report. Returns a <div> containing
   * a "Reprocess Document" button and an inline status span. The button click
   * delegates to reprocessDocument (Command pattern over HttpClient).
   */
  buildReprocessBar(r) {
    const bar = this._doc.createElement("div");
    bar.className = "reprocess-bar";

    const btn = this._doc.createElement("button");
    btn.type = "button";
    btn.className = "reprocess-btn";
    btn.textContent = "Reprocess Document";

    const status = this._doc.createElement("span");
    status.className = "reprocess-status";

    bar.appendChild(btn);
    bar.appendChild(status);

    btn.addEventListener("click", () =>
      this.reprocessDocument(r.key, r.url, btn, status),
    );

    return bar;
  }

  /**
   * Re-run the full intake pipeline (facade + Mazda) for this report's source
   * document. Programs to HttpClient (postJSON) and renders the inline result
   * via renderReprocessResult (a pure view method).
   */
  async reprocessDocument(_key, url, buttonEl, statusEl) {
    if (buttonEl) buttonEl.disabled = true;
    if (statusEl) statusEl.textContent = "Reprocessing…";
    try {
      const result = await this._http.postJSON(this._reprocessEndpoint, {
        report_url: url,
      });
      this.renderReprocessResult(statusEl, result);
    } catch (e) {
      if (statusEl) statusEl.textContent = `Error: ${TextUtils.esc(e.message)}`;
    } finally {
      if (buttonEl) buttonEl.disabled = false;
    }
  }

  /**
   * Pure view update: render a pipeline result into the status span.
   * Reuses describePipelineStage from DocumentPipelineController so the
   * stage-formatting logic is not duplicated.
   */
  renderReprocessResult(statusEl, result) {
    if (!statusEl) return;
    if (!result.ok && result.error) {
      statusEl.textContent = `Failed: ${result.error}`;
      return;
    }
    const stages = (result.stages || []).map(describePipelineStage);
    const parts = stages.map((s) =>
      s.summary
        ? `${s.name}: ${s.status} (${s.summary})`
        : `${s.name}: ${s.status}`,
    );
    statusEl.textContent =
      parts.join(" · ") || (result.ok ? "Dispatched to Mazda" : "Error");
  }

  /**
   * Reach into a same-origin report iframe and hide every <section> except
   * the one containing #verified-transactions.
   */
  showOnlyVerifiedTransactions(iframe) {
    let doc;
    try {
      doc = iframe.contentDocument;
    } catch {
      return;
    }
    if (!doc) return;
    const vt = doc.getElementById("verified-transactions");
    if (!vt) return;
    const keep = vt.closest("section");
    if (!keep || !keep.parentElement) return;
    for (const child of keep.parentElement.children) {
      if (child !== keep && child.tagName === "SECTION") {
        child.style.display = "none";
      }
    }
  }

  /** Highlight a document tab (within the current month) and open its view. */
  selectReport(key) {
    const tab = this._nav.querySelector(`[data-report-key="${key}"]`);
    if (tab) {
      this._nav.querySelectorAll(".tab[data-report-key]").forEach((t) => {
        t.classList.toggle("active", t === tab);
      });
      this._nav.querySelectorAll(".tab[data-recent-report]").forEach((t) => {
        t.classList.remove("active");
      });
    }
    this.openReport(key);
  }

  openReport(key) {
    this._activateView(`rol-finance-report-${key}`);
  }

  // ── Expense-stored polling ─────────────────────────────────────────────────

  /**
   * Start polling /api/expense-stored-events every 15 s. No-op if setInterval
   * was not injected (polling is disabled by default in tests).
   * Idempotent: calling more than once does not start additional timers.
   */
  startPolling() {
    if (!this._setInterval || this._pollTimer != null) return;
    this._pollTimer = this._setInterval(
      () => this._pollStoredExpenses(),
      15_000,
    );
  }

  /** Stop the expense-stored poll (e.g. on teardown). */
  stopPolling() {
    if (this._pollTimer == null) return;
    this._clearInterval(this._pollTimer);
    this._pollTimer = null;
  }

  async _pollStoredExpenses() {
    try {
      const events = await this._http.getJSON(
        `${this._expenseEventsEndpoint}?since=${this._lastEventTs}`,
      );
      if (Array.isArray(events) && events.length > 0) {
        this._lastEventTs = Math.max(...events.map((e) => e.stored_at));
        this._reloadOpenIframes();
      }
    } catch {
      // Network error — silently ignore; retry on the next tick.
    }
    // Refresh every tick (not just when an expense-stored event fires): a
    // report can flip from review/fail to pass via the verification workflow
    // alone, with no expense-stored event, and New Records must still drop
    // it + pull the next queued document up within one poll interval.
    this.refreshStatus();
  }

  /**
   * Reload any open (accessible) report iframes so the receipt-present markers
   * re-run after Mazda stores a new expense + receipt.
   */
  _reloadOpenIframes() {
    this._viewsContainer
      .querySelectorAll("iframe.plan-frame")
      .forEach((iframe) => {
        let accessible = false;
        try {
          accessible = iframe.contentDocument != null;
        } catch {
          /* cross-origin — skip */
        }
        if (accessible) {
          // biome-ignore lint/correctness/noSelfAssign: triggers iframe reload
          iframe.src = iframe.src;
        }
      });
  }
}
