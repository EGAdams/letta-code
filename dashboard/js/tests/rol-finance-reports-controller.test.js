import { describe, expect, test } from "bun:test";
import { RolFinanceReportsController } from "../implementation/rol-finance-reports-controller.js";
import { FakeDocument } from "./_fake-dom.js";

function setup(payload, opts = {}) {
  const doc = new FakeDocument();
  const nav = doc.createElement("div");
  const viewsContainer = doc.createElement("div");
  const activated = [];
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
    ...opts,
  });
  return { rf, nav, viewsContainer, activated, doc };
}

const REPORTS = [
  { key: "jan", label: "January", exists: true, url: "/r/jan.html" },
  { key: "feb", label: "February", exists: false, url: "/r/feb.html" },
];

describe("RolFinanceReportsController", () => {
  test("requires http, nav and viewsContainer", () => {
    expect(() => new RolFinanceReportsController({})).toThrow();
  });

  test("openReports injects month tabs and opens the first month", async () => {
    const ctx = setup(REPORTS);
    await ctx.rf.openReports();

    // Two month tabs, January active by default.
    const months = ctx.nav.querySelectorAll("[data-month-key]");
    expect(months.map((m) => m.textContent)).toEqual([
      "January 2025",
      "February 2025",
    ]);
    expect(months[0].classList.contains("active")).toBe(true);
    expect(months[1].classList.contains("active")).toBe(false);

    // January is available → existing report normal, missing report red.
    const tabs = ctx.nav.querySelectorAll("[data-report-key]");
    expect(tabs.length).toBe(2);
    expect(tabs[0].className).toContain("tab");
    expect(tabs[0].className).not.toContain("report-missing");
    expect(tabs[1].className).toContain("report-missing");

    const views = ctx.viewsContainer.querySelectorAll("section");
    expect(views[0].innerHTML).toContain("/r/jan.html");
    expect(views[1].innerHTML).toContain("Missing report.html");

    // First report selected + activated.
    expect(tabs[0].classList.contains("active")).toBe(true);
    expect(ctx.activated).toEqual(["rol-finance-report-jan"]);
  });

  test("an unavailable month forces every document red + a not-found view", async () => {
    const ctx = setup(REPORTS);
    await ctx.rf.openReports();
    ctx.rf.openMonth("feb-2025");

    // February tab active, January no longer active.
    const months = ctx.nav.querySelectorAll("[data-month-key]");
    expect(months[0].classList.contains("active")).toBe(false);
    expect(months[1].classList.contains("active")).toBe(true);

    // Same document list, but every tab is red...
    const tabs = ctx.nav.querySelectorAll("[data-report-key]");
    expect(tabs.length).toBe(2);
    for (const t of tabs) expect(t.className).toContain("report-missing");

    // ...and every view says no report.html was found.
    const views = ctx.viewsContainer.querySelectorAll("section");
    expect(views.length).toBe(2);
    for (const v of views)
      expect(v.innerHTML).toContain("No report.html file found.");
    expect(views[0].innerHTML).not.toContain("iframe");
  });

  test("switching months rebuilds document tabs without duplicating them", async () => {
    const ctx = setup(REPORTS);
    await ctx.rf.openReports();
    ctx.rf.openMonth("feb-2025");
    ctx.rf.openMonth("jan-2025");

    // Month tabs are injected once; document tabs are rebuilt, not stacked.
    expect(ctx.nav.querySelectorAll("[data-month-key]").length).toBe(2);
    expect(ctx.nav.querySelectorAll("[data-report-key]").length).toBe(2);
    expect(ctx.viewsContainer.querySelectorAll("section").length).toBe(2);
  });

  test("openReports caches the list (no extra month tabs on second call)", async () => {
    const ctx = setup([REPORTS[0]]);
    await ctx.rf.openReports();
    await ctx.rf.openReports();
    expect(ctx.nav.querySelectorAll("[data-month-key]").length).toBe(2);
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
