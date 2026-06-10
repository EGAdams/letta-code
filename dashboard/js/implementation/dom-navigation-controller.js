import { NavigationController } from "../abstract/navigation-controller.interface.js";

/**
 * DomNavigationController — concrete NavigationController bound to the sidebar
 * DOM. The state machine (enterSection / selectView / back) is inherited; this
 * binds the four DOM effects:
 *
 *   showPanel    → remove the `hidden` class from a nav panel
 *   hidePanel    → add the `hidden` class to a nav panel
 *   activateView → clear `active` from every `.view`, set it on one section
 *   setActiveTab → within a panel, mark the tab whose data-target matches
 *
 * Selectors / class names are configurable; `doc` is injectable for tests.
 */
export class DomNavigationController extends NavigationController {
  constructor(
    sections,
    {
      doc = globalThis.document,
      hiddenClass = "hidden",
      activeClass = "active",
      viewSelector = ".view",
      tabSelector = "[data-target]",
      ...opts
    } = {},
  ) {
    super(sections, opts);
    this._doc = doc;
    this._hidden = hiddenClass;
    this._active = activeClass;
    this._viewSelector = viewSelector;
    this._tabSelector = tabSelector;
  }

  /** @override */
  showPanel(panelId) {
    const el = this._doc.getElementById(panelId);
    if (el) el.classList.remove(this._hidden);
  }

  /** @override */
  hidePanel(panelId) {
    const el = this._doc.getElementById(panelId);
    if (el) el.classList.add(this._hidden);
  }

  /** @override */
  activateView(viewId) {
    for (const v of this._doc.querySelectorAll(this._viewSelector)) {
      v.classList.remove(this._active);
    }
    const el = this._doc.getElementById(viewId);
    if (el) el.classList.add(this._active);
  }

  /** @override */
  setActiveTab(panelId, target) {
    const panel = this._doc.getElementById(panelId);
    if (!panel) return;
    for (const t of panel.querySelectorAll(this._tabSelector)) {
      t.classList.remove(this._active);
    }
    const tab = panel.querySelector(`[data-target="${target}"]`);
    if (tab) tab.classList.add(this._active);
  }
}
