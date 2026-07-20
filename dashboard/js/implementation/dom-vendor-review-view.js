import { TextUtils } from "../abstract/text-utils.js";
import { VendorReviewView } from "../abstract/vendor-review-view.interface.js";

/**
 * DomVendorReviewView — concrete VendorReviewView rendering the "Needs Vendor
 * Review" panel + a shared vendor-picker modal into the DOM. The only
 * browser-dependent piece; VendorReviewController owns the fetch/refresh
 * logic and calls renderPending()/renderError() on this class.
 *
 * The two callbacks (getVendorKeys/onPickVendor) let this stay a thin DOM
 * binder without hard-depending on the concrete controller class — a fake of
 * either is enough to unit test in isolation.
 */
export class DomVendorReviewView extends VendorReviewView {
  /**
   * @param {{innerHTML:string, classList:DOMTokenList, querySelector:Function}} panelEl
   *   container the pending-rows list renders into
   * @param {{getVendorKeys: () => Promise<Array<{vendor_key:string, category_id:number,
   *           category_name:?string}>>, onPickVendor: (expenseId:number, vendorKey:string)
   *           => Promise<{ok:boolean, error?:string}>}} deps
   */
  constructor(panelEl, { getVendorKeys, onPickVendor } = {}) {
    super();
    if (!panelEl) {
      throw new Error("DomVendorReviewView requires a panel element");
    }
    if (
      typeof getVendorKeys !== "function" ||
      typeof onPickVendor !== "function"
    ) {
      throw new Error(
        "DomVendorReviewView requires { getVendorKeys, onPickVendor }",
      );
    }
    this._panel = panelEl;
    this._getVendorKeys = getVendorKeys;
    this._onPickVendor = onPickVendor;
    this._modal = this._buildModal();
  }

  renderPending(rows) {
    if (!Array.isArray(rows) || rows.length === 0) {
      this._panel.classList.add("hidden");
      this._panel.innerHTML = "";
      return;
    }
    this._panel.classList.remove("hidden");
    const items = rows
      .map((r) => {
        const imageLink = r.image_url
          ? `<a class="vendor-review-row-image" href="${TextUtils.esc(r.image_url)}" target="_blank" rel="noopener noreferrer">View scan</a>`
          : "";
        const summary = `${TextUtils.esc(r.expense_date || "")} · ${TextUtils.esc(r.amount || "")} · ${TextUtils.esc(r.description || "")}`;
        return (
          '<div class="vendor-review-row">' +
          `<span class="vendor-review-row-summary">${summary}</span>` +
          imageLink +
          `<button type="button" class="am-btn vendor-review-pick-btn" data-expense-id="${r.expense_id}">Pick Vendor</button>` +
          "</div>"
        );
      })
      .join("");
    this._panel.innerHTML =
      '<div class="vendor-review-title">Needs Vendor Review</div>' + items;
    for (const btn of this._panel.querySelectorAll(".vendor-review-pick-btn")) {
      btn.addEventListener("click", () => {
        this._openModal(Number(btn.getAttribute("data-expense-id")));
      });
    }
  }

  renderError(message) {
    this._panel.classList.remove("hidden");
    this._panel.innerHTML =
      '<div class="vendor-review-title">Needs Vendor Review</div>' +
      `<div class="vendor-picker-msg">Could not load: ${TextUtils.esc(message || "unknown error")}</div>`;
  }

  _buildModal() {
    const overlay = document.createElement("div");
    overlay.id = "vendor-picker-modal";
    overlay.className = "modal-overlay hidden";
    overlay.innerHTML =
      '<div class="modal-box">' +
      '<input type="text" class="vendor-picker-filter" placeholder="Filter vendor keys…" />' +
      '<ul class="vendor-picker-list"></ul>' +
      '<div class="vendor-picker-msg"></div>' +
      '<div class="modal-actions"><button type="button" class="am-btn vendor-picker-cancel">Cancel</button></div>' +
      "</div>";
    document.body.appendChild(overlay);
    overlay
      .querySelector(".vendor-picker-cancel")
      .addEventListener("click", () => overlay.classList.add("hidden"));
    return overlay;
  }

  async _openModal(expenseId) {
    const list = this._modal.querySelector(".vendor-picker-list");
    const filterInput = this._modal.querySelector(".vendor-picker-filter");
    const msg = this._modal.querySelector(".vendor-picker-msg");
    msg.textContent = "";
    filterInput.value = "";
    list.innerHTML = "<li>Loading vendor keys…</li>";
    this._modal.classList.remove("hidden");

    let vendorKeys = [];
    try {
      vendorKeys = await this._getVendorKeys();
    } catch (e) {
      list.innerHTML = "";
      msg.textContent = `Could not load vendor keys: ${e.message}`;
      return;
    }

    const renderList = (filterText) => {
      const needle = (filterText || "").trim().toLowerCase();
      const matches = needle
        ? vendorKeys.filter((v) => v.vendor_key.toLowerCase().includes(needle))
        : vendorKeys;
      list.innerHTML = matches
        .slice(0, 200)
        .map((v) => {
          const label = v.category_name
            ? `${v.vendor_key} — ${v.category_name}`
            : v.vendor_key;
          return (
            `<li><button type="button" class="vendor-picker-item" data-vendor-key="${TextUtils.esc(v.vendor_key)}">` +
            `${TextUtils.esc(label)}</button></li>`
          );
        })
        .join("");
      for (const btn of list.querySelectorAll(".vendor-picker-item")) {
        btn.addEventListener("click", async () => {
          msg.textContent = "";
          const vendorKey = btn.getAttribute("data-vendor-key");
          const result = await this._onPickVendor(expenseId, vendorKey);
          if (result && result.ok) {
            this._modal.classList.add("hidden");
          } else {
            msg.textContent =
              (result && result.error) || "Could not set vendor.";
          }
        });
      }
    };

    renderList("");
    filterInput.oninput = () => renderList(filterInput.value);
  }
}
