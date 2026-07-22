/**
 * The Scanner screen's statement-review dialog.
 *
 * Polls /api/statement-reviews and pops a modal for each quarantined statement:
 * either "add this card to the workbook, then press OK", or an input per
 * unreadable amount (prefilled with the server's suggestion where subtraction
 * made one certain). Submitting re-runs the store; on failure the item stays
 * queued and the dialog comes back, which is the behavior EG asked for.
 *
 * All the decision logic lives in ../abstract/statement-review.interface.js so
 * it can be tested without a browser; this class is DOM + fetch only.
 */
import {
  answerableRows,
  buildResolvePayload,
  collectAmounts,
  isSubmittable,
  nextStateAfterResolve,
  prefillFor,
  REVIEW_KIND,
} from "../abstract/statement-review.interface.js";

const POLL_MS = 15000;

export class StatementReviewDialog {
  constructor({ http, pollMs = POLL_MS, doc = document } = {}) {
    this.http = http;
    this.pollMs = pollMs;
    this.doc = doc;
    this.timer = null;
    this.current = null;
    this.values = {};
    this.busy = false;
    this.root = null;
  }

  start() {
    if (this.timer) return;
    this.refresh();
    this.timer = setInterval(() => {
      this.refresh();
    }, this.pollMs);
  }

  stop() {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }

  async refresh() {
    // Never yank the dialog out from under someone mid-typing.
    if (this.current || this.busy) return;
    try {
      const data = await this.http.getJSON("/api/statement-reviews");
      const reviews = (data && data.reviews) || [];
      if (reviews.length) this.open(reviews[0]);
    } catch (_err) {
      /* a poll failure is not worth interrupting the user for */
    }
  }

  open(item) {
    this.current = item;
    this.values = {};
    answerableRows(item).forEach((row) => {
      this.values[row.index] = prefillFor(row);
    });
    this.render();
  }

  close() {
    this.current = null;
    this.values = {};
    if (this.root) {
      this.root.remove();
      this.root = null;
    }
  }

  _ensureRoot() {
    if (this.root) return this.root;
    const root = this.doc.createElement("div");
    root.id = "statement-review-dialog";
    root.className = "statement-review-overlay";
    this.doc.body.appendChild(root);
    this.root = root;
    return root;
  }

  render(banner) {
    const item = this.current;
    if (!item) return;
    const root = this._ensureRoot();
    const rows = answerableRows(item);
    const { errors } = collectAmounts(item, this.values);

    const rowsHtml = rows
      .map((row) => {
        const err = errors[row.index];
        return `
        <label class="srd-row" data-index="${row.index}">
          <span class="srd-row-label">${escapeHtml(row.description || "Unlabeled row")}
            <em>${escapeHtml(row.date || "date unreadable")}</em></span>
          <span class="srd-input-wrap">
            <span class="srd-currency">$</span>
            <input type="text" inputmode="decimal" class="srd-amount"
                   data-index="${row.index}"
                   value="${escapeHtml(this.values[row.index] ?? "")}" />
          </span>
          ${err ? `<span class="srd-error">${escapeHtml(err)}</span>` : ""}
        </label>`;
      })
      .join("");

    const isWorkbook = item.kind === REVIEW_KIND.WORKBOOK;
    root.innerHTML = `
      <div class="srd-panel" role="dialog" aria-modal="true">
        <div class="srd-head">
          <h3>${isWorkbook ? "Add this card to the sheet" : "I need one number"}</h3>
          <p>${escapeHtml(item.bank_name || "Statement")}${
            item.account_last4 ? ` ····${escapeHtml(item.account_last4)}` : ""
          }</p>
        </div>
        <div class="srd-body">
          <p class="srd-message">${escapeHtml(item.message || "")}</p>
          ${rowsHtml}
          ${banner ? `<p class="srd-banner">${escapeHtml(banner)}</p>` : ""}
        </div>
        <div class="srd-foot">
          <button type="button" class="srd-later">Leave for later</button>
          <button type="button" class="srd-ok"${this.busy ? " disabled" : ""}>${
            this.busy ? "Working…" : isWorkbook ? "OK" : "Save"
          }</button>
        </div>
      </div>`;

    root.querySelectorAll(".srd-amount").forEach((input) => {
      input.addEventListener("input", (event) => {
        this.values[event.target.dataset.index] = event.target.value;
      });
    });
    root.querySelector(".srd-later").addEventListener("click", () => {
      this.close();
    });
    root.querySelector(".srd-ok").addEventListener("click", () => {
      this.submit();
    });
  }

  async submit() {
    const item = this.current;
    if (!item || this.busy) return;
    if (!isSubmittable(item, this.values)) {
      this.render("Fill in every amount first.");
      return;
    }
    const payload = buildResolvePayload(item, this.values);
    if (!payload) {
      this.render("Fill in every amount first.");
      return;
    }

    this.busy = true;
    this.render();
    let response;
    try {
      response = await this.http.postJSON(
        "/api/statement-review-resolve",
        payload,
      );
    } catch (err) {
      response = { ok: false, error: String((err && err.message) || err) };
    }
    this.busy = false;

    const state = nextStateAfterResolve(item, response);
    if (state.done) {
      this.close();
      return;
    }
    // Still not storable — keep the dialog up so it "pops up again".
    this.current = state.item || item;
    this.render(state.message);
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
