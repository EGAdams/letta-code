import { abstractMethod } from "./not-implemented.js";

/**
 * NavigationController — State pattern (sidebar panel state machine).
 *
 * The sidebar has one "main" nav plus several sub-navs (status, tools, agents,
 * agent-detail, servers, plans). Exactly one panel is visible at a time;
 * entering a section hides main and shows that section's panel with a default
 * view+tab; "Back" returns to main/home. That is a small state machine.
 *
 * The transition table is concrete, data-driven, and testable. The four DOM
 * effects are abstract primitives bound by the implementation:
 *   showPanel / hidePanel / activateView / setActiveTab
 * Each fires through these so a test double can assert the exact sequence.
 */
export class NavigationController {
  /**
   * @param {Record<string,{panel:string,view:string,tab?:string}>} sections
   *   Map of main-tab target → the panel/view/tab to show on entry.
   * @param {string} [mainPanel="nav-main"]
   * @param {string} [homeView="home"]
   */
  constructor(sections, { mainPanel = "nav-main", homeView = "home" } = {}) {
    this.sections = sections;
    this.mainPanel = mainPanel;
    this.homeView = homeView;
    this.activePanel = mainPanel;
  }

  /** Abstract: reveal a nav panel by id. */
  showPanel(_panelId) {
    abstractMethod("showPanel");
  }

  /** Abstract: hide a nav panel by id. */
  hidePanel(_panelId) {
    abstractMethod("hidePanel");
  }

  /** Abstract: show the content section with this id, hide the rest. */
  activateView(_viewId) {
    abstractMethod("activateView");
  }

  /** Abstract: mark `target` as the active tab within `panelId`. */
  setActiveTab(_panelId, _target) {
    abstractMethod("setActiveTab");
  }

  /**
   * Enter a section: hide the current panel, show the section's panel, and
   * activate its default view/tab. Returns false for an unknown section.
   */
  enterSection(name) {
    const spec = this.sections[name];
    if (!spec) return false;
    this.hidePanel(this.activePanel);
    this.showPanel(spec.panel);
    this.activePanel = spec.panel;
    if (spec.tab) this.setActiveTab(spec.panel, spec.tab);
    this.activateView(spec.view);
    return true;
  }

  /** Activate a sibling view within the current panel and mark its tab. */
  selectView(target) {
    this.setActiveTab(this.activePanel, target);
    this.activateView(target);
  }

  /** Return to the main nav and home view. */
  back() {
    if (this.activePanel !== this.mainPanel) {
      this.hidePanel(this.activePanel);
      this.showPanel(this.mainPanel);
      this.activePanel = this.mainPanel;
    }
    this.setActiveTab(this.mainPanel, this.homeView);
    this.activateView(this.homeView);
  }
}
