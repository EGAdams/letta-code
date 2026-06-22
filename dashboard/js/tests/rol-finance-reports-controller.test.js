import { describe, expect, test } from "bun:test";
import { RolFinanceReportsController } from "../implementation/rol-finance-reports-controller.js";
import { FakeDocument } from "./_fake-dom.js";

function setup(payloadOrFn) {
  const doc = new FakeDocument();
  const nav = doc.createElement("div");
  const viewsContainer = doc.createElement("div");
  const activated = [];
  const selected = [];
  const requestedUrls = [];
  const http = {
    getJSON: async (url) => {
      requestedUrls.push(url);
      const payload =
        typeof payloadOrFn === "function" ? payloadOrFn(url) : payloadOrFn;
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
  return { rf, nav, viewsContainer, activated, selected, requestedUrls, doc };
}

describe("RolFinanceReportsController", () => {
  test("requires http, nav and viewsContainer", () => {
    expect(() => new RolFinanceReportsController({})).toThrow();
  });

  test("openReports builds a tab + view per report and lands on the overview (not a document)", async () => {
    const ctx = setup([
      {
        key: "jan",
        label: "January",
        exists: true,
        status: "pass",
        url: "/r/jan.html",
      },
      {
        key: "feb",
        label: "February",
        exists: false,
        status: "missing",
        url: "/r/feb.html",
      },
    ]);
    await ctx.rf.openReports();

    const tabs = ctx.nav.querySelectorAll("[data-report-key]");
    expect(tabs.length).toBe(2);
    expect(tabs[0].textContent).toBe("January");
    expect(tabs[0].className).toBe("tab");
    // Missing report → red tab + placeholder view.
    expect(tabs[1].className).toBe("tab report-missing");

    const views = ctx.viewsContainer.querySelectorAll("section");
    // overview + 2 document views.
    expect(views.length).toBe(3);
    const docViews = views.filter(
      (v) => v.id !== "rol-finance-reports-overview",
    );
    expect(docViews[0].id).toBe("rol-finance-report-jan");
    expect(docViews[0].innerHTML).toContain("/r/jan.html");
    expect(docViews[1].innerHTML).toContain("Missing report.html");

    // No document tab selected — the month overview is shown instead.
    expect(ctx.selected.length).toBe(0);
    expect(ctx.activated).toEqual(["rol-finance-reports-overview"]);

    // Default month (jan-2025) requested.
    expect(ctx.requestedUrls).toEqual([
      "/api/rol-finance-reports?month=jan-2025",
    ]);
  });

  test("overview shows a color-coded row per document, skipping reports with no status", async () => {
    const ctx = setup([
      {
        key: "jan",
        label: "January",
        exists: true,
        status: "pass",
        url: "/r/jan.html",
      },
      {
        key: "wip",
        label: "Work In Progress",
        exists: true,
        status: "review",
        url: "/r/wip.html",
      },
      {
        key: "broken",
        label: "Broken",
        exists: true,
        status: "fail",
        url: "/r/broken.html",
      },
      {
        key: "feb",
        label: "February",
        exists: false,
        status: "missing",
        url: "/r/feb.html",
      },
      {
        key: "receipt-only",
        label: "Receipt Only",
        exists: true,
        status: null,
        url: "/r/receipt.html",
      },
    ]);
    await ctx.rf.openReports();

    const overview = ctx.viewsContainer
      .querySelectorAll("section")
      .find((v) => v.id === "rol-finance-reports-overview");
    expect(overview.innerHTML).toContain('class="rol-status-pass"');
    expect(overview.innerHTML).toContain('class="rol-status-review"');
    // Both the explicit "fail" and "missing" statuses render as the fail row class.
    expect(
      [...overview.innerHTML.matchAll(/class="rol-status-fail"/g)].length,
    ).toBe(2);
    expect(overview.innerHTML).toContain("January");
    expect(overview.innerHTML).toContain("Finished");
    expect(overview.innerHTML).toContain("In progress");
    expect(overview.innerHTML).toContain("Failed");
    expect(overview.innerHTML).toContain("Not started");
    // Receipt Only isn't a verification target — not listed in the overview.
    expect(overview.innerHTML).not.toContain("Receipt Only");
  });

  test("openReports caches the list (no rebuild / refetch on second call)", async () => {
    const ctx = setup([
      {
        key: "jan",
        label: "January",
        exists: true,
        status: "pass",
        url: "/r/jan.html",
      },
    ]);
    await ctx.rf.openReports();
    await ctx.rf.openReports();
    expect(ctx.nav.querySelectorAll("[data-report-key]").length).toBe(1);
    expect(ctx.requestedUrls.length).toBe(1);
  });

  test("openMonth fetches and caches per month, independent existence per document", async () => {
    const ctx = setup((url) =>
      url.includes("feb-2025")
        ? [
            {
              key: "platinum-year",
              label: "Platinum Year",
              exists: true,
              status: "pass",
              url: "/r/feb-platinum.html",
            },
          ]
        : [
            {
              key: "platinum-year",
              label: "Platinum Year",
              exists: true,
              status: "pass",
              url: "/r/jan-platinum.html",
            },
          ],
    );
    await ctx.rf.openReports(); // opens jan-2025 by default
    await ctx.rf.openMonth("feb-2025");

    expect(ctx.requestedUrls).toEqual([
      "/api/rol-finance-reports?month=jan-2025",
      "/api/rol-finance-reports?month=feb-2025",
    ]);
    expect(
      ctx.viewsContainer.querySelector("#rol-finance-report-platinum-year")
        .innerHTML,
    ).toContain("/r/feb-platinum.html");

    // Re-selecting January doesn't refetch.
    await ctx.rf.openMonth("jan-2025");
    expect(ctx.requestedUrls.length).toBe(2);
    expect(
      ctx.viewsContainer.querySelector("#rol-finance-report-platinum-year")
        .innerHTML,
    ).toContain("/r/jan-platinum.html");
  });

  test("selecting a report from the overview/tab highlights its tab and opens its view", async () => {
    const ctx = setup([
      {
        key: "jan",
        label: "January",
        exists: true,
        status: "pass",
        url: "/r/jan.html",
      },
    ]);
    await ctx.rf.openReports();
    ctx.activated.length = 0;
    ctx.selected.length = 0;

    ctx.rf.selectReport("jan");
    expect(ctx.activated).toEqual(["rol-finance-report-jan"]);
    expect(
      ctx.nav
        .querySelector('[data-report-key="jan"]')
        .classList.contains("active"),
    ).toBe(true);
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
