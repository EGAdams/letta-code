import { abstractMethod } from "./not-implemented.js";

/**
 * VendorReviewView — the output Strategy for the "Needs Vendor Review" panel.
 *
 * A receipt whose vendor/category couldn't be auto-resolved is saved anyway
 * (image + a NULL-category expense row, expense_status=NEEDS_VENDOR_KEY —
 * see save_receipt_pending_vendor_review() in rol_finances) instead of being
 * dropped. This view lists those rows and lets a human finish the save by
 * picking an existing vendor_key. VendorReviewController drives it; nothing
 * here talks to the network directly, so a fake view keeps the controller
 * unit-testable.
 */
export class VendorReviewView {
  /**
   * Render the current list of receipts awaiting a vendor pick.
   * @param {Array<{expense_id:number, expense_date:string, amount:string,
   *                 description:string, image_url:?string}>} _rows
   */
  renderPending(_rows) {
    abstractMethod("renderPending");
  }

  /** Render a transport/load failure message. */
  renderError(_message) {
    abstractMethod("renderError");
  }
}
