import { ConsoleView } from "../abstract/console-view.interface.js";

/**
 * DomConsoleView — concrete ConsoleView bound to a real `.msi-console` element.
 *
 * The dedup / first-render bookkeeping lives in the base class; this only binds
 * the three DOM primitives:
 *   writeHtml      → inner.insertAdjacentHTML('beforeend', …)
 *   replaceHtml    → inner.innerHTML = …
 *   scrollToBottom → box.scrollTop = box.scrollHeight
 *
 * `box` is the scrolling `.msi-console`; `inner` is its `.msi-inner` body.
 */
export class DomConsoleView extends ConsoleView {
  /**
   * @param {Element} box   the scrolling `.msi-console`
   * @param {Element} [inner] the `.msi-inner` body (looked up under box if omitted)
   */
  constructor(box, inner = box?.querySelector(".msi-inner")) {
    super();
    if (!box || !inner) {
      throw new Error(
        "DomConsoleView requires a console box with a .msi-inner child",
      );
    }
    this._box = box;
    this._inner = inner;
  }

  /** @override */
  writeHtml(html) {
    this._inner.insertAdjacentHTML("beforeend", html);
  }

  /** @override */
  replaceHtml(html) {
    this._inner.innerHTML = html;
  }

  /** @override */
  scrollToBottom() {
    this._box.scrollTop = this._box.scrollHeight;
  }

  /**
   * Build the standard MSI console shell inside `container` and return a view
   * bound to it. Elements are created via the DOM API (not an innerHTML string)
   * so the result is queryable immediately.
   *
   * @param {Element} container host element to mount into
   * @param {string} id suffix for the console's element id (`msi-<id>`)
   * @param {Document} [doc]
   * @returns {DomConsoleView}
   */
  static mount(container, id, doc = globalThis.document) {
    container.innerHTML = "";
    const box = doc.createElement("div");
    box.className = "msi-console";
    box.id = `msi-${id}`;
    const inner = doc.createElement("span");
    inner.className = "msi-inner";
    const cursor = doc.createElement("span");
    cursor.className = "msi-cursor";
    cursor.innerHTML = "&#9608;";
    box.appendChild(inner);
    box.appendChild(cursor);
    container.appendChild(box);
    return new DomConsoleView(box, inner);
  }
}
