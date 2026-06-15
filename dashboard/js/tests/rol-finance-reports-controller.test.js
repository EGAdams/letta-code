import { describe, expect, test } from "bun:test";
import { RolFinanceReportsController } from "../implementation/rol-finance-reports-controller.js";
import { FakeDocument } from "./_fake-dom.js";

function setup(payload) {
  const doc = new FakeDocument();
  const nav = doc.createElement("div");
  const viewsContainer = doc.createElement("div");
  const activated = [];
  const selected = [];
  const http = {
    getJSON: async () => {
      if (payload instanceof Error) throw payload;
      return payload;
    },
  };
  const rf = new RolFinanceReportsController({
    http,
    nav,
    viewsContainer,
    doc,
    activateView: (id) => activated.push(id),
    setActiveTab: (tab) => selected.push(tab),
  });
  return { rf, nav, viewsContainer, activated, selected, doc };
}

describe("RolFinanceReportsController", () => {
  test("requires http, nav and viewsContainer", () => {
    expect(() => new RolFinanceReportsController({})).toThrow();
  });

  test("openReports builds a tab + view per report and opens the first", async () => {
    const ctx = setup([
      { key: "jan", label: "January", exists: true, url: "/r/jan.html" },
      { key: "feb", label: "February", exists: false, url: "/r/feb.html" },
    ]);
    await ctx.rf.openReports();

    const tabs = ctx.nav.querySelectorAll("[data-report-key]");
    expect(tabs.length).toBe(2);
    expect(tabs[0].textContent).toBe("January");
    expect(tabs[0].className).toBe("tab");
    // Missing report → red tab + placeholder view.
    expect(tabs[1].className).toBe("tab report-missing");

    const views = ctx.viewsContainer.querySelectorAll("section");
    expect(views.length).toBe(2);
    expect(views[0].id).toBe("rol-finance-report-jan");
    expect(views[0].innerHTML).toContain("/r/jan.html");
    expect(views[1].innerHTML).toContain("Missing report.html");

    // First report selected + activated.
    expect(ctx.selected.length).toBe(1);
    expect(ctx.activated).toEqual(["rol-finance-report-jan"]);
  });

  test("openReports caches the list (no rebuild on second call)", async () => {
    const ctx = setup([
      { key: "jan", label: "January", exists: true, url: "/r/jan.html" },
    ]);
    await ctx.rf.openReports();
    await ctx.rf.openReports();
    expect(ctx.nav.querySelectorAll("[data-report-key]").length).toBe(1);
  });

  test("a fetch failure shows an error section", async () => {
    const ctx = setup(new Error("nope"));
    await ctx.rf.openReports();
    expect(ctx.viewsContainer.innerHTML).toContain("Failed to load reports");
    expect(ctx.viewsContainer.innerHTML).toContain("nope");
  });

  test("openReport activates the matching view", () => {
    const ctx = setup([]);
    ctx.rf.openReport("march");
    expect(ctx.activated).toEqual(["rol-finance-report-march"]);
  });
});
