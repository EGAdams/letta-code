/**
 * A one-slot handle on a widget that mounts itself.
 *
 * The Verified Transactions table and the review dialog (ManualEntryForm) are
 * two independent mount points on the same report page — Python renders each
 * one's <div> and each one's <script type="module">, in that order or the
 * other, with no composition root between them. Clicking Edit on a row has to
 * reach the dialog, and the dialog may not have mounted yet.
 *
 * The alternatives were worse. A global (`window.__manualEntryForm`) is an
 * agreement nothing declares and nothing tests. Digging the instance out of a
 * DOM node couples the table to the dialog's markup. A custom event needs both
 * sides listening before either one speaks, which is the exact race here.
 *
 * So: whoever mounts publishes, whoever needs it awaits, and late arrivals get
 * the value immediately. An ES module is a per-page singleton, which is what
 * makes the shared slot work at all.
 */

export class MountedWidgetRegistry {
  constructor() {
    this._value = null;
    this._waiting = [];
  }

  /** The mounted widget, or null if nothing has mounted yet. */
  get current() {
    return this._value;
  }

  /** Hand over the mounted widget and release anyone waiting for it. */
  publish(widget) {
    this._value = widget || null;
    const waiting = this._waiting;
    this._waiting = [];
    for (const resolve of waiting) resolve(this._value);
    return this._value;
  }

  /**
   * Resolve once something is published. `timeoutMs` resolves to null instead
   * of hanging: a page that renders the table without the review dialog is a
   * real shape (see expense_edit_panel_html), and the Edit button there should
   * say it cannot open rather than wait forever.
   */
  whenMounted({ timeoutMs = 0, setTimeout: setTimeoutFn = null } = {}) {
    if (this._value) return Promise.resolve(this._value);
    return new Promise((resolve) => {
      this._waiting.push(resolve);
      const timer = setTimeoutFn || globalThis.setTimeout;
      if (timeoutMs > 0 && typeof timer === "function") {
        timer(() => {
          if (!this._value) resolve(null);
        }, timeoutMs);
      }
    });
  }

  /** Drop the slot. Tests share this module the way a page shares it. */
  reset() {
    this._value = null;
    this._waiting = [];
  }
}

/** The review dialog on a report page — one per page, published by mount(). */
export const manualEntryFormRegistry = new MountedWidgetRegistry();

/** The server-rendered Verified Transactions table controller, one per page. */
export const verifiedTransactionRowsRegistry = new MountedWidgetRegistry();
