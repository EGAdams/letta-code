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
 * it can be tested without a browser; this class is DOM + injected ports only.
 */
import { PollingController } from "../abstract/polling-controller.interface.js";
import {
  answerableFields,
  buildMazdaReviewPrompt,
  buildResolvePayload,
  collectCorrections,
  isSubmittable,
  nextPendingReview,
  nextStateAfterResolve,
  prefillFor,
  REVIEW_KIND,
  reviewIdentity,
} from "../abstract/statement-review.interface.js";
import { StatementReviewActions } from "../abstract/statement-review-actions.interface.js";

const POLL_MS = 15000;
const DEFERRED_STORAGE_KEY = "dashboard.statementReviews.deferred";

export class StatementReviewDialog extends PollingController {
  constructor({
    http,
    pollMs = POLL_MS,
    doc = document,
    storage = globalThis.sessionStorage,
    actions,
    setInterval,
    clearInterval,
    // The dashboard is a single page with many unrelated tabs (Agents,
    // Server Management, ...); this dialog exists to gate the Scanner
    // workflow, not the whole app. Defaults to always-relevant so existing
    // callers/tests that don't care about scoping keep working unmodified.
    isRelevantView = () => true,
  } = {}) {
    super({
      intervalMs: pollMs,
      ...(setInterval ? { setInterval } : {}),
      ...(clearInterval ? { clearInterval } : {}),
    });
    if (!(actions instanceof StatementReviewActions)) {
      throw new TypeError(
        "StatementReviewDialog requires StatementReviewActions",
      );
    }
    this.http = http;
    this.doc = doc;
    this.current = null;
    this.values = {};
    this.storage = storage;
    this.actions = actions;
    this.deferredIds = this._loadDeferredIds();
    this.busy = false;
    this.root = null;
    this.isRelevantView = isRelevantView;
  }

  _loadDeferredIds() {
    try {
      const ids = JSON.parse(
        this.storage?.getItem(DEFERRED_STORAGE_KEY) || "[]",
      );
      return new Set(Array.isArray(ids) ? ids : []);
    } catch (_err) {
      return new Set();
    }
  }

  _saveDeferredIds() {
    try {
      if (this.storage) {
        this.storage.setItem(
          DEFERRED_STORAGE_KEY,
          JSON.stringify([...this.deferredIds]),
        );
      }
    } catch (_err) {
      /* Deferral still works in memory when browser storage is unavailable. */
    }
  }

  /** @override */
  async poll() {
    if (this.busy) return;
    try {
      const data = await this.http.getJSON("/api/statement-reviews");
      const reviews = data?.reviews || [];
      if (this.current) {
        // Keep a live item stable while someone types, but dismiss it when a
        // retry or another browser has actually removed that source from the
        // server queue. Previously a resolved workbook error stayed over the
        // scanner forever because current!=null disabled every future poll.
        const identity = reviewIdentity(this.current);
        const stillQueued = reviews.some(
          (item) => reviewIdentity(item) === identity,
        );
        if (!stillQueued) {
          this.close();
        } else {
          // Re-sync visibility each tick as a fallback for the immediate
          // syncVisibility() call other tabs' nav handlers make.
          this.render();
        }
        return;
      }
      const next = nextPendingReview(reviews, this.deferredIds);
      if (next) this.open(next);
    } catch (_err) {
      /* a poll failure is not worth interrupting the user for */
    }
  }

  /** Named alias retained for callers that request an immediate queue refresh. */
  async refresh() {
    return this.poll();
  }

  /**
   * Re-check isRelevantView() without waiting for the next poll tick. The
   * page's view-switch code calls this on every navigation so leaving the
   * Scanner tab immediately frees up the rest of the app instead of leaving
   * it blocked for up to POLL_MS.
   */
  syncVisibility() {
    if (this.current) this.render();
  }

  open(item) {
    this.current = item;
    this.values = {};
    answerableFields(item).forEach((entry) => {
      this.values[entry.key] = prefillFor(entry, entry.field);
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

  /** Detach the modal from the DOM without forgetting the queued item. */
  _hideRoot() {
    if (this.root) {
      this.root.remove();
      this.root = null;
    }
  }

  render(banner) {
    const item = this.current;
    if (!item) return;
    if (!this.isRelevantView()) {
      this._hideRoot();
      return;
    }
    const root = this._ensureRoot();
    const fields = answerableFields(item);
    const { errors } = collectCorrections(item, this.values);

    const rowsHtml = fields
      .map((entry) => {
        const err = errors[entry.key];
        const label =
          entry.field === "date"
            ? "Transaction date"
            : entry.field === "description"
              ? "Merchant or description"
              : "Expense amount";
        const currency =
          entry.field === "amount" ? '<span class="srd-currency">$</span>' : "";
        return `
        <label class="srd-row" data-index="${entry.index}" data-field="${entry.field}">
          <span class="srd-row-label">${escapeHtml(label)}
            <em>${escapeHtml(entry.description || "Unlabeled row")}</em></span>
          <span class="srd-input-wrap">
            ${currency}
            <input type="${entry.inputType}" ${
              entry.field === "amount" ? 'inputmode="decimal"' : ""
            } class="srd-amount"
                   data-key="${entry.key}"
                   value="${escapeHtml(this.values[entry.key] ?? "")}" />
          </span>
          ${err ? `<span class="srd-error">${escapeHtml(err)}</span>` : ""}
        </label>`;
      })
      .join("");

    const isWorkbook = item.kind === REVIEW_KIND.WORKBOOK;
    root.innerHTML = `
      <div class="srd-panel" role="dialog" aria-modal="true">
        <div class="srd-head">
          <h3>${isWorkbook ? "Add this card to the sheet" : "I need one detail"}</h3>
          <p>${escapeHtml(item.bank_name || "Statement")}${
            item.account_last4 ? ` ····${escapeHtml(item.account_last4)}` : ""
          }</p>
        </div>
        <div class="srd-body">
          <p class="srd-message">${escapeHtml(item.message || "")}</p>
          <div class="srd-document">
            <span>Offending document</span>
            <code>${escapeHtml(
              item.document_path || item.source_file || "Path unavailable",
            )}</code>
          </div>
          ${rowsHtml}
          ${banner ? `<p class="srd-banner">${escapeHtml(banner)}</p>` : ""}
        </div>
        <div class="srd-foot">
          <button type="button" class="srd-later">Leave for later</button>
          <button type="button" class="srd-ask-mazda">Ask Mazda</button>
          <button type="button" class="srd-show-document">Show Document</button>
          <button type="button" class="srd-ok"${this.busy ? " disabled" : ""}>${
            this.busy ? "Working…" : isWorkbook ? "OK" : "Save"
          }</button>
        </div>
      </div>`;

    root.querySelectorAll(".srd-amount").forEach((input) => {
      input.addEventListener("input", (event) => {
        this.values[event.target.dataset.key] = event.target.value;
      });
    });
    root.querySelector(".srd-later").addEventListener("click", () => {
      const identity = reviewIdentity(this.current);
      if (identity) {
        this.deferredIds.add(identity);
        this._saveDeferredIds();
      }
      this.close();
    });
    root.querySelector(".srd-ask-mazda").addEventListener("click", async () => {
      if (!this.current) return;
      const prompt = buildMazdaReviewPrompt(this.current);
      try {
        await this.actions.askMazda(prompt, this.current);
        this.close();
      } catch (err) {
        this.render(`Could not open Mazda: ${String(err?.message || err)}`);
      }
    });
    root.querySelector(".srd-show-document").addEventListener("click", () => {
      try {
        this.actions.showDocument(this.current?.document_url, this.current);
      } catch (err) {
        this.render(String(err?.message || err));
      }
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
      response = { ok: false, error: String(err?.message || err) };
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
