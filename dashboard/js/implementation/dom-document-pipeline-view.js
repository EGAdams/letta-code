import { DocumentPipelineView } from "../abstract/document-pipeline-view.interface.js";
import { TextUtils } from "../abstract/text-utils.js";
import { describePipelineStage } from "./document-pipeline-controller.js";

/**
 * DomDocumentPipelineView — concrete DocumentPipelineView that renders the
 * pipeline result into a DOM container inside a scanner dialog. The only
 * browser-dependent piece; all formatting decisions live in the pure
 * describePipelineStage() so this class stays a thin DOM binder.
 */
export class DomDocumentPipelineView extends DocumentPipelineView {
  /** @param {{innerHTML:string, classList:DOMTokenList}} container */
  constructor(container) {
    super();
    if (!container) {
      throw new Error("DomDocumentPipelineView requires a container element");
    }
    this._el = container;
  }

  clear() {
    this._el.classList.add("hidden");
    this._el.innerHTML = "";
  }

  setBusy() {
    this._el.classList.remove("hidden");
    this._el.innerHTML =
      '<div class="pipeline-title">Processing document…</div>' +
      '<div class="pipeline-busy">Running classify → parse ' +
      "(cheapest reliable tool first)…</div>";
  }

  renderError(message) {
    this._el.classList.remove("hidden");
    this._el.innerHTML =
      '<div class="pipeline-title">Document pipeline</div>' +
      `<div class="pipeline-error">Pipeline failed: ${TextUtils.esc(
        message || "unknown error",
      )}</div>`;
  }

  requestStatementMetadata(result) {
    const current = result?.statement_metadata || {};
    return new Promise((resolve) => {
      const overlay = document.createElement("div");
      overlay.className = "modal-overlay statement-metadata-modal";
      overlay.innerHTML =
        '<form class="modal-box statement-metadata-form">' +
        "<h3>Bank statement details required</h3>" +
        "<p>Confirm the bank and enter the final four account digits before this statement is stored.</p>" +
        '<label>Bank name<input name="bank_name" required></label>' +
        '<label>Account last 4<input name="account_last4" inputmode="numeric" pattern="[0-9]{4}" maxlength="4" required></label>' +
        '<div class="statement-metadata-error" aria-live="polite"></div>' +
        '<div class="modal-actions"><button type="button" class="am-btn metadata-cancel">Cancel</button>' +
        '<button type="submit" class="am-btn">Continue intake</button></div>' +
        "</form>";
      const bank = overlay.querySelector('[name="bank_name"]');
      const last4 = overlay.querySelector('[name="account_last4"]');
      const error = overlay.querySelector(".statement-metadata-error");
      bank.value = current.bank_name || "";
      last4.value = current.account_last4 || "";
      const finish = (value) => {
        overlay.remove();
        resolve(value);
      };
      overlay
        .querySelector(".metadata-cancel")
        .addEventListener("click", () => {
          finish(null);
        });
      overlay.querySelector("form").addEventListener("submit", (event) => {
        event.preventDefault();
        const bankName = bank.value.trim().replace(/\s+/g, " ");
        const accountLast4 = last4.value.trim();
        if (!bankName || !/^\d{4}$/.test(accountLast4)) {
          error.textContent =
            "Enter a bank name and exactly four account digits.";
          return;
        }
        finish({ bank_name: bankName, account_last4: accountLast4 });
      });
      document.body.appendChild(overlay);
      (bank.value ? last4 : bank).focus();
    });
  }

  render(result) {
    this._el.classList.remove("hidden");
    const stages = Array.isArray(result?.stages) ? result.stages : [];
    const rows = stages
      .map((s) => {
        const d = describePipelineStage(s);
        return (
          `<li class="pipeline-stage stage-${TextUtils.esc(d.status)}">` +
          `<span class="pipeline-stage-name">${TextUtils.esc(d.name)}</span>` +
          `<span class="pipeline-stage-status">${TextUtils.esc(d.status)}</span>` +
          `<span class="pipeline-stage-summary">${TextUtils.esc(d.summary)}</span>` +
          "</li>"
        );
      })
      .join("");
    const note = result?.mazda_dispatched
      ? "Mazda is processing investigate → categorize → store in the background."
      : "Mazda was not dispatched (no scanned image found).";
    const errorText = result?.stage_error || result?.error;
    const err = errorText
      ? `<div class="pipeline-error">${TextUtils.esc(errorText)}</div>`
      : "";
    this._el.innerHTML =
      '<div class="pipeline-title">Document pipeline</div>' +
      err +
      `<ul class="pipeline-stages">${rows}</ul>` +
      `<div class="pipeline-note">${TextUtils.esc(note)}</div>`;
  }
}
