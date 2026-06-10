import { abstractMethod } from "./not-implemented.js";

/**
 * ConsoleView — Builder + Composite, with a Template Method for de-duplication.
 *
 * The "MSI installer" scrolling console appears three times (agent streams,
 * server logs, chat replies). Each appends entries, skips ones already seen
 * (the `seen` Set keyed by date|type|text or by seq), and auto-scrolls.
 *
 * The dedup + first-render bookkeeping is the shared template logic and lives
 * here. The DOM primitives (`writeHtml`, `clearDom`, `scrollToBottom`) are
 * abstract so the implementation can bind them to a real element while tests
 * use a string-buffer fake.
 */
export class ConsoleView {
  constructor() {
    this._seen = new Set();
    this._first = true;
  }

  /** Abstract: append raw HTML to the console body. */
  writeHtml(_html) {
    abstractMethod("writeHtml");
  }

  /** Abstract: replace the console body with raw HTML. */
  replaceHtml(_html) {
    abstractMethod("replaceHtml");
  }

  /** Abstract: scroll the console to the newest line. */
  scrollToBottom() {
    abstractMethod("scrollToBottom");
  }

  /** Reset dedup state — call when (re)mounting on a new target. */
  reset() {
    this._seen = new Set();
    this._first = true;
  }

  /** Whether no rows have been rendered yet this session. */
  get isFirstRender() {
    return this._first;
  }

  /**
   * Render an empty-state placeholder exactly once (on first render with no
   * rows). Returns true if it handled the empty case.
   */
  renderEmptyOnce(html) {
    if (this._first) {
      this.replaceHtml(html);
      this._first = false;
      return true;
    }
    return false;
  }

  /**
   * Template Method: append a row only if its dedup `key` is unseen.
   * On the very first non-empty render it clears the placeholder first.
   * Returns true if the row was newly appended.
   */
  appendUnique(key, html, { autoScroll = true } = {}) {
    if (this._first) {
      this.replaceHtml("");
      this._first = false;
    }
    if (this._seen.has(key)) return false;
    this._seen.add(key);
    this.writeHtml(html);
    if (autoScroll) this.scrollToBottom();
    return true;
  }
}
