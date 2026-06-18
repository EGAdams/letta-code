import { beforeEach, describe, expect, test } from "bun:test";
import { NavigationController } from "../abstract/navigation-controller.interface.js";

const SECTIONS = {
  status: { panel: "nav-status", view: "status-home", tab: "status-home" },
  "agent-management": {
    panel: "nav-agents",
    view: "agents-home",
    tab: "agents-home",
  },
  "project-plans": {
    panel: "nav-plans",
    view: "plans-self-evolving",
    tab: "plans-self-evolving",
  },
};

/** Records every DOM effect so transitions can be asserted as a sequence. */
class SpyNav extends NavigationController {
  constructor() {
    super(SECTIONS);
    this.log = [];
  }
  showPanel(id) {
    this.log.push(["show", id]);
  }
  hidePanel(id) {
    this.log.push(["hide", id]);
  }
  activateView(id) {
    this.log.push(["view", id]);
  }
  setActiveTab(panel, target) {
    this.log.push(["tab", panel, target]);
  }
}

describe("NavigationController (State)", () => {
  let nav;
  beforeEach(() => {
    nav = new SpyNav();
  });

  test("abstract primitives throw on the base", () => {
    const base = new NavigationController(SECTIONS);
    expect(() => base.showPanel("x")).toThrow(/showPanel\(\) is abstract/);
  });

  test("entering a section hides main, shows panel, sets tab+view", () => {
    expect(nav.enterSection("status")).toBe(true);
    expect(nav.activePanel).toBe("nav-status");
    expect(nav.log).toEqual([
      ["hide", "nav-main"],
      ["show", "nav-status"],
      ["tab", "nav-status", "status-home"],
      ["view", "status-home"],
    ]);
  });

  test("unknown section is rejected without side effects", () => {
    expect(nav.enterSection("bogus")).toBe(false);
    expect(nav.log).toHaveLength(0);
  });

  test("selectView switches view within the active panel", () => {
    nav.enterSection("project-plans");
    nav.log.length = 0;
    nav.selectView("plans-audio-input");
    expect(nav.log).toEqual([
      ["tab", "nav-plans", "plans-audio-input"],
      ["view", "plans-audio-input"],
    ]);
  });

  test("back returns to main/home", () => {
    nav.enterSection("agent-management");
    nav.log.length = 0;
    nav.back();
    expect(nav.activePanel).toBe("nav-main");
    expect(nav.log).toEqual([
      ["hide", "nav-agents"],
      ["show", "nav-main"],
      ["tab", "nav-main", "home"],
      ["view", "home"],
    ]);
  });

  test("back from main does not double-hide", () => {
    nav.back();
    expect(nav.log).toEqual([
      ["tab", "nav-main", "home"],
      ["view", "home"],
    ]);
  });
});
