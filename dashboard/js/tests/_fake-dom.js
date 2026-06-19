/**
 * Tiny DOM double for the implementation/ tests. NOT a test file (no `.test.`
 * suffix, so Bun won't execute it). It implements just enough of the DOM API
 * the concrete classes touch: createElement, getElementById, querySelector(All),
 * classList, dataset, innerHTML/insertAdjacentHTML, appendChild/prepend,
 * scrollTop/scrollHeight.
 *
 * Querying walks the live child tree (built via createElement/appendChild), so
 * it only understands simple selectors: `.class`, `#id`, `tag`, `[data-x]`,
 * `[data-x="v"]`. Setting `.innerHTML` to a string clears children (matching the
 * browser) — code under test builds queryable structure with createElement.
 */

const camel = (name) =>
  name.replace(/^data-/, "").replace(/-([a-z])/g, (_, c) => c.toUpperCase());

class FakeClassList {
  constructor() {
    this._set = new Set();
  }
  add(...cs) {
    for (const c of cs) if (c) this._set.add(c);
  }
  remove(...cs) {
    for (const c of cs) this._set.delete(c);
  }
  contains(c) {
    return this._set.has(c);
  }
  toggle(c, force) {
    const want = force === undefined ? !this._set.has(c) : !!force;
    if (want) this._set.add(c);
    else this._set.delete(c);
    return want;
  }
  get value() {
    return [...this._set].join(" ");
  }
}

export class FakeElement {
  constructor(tag = "div", doc = null) {
    this.tagName = String(tag).toUpperCase();
    this._doc = doc;
    this.classList = new FakeClassList();
    this.dataset = {};
    this.style = {};
    this.children = [];
    this.parent = null;
    this.id = "";
    this.type = "";
    this.value = "";
    this.textContent = "";
    this.placeholder = "";
    this.disabled = false;
    this.scrollTop = 0;
    this.scrollHeight = 0;
    this._innerHTML = "";
    this._listeners = {};
  }

  get className() {
    return this.classList.value;
  }
  set className(v) {
    this.classList = new FakeClassList();
    for (const c of String(v || "").split(/\s+/)) this.classList.add(c);
  }

  get innerHTML() {
    return this._innerHTML;
  }
  set innerHTML(v) {
    this._innerHTML = String(v);
    this.children = []; // browser parity: assigning innerHTML replaces children
  }

  insertAdjacentHTML(pos, html) {
    if (pos === "beforeend") this._innerHTML += html;
    else this._innerHTML = html + this._innerHTML;
  }

  appendChild(child) {
    child.parent = this;
    this.children.push(child);
    return child;
  }
  remove() {
    if (this.parent) {
      this.parent.children = this.parent.children.filter((c) => c !== this);
      this.parent = null;
    }
  }
  append(...kids) {
    for (const k of kids) this.appendChild(k);
  }
  prepend(...kids) {
    this.children.unshift(...kids);
    for (const k of kids) k.parent = this;
  }

  addEventListener(type, fn) {
    if (!this._listeners[type]) this._listeners[type] = [];
    this._listeners[type].push(fn);
  }
  dispatch(type, evt = {}) {
    for (const fn of this._listeners[type] || []) fn(evt);
  }
  /** Convenience for tests: fire the first click listener. */
  click() {
    this.dispatch("click", {});
  }

  matches(sel) {
    // Support a comma list (`a, b`) and compound simple selectors
    // (`.tab[data-report-key]`) by splitting into parts that must all match.
    for (const group of sel.split(",")) {
      if (this._matchesCompound(group.trim())) return true;
    }
    return false;
  }

  _matchesCompound(sel) {
    if (!sel) return false;
    // Split a compound selector into its `.class` / `#id` / `[attr]` / `tag`
    // pieces; every piece must match the same element.
    const parts = sel.match(/(\[[^\]]*\]|[.#]?[\w-]+)/g) || [];
    return parts.every((p) => this._matchesSimple(p));
  }

  _matchesSimple(sel) {
    if (sel.startsWith(".")) return this.classList.contains(sel.slice(1));
    if (sel.startsWith("#")) return this.id === sel.slice(1);
    const attr = sel.match(/^\[([\w-]+)(?:="([^"]*)")?\]$/);
    if (attr) {
      const key = camel(attr[1]);
      if (attr[2] === undefined) return this.dataset[key] !== undefined;
      return this.dataset[key] === attr[2];
    }
    return this.tagName === sel.toUpperCase();
  }

  _walk(out) {
    for (const c of this.children) {
      out.push(c);
      c._walk(out);
    }
    return out;
  }

  querySelectorAll(sel) {
    return this._walk([]).filter((el) => el.matches(sel));
  }
  querySelector(sel) {
    return this.querySelectorAll(sel)[0] || null;
  }
}

export class FakeDocument {
  constructor() {
    this._all = [];
  }
  createElement(tag) {
    const el = new FakeElement(tag, this);
    this._all.push(el);
    return el;
  }
  /** Register a pre-built element (e.g. a section) so getElementById finds it. */
  add(el) {
    this._all.push(el);
    return el;
  }
  getElementById(id) {
    return this._all.find((el) => el.id === id) || null;
  }
  querySelectorAll(sel) {
    return this._all.filter((el) => el.matches(sel));
  }
  querySelector(sel) {
    return this.querySelectorAll(sel)[0] || null;
  }
}
