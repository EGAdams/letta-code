import { beforeEach, describe, expect, test } from "bun:test";
import { DomNavigationController } from "../implementation/dom-navigation-controller.js";
import { FakeDocument } from "./_fake-dom.js";

function setup() {
  const doc = new FakeDocument();

  const mkPanel = (id) => {
    const p = doc.createElement("nav");
    p.id = id;
    return p;
  };
  const mkView = (id) => {
    const v = doc.createElement("section");
    v.id = id;
    v.classList.add("view");
    return v;
  };
  const mkTab = (panel, target) => {
    const t = doc.createElement("button");
    t.classList.add("tab");
    t.dataset.target = target;
    panel.appendChild(t);
    return t;
  };

  const navMain = mkPanel("nav-main");
  const navAgents = mkPanel("nav-agents");
  navAgents.classList.add("hidden");
  mkView("home");
  mkView("agents-home");
  const homeTab = mkTab(navMain, "home");
  const agentsHomeTab = mkTab(navAgents, "agents-home");

  const nav = new DomNavigationController(
    {
      agents: { panel: "nav-agents", view: "agents-home", tab: "agents-home" },
    },
    { doc },
  );
  return { doc, nav, navMain, navAgents, homeTab, agentsHomeTab };
}

describe("DomNavigationController (concrete NavigationController)", () => {
  let ctx;
  beforeEach(() => {
    ctx = setup();
  });

  test("enterSection swaps panels and activates the default view/tab", () => {
    expect(ctx.nav.enterSection("agents")).toBe(true);
    expect(ctx.navMain.classList.contains("hidden")).toBe(true);
    expect(ctx.navAgents.classList.contains("hidden")).toBe(false);
    expect(
      ctx.doc.getElementById("agents-home").classList.contains("active"),
    ).toBe(true);
    expect(ctx.doc.getElementById("home").classList.contains("active")).toBe(
      false,
    );
    expect(ctx.agentsHomeTab.classList.contains("active")).toBe(true);
  });

  test("activateView clears active from sibling views", () => {
    ctx.doc.getElementById("home").classList.add("active");
    ctx.nav.activateView("agents-home");
    expect(ctx.doc.getElementById("home").classList.contains("active")).toBe(
      false,
    );
    expect(
      ctx.doc.getElementById("agents-home").classList.contains("active"),
    ).toBe(true);
  });

  test("back returns to main + home", () => {
    ctx.nav.enterSection("agents");
    ctx.nav.back();
    expect(ctx.navAgents.classList.contains("hidden")).toBe(true);
    expect(ctx.navMain.classList.contains("hidden")).toBe(false);
    expect(ctx.doc.getElementById("home").classList.contains("active")).toBe(
      true,
    );
    expect(ctx.homeTab.classList.contains("active")).toBe(true);
  });

  test("unknown section is a no-op returning false", () => {
    expect(ctx.nav.enterSection("nope")).toBe(false);
  });
});
