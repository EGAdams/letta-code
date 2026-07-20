/**
 * VendorReviewController — Command for the "Needs Vendor Review" panel.
 *
 * Backs the dashboard's "pick a vendor" flow: a scan that couldn't be
 * auto-categorized is saved anyway with expense_status=NEEDS_VENDOR_KEY, and
 * this controller lists those rows (GET /api/pending-vendor-review), fetches
 * the pickable vendor_key list (GET /api/vendor-keys, cached), and finishes
 * the save once a human picks one (POST /api/set-receipt-vendor).
 *
 * Programs to two interfaces — HttpClient (transport) and VendorReviewView
 * (presentation) — both injected, so it is unit-testable with a fake http and
 * a recording view.
 */
export class VendorReviewController {
  /**
   * @param {{ http: import("../abstract/http-client.interface.js").HttpClient,
   *           view: import("../abstract/vendor-review-view.interface.js").VendorReviewView }} deps
   */
  constructor({ http, view } = {}) {
    if (!http || typeof http.getJSON !== "function") {
      throw new Error("VendorReviewController requires { http }");
    }
    if (!view || typeof view.renderPending !== "function") {
      throw new Error("VendorReviewController requires { view }");
    }
    this._http = http;
    this._view = view;
    this._vendorKeysCache = null;
  }

  /** Reload the pending list and push it to the view. */
  async refresh() {
    try {
      const result = await this._http.getJSON("/api/pending-vendor-review");
      const rows = result && result.ok ? result.rows || [] : [];
      this._view.renderPending(rows);
      return rows;
    } catch (e) {
      this._view.renderError(e.message);
      return [];
    }
  }

  /** Every known vendor_key + category, cached for the lifetime of this controller. */
  async listVendorKeys() {
    if (this._vendorKeysCache) return this._vendorKeysCache;
    const result = await this._http.getJSON("/api/vendor-keys");
    this._vendorKeysCache = result && result.ok ? result.vendor_keys || [] : [];
    return this._vendorKeysCache;
  }

  /**
   * Finish a pending save by applying a human-picked vendor_key.
   * @param {number} expenseId
   * @param {string} vendorKey
   * @returns {Promise<object>} the /api/set-receipt-vendor response
   */
  async pickVendor(expenseId, vendorKey) {
    const result = await this._http.postJSON("/api/set-receipt-vendor", {
      expense_id: expenseId,
      vendor_key: vendorKey,
    });
    if (result && result.ok) {
      await this.refresh();
    }
    return result;
  }
}
