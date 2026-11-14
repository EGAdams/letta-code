import { diffNavTabs } from "../abstract/nav-live-sync.js";
import {
  parseNavMainTabs,
  parseViewSection,
} from "../abstract/nav-markup-parser.js";

/**
 * DomNavLiveSync — polls the lightweight `/api/nav-status` signature and,
 * only when it changes, fetches the live page and patches the open DOM: new
 * top-level sidebar tabs (and their view section, if the fetched markup has
 * one) are inserted, tabs that disappeared are removed. Never a full reload —
 * the caller's current view and active tab are left exactly as they were.
 *
 * A tab this adds gets the same generic click behaviour every existing
 * main-nav tab falls back to in bindMainNav: select it, activate its view.
 * Anything that needs more than that (its own sub-nav, a live poll) gets its
 * own case hand-added to bindMainNav later, same as every tab before it.
 *
 * Reconnection: a failed poll or page fetch is swallowed and retried on the
 * next tick without ever updating the stored signature, so a server restart
 * or network blip just delays the next successful sync instead of losing it.
 * `_syncing` makes poll() a no-op while one is already in flight, so a slow
 * fetch can never overlap the next tick and double-add a tab.
 */
export class DomNavLiveSync {
  constructor({
    http,
    doc = globalThis.document,
    nav,
    viewNav,
    fetchFn = globalThis.fetch?.bind(globalThis),
    pageUrl = "/",
    intervalMs = 15000,
    setInterval: setIntervalFn = globalThis.setInterval?.bind(globalThis),
  } = {}) {
    if (!http) throw new Error("DomNavLiveSync requires an HttpClient");
    if (!nav?.main) throw new Error("DomNavLiveSync requires nav.main");
    if (!viewNav) throw new Error("DomNavLiveSync requires a viewNav");
    this._http = http;
    this._doc = doc;
    this._nav = nav;
    this._viewNav = viewNav;
    this._fetch = fetchFn;
    this._pageUrl = pageUrl;
    this._intervalMs = intervalMs;
    this._setInterval = setIntervalFn;
    this._signature = null;
    this._syncing = false;
  }

  /** Record the current signature (no sync — the page already matches it), then arm the loop. */
  async start() {
    try {
      const status = await this._http.getJSON("/api/nav-status");
      this._signature = status.signature;
    } catch {
      /* first read failed; poll() will fetch+compare properly next tick */
    }
    if (this._setInterval)
      this._setInterval(() => this.poll(), this._intervalMs);
  }

  async poll() {
    if (this._syncing) return;
    this._syncing = true;
    try {
      await this._pollOnce();
    } finally {
      this._syncing = false;
    }
  }

  async _pollOnce() {
    let status;
    try {
      status = await this._http.getJSON("/api/nav-status");
    } catch {
      return;
    }
    if (status.signature === this._signature) return;
    if (!this._fetch) return;
    let html;
    try {
      const res = await this._fetch(this._pageUrl, { cache: "no-store" });
      if (!res.ok) return;
      html = await res.text();
    } catch {
      return;
    }
    this._applyMarkup(html);
    this._signature = status.signature;
  }

  _currentTargets() {
    return [
      ...this._nav.main.querySelectorAll('[data-nav="main"][data-target]'),
    ].map((el) => el.dataset.target);
  }

  _applyMarkup(html) {
    const nextTabs = parseNavMainTabs(html);
    const { toAdd, toRemove } = diffNavTabs(this._currentTargets(), nextTabs);
    const order = nextTabs.map((tab) => tab.target);
    for (const tab of toAdd) this._addTab(tab, html, order);
    for (const target of toRemove) this._removeTab(target);
  }

  _addTab({ target, label }, html, order) {
    // Idempotent: a tab already on screen (added by an earlier tick, or
    // present since page load) is never duplicated.
    if (this._nav.main.querySelector(`[data-target="${target}"]`)) return;
    const button = this._doc.createElement("button");
    button.type = "button";
    button.className = "tab";
    button.dataset.nav = "main";
    button.dataset.target = target;
    button.textContent = label;
    button.addEventListener("click", () => {
      this._viewNav.setActive(
        this._nav.main,
        '[data-nav="main"][data-target]',
        button,
      );
      this._viewNav.activateView(target);
    });
    this._insertAtPosition(button, target, order);
    this._addViewSection(target, html);
  }

  // Keep the fetched order rather than always appending, so a tab inserted
  // ahead of existing ones (e.g. "above Debugger") lands in the right place.
  _insertAtPosition(button, target, order) {
    const idx = order.indexOf(target);
    for (let i = idx + 1; i < order.length; i++) {
      const sibling = this._nav.main.querySelector(
        `[data-target="${order[i]}"]`,
      );
      if (sibling) {
        this._nav.main.insertBefore(button, sibling);
        return;
      }
    }
    this._nav.main.appendChild(button);
  }

  _addViewSection(target, html) {
    if (this._doc.getElementById(target)) return; // already has a view
    const parsed = parseViewSection(html, target);
    if (!parsed || !this._nav.mainContent) return;
    const section = this._doc.createElement("section");
    section.id = parsed.id;
    section.className = parsed.className;
    section.innerHTML = parsed.innerHTML;
    this._nav.mainContent.appendChild(section);
  }

  _removeTab(target) {
    const button = this._nav.main.querySelector(`[data-target="${target}"]`);
    // Never drop the tab the user is currently looking at out from under them.
    if (!button || button.classList.contains("active")) return;
    button.remove();
  }
}
