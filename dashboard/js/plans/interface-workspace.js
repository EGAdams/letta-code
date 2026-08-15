import { STATUS_LABELS, validateSpecs } from "./interface-spec.js";

/**
 * InterfaceWorkspace — the SPA shell: a nav of interfaces on one side, the
 * selected interface's page on the other.
 *
 * Deliberately generic. It knows about `InterfaceSpec` and nothing about voice
 * communication, so pointing it at a different set of specs produces a
 * workspace for a different project. The page renderer is injected, so how a
 * tab looks is not this class's business either.
 *
 * Routing is by `location.hash`, which makes a tab linkable — the point of
 * "open Project Plans → Voice Communication → IConversationAgent and see where
 * development stopped".
 */
export class InterfaceWorkspace {
  constructor({
    specs,
    pageRenderer,
    mermaidView = null,
    doc = globalThis.document,
    win = globalThis,
  }) {
    if (!pageRenderer)
      throw new Error("InterfaceWorkspace requires a page renderer");
    this._specs = validateSpecs(specs);
    this._pages = pageRenderer;
    this._mermaid = mermaidView;
    this._doc = doc;
    this._win = win;
    this._navButtons = new Map();
    this._currentId = null;
  }

  get currentId() {
    return this._currentId;
  }

  _el(tag, className, props = {}) {
    const el = this._doc.createElement(tag);
    if (className) el.className = className;
    Object.assign(el, props);
    return el;
  }

  /** Build the nav into `navTarget` and mount pages into `contentTarget`. */
  mount(navTarget, contentTarget) {
    const content = this._doc.getElementById(contentTarget);
    if (!content) return null;
    this._content = content;

    if (navTarget) {
      const nav = this._doc.getElementById(navTarget);
      if (!nav) return null;
      nav.innerHTML = "";

      let group = null;
      for (const spec of this._specs) {
        if (spec.group && spec.group !== group) {
          group = spec.group;
          nav.append(this._el("div", "nav-group", { textContent: group }));
        }
        const button = this._el("button", "nav-item", {
          type: "button",
          textContent: spec.name,
        });
        button.dataset.specId = spec.id;
        button.append(
          this._el("span", `dot status-${spec.status}`, {
            title: STATUS_LABELS[spec.status],
          }),
        );
        button.addEventListener("click", () => this.show(spec.id));
        nav.append(button);
        this._navButtons.set(spec.id, button);
      }
    }

    this._win.addEventListener?.("hashchange", () => this._showFromHash());
    return this._showFromHash();
  }

  _showFromHash() {
    const raw = String(this._win.location?.hash || "").replace(/^#/, "");
    const wanted = this._specs.some((s) => s.id === raw)
      ? raw
      : this._specs[0].id;
    return this.show(wanted, { updateHash: false });
  }

  /** Switch to one interface's page. */
  async show(id, { updateHash = true } = {}) {
    const spec = this._specs.find((s) => s.id === id);
    if (!spec || !this._content) return null;

    // Showing the tab that is already open is a no-op, and that guard is what
    // keeps the page correct rather than merely saving work: this workspace can
    // be driven from two places at once — the dashboard's own Voice
    // Communication sub-nav calls show() AND sets the iframe's hash, which
    // fires our hashchange listener and calls show() a second time for the same
    // spec. render() is async (it awaits Mermaid), so two overlapping calls
    // used to interleave: the second cleared the container mid-flight and both
    // then appended, producing duplicated "2 · Contract … 7 · Next work"
    // sections and pan/zoom attached to detached SVGs ("matrix is not
    // invertible"). One render per tab, always.
    if (this._currentId === spec.id) return spec;

    // Old diagrams keep window resize listeners and pan/zoom instances alive;
    // drop them before the DOM they point at is replaced.
    this._mermaid?.destroyAll();

    this._currentId = spec.id;
    for (const [specId, button] of this._navButtons)
      button.classList.toggle("active", specId === spec.id);
    if (updateHash && this._win.location) this._win.location.hash = spec.id;

    await this._pages.render(this._content, spec);
    this._content.scrollTop = 0;
    return spec;
  }
}
