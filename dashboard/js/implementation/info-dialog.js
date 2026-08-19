/**
 * InfoDialog — a single win98-styled "Info" message box (title bar + one
 * message + one OK button), matching the 98.css chrome already loaded on
 * this page (css/vendor/98css/98.css: .window/.title-bar/.window-body).
 *
 * A plain concrete class, not a port + adapter: there is exactly one way this
 * box is ever shown (an OK-only informational note), so an interface with a
 * single implementation would be the "meaningless abstraction" the GoF
 * debugging guide warns against -- worth revisiting only if a second kind of
 * dialog (e.g. confirm/cancel) needs to share this shell.
 *
 * Built lazily and reused: `show(message)` mounts once on first call and
 * simply updates the message text/visibility after that, so repeated triggers
 * (e.g. every fill button on a long session) don't grow the DOM.
 */
export class InfoDialog {
  /**
   * @param {{root: Element, doc: Document, title?: string}} opts
   */
  constructor({ root, doc, title = "Info" }) {
    if (!root) throw new TypeError("InfoDialog requires a mount element");
    this.root = root;
    this.doc = doc;
    this.title = title;
    this._el = null;
    this._messageEl = null;
  }

  _ensureBuilt() {
    if (this._el) return;
    const overlay = this._make("div", "info-dialog-overlay");
    const win = this._make("div", "window info-dialog-window");
    overlay.appendChild(win);

    const titleBar = this._make("div", "title-bar");
    const titleText = this._make("div", "title-bar-text");
    titleText.textContent = this.title;
    titleBar.appendChild(titleText);
    win.appendChild(titleBar);

    const body = this._make("div", "window-body info-dialog-body");
    this._messageEl = this._make("p");
    body.appendChild(this._messageEl);
    const footer = this._make("div", "info-dialog-footer");
    // Exposed on the instance (not just buried in the child tree) so a test
    // can press it without depending on the DOM structure above.
    this._okButton = this._make("button");
    this._okButton.type = "button";
    this._okButton.textContent = "OK";
    this._okButton.addEventListener("click", () => this.hide());
    footer.appendChild(this._okButton);
    body.appendChild(footer);
    win.appendChild(body);

    // Clicking the dimmed backdrop is the same as pressing OK -- there is
    // nothing destructive behind this dialog to protect against a stray
    // dismiss, unlike a confirm/cancel prompt.
    overlay.addEventListener("click", (event) => {
      if (event.target === overlay) this.hide();
    });

    this.root.appendChild(overlay);
    this._el = overlay;
    this._el.style.display = "none";
  }

  _make(tag, className) {
    const node = this.doc.createElement(tag);
    if (className) node.className = className;
    return node;
  }

  /** @param {string} message */
  show(message) {
    this._ensureBuilt();
    this._messageEl.textContent = message;
    this._el.style.display = "flex";
  }

  hide() {
    if (this._el) this._el.style.display = "none";
  }
}
