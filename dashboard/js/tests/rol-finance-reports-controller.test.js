import { describe, expect, test } from "bun:test";
import { RolFinanceReportsController } from "../implementation/rol-finance-reports-controller.js";
import { FakeDocument } from "./_fake-dom.js";

function setup(payloadOrFn, { postPayload } = {}) {
  const doc = new FakeDocument();
  const nav = doc.createElement("div");
  // Wrap the views container so the recently-scanned panel has a real parent to
  // be inserted before (mirrors the live dashboard where #rol-finance-reports-
  // views sits inside a wrapper).
  const viewsParent = doc.createElement("div");
  const viewsContainer = doc.createElement("div");
  viewsParent.appendChild(viewsContainer);
  const activated = [];
  const selected = [];
  const requestedUrls = [];
  const postedRequests = [];
  const http = {
    getJSON: async (url) => {
      requestedUrls.push(url);
      const payload =
        typeof payloadOrFn === "function"
          ? payloadOrFn(url, { method: "GET" })
          : payloadOrFn;
      if (payload instanceof Error) throw payload;
      return payload;
    },
    postJSON: async (url, body) => {
      postedRequests.push({ url, body });
      // Router-based POST payload (New Records "set category" tests branch on
      // opts.method); falls back to the postPayload option (reprocess tests).
      const routed =
        typeof payloadOrFn === "function"
          ? payloadOrFn(url, { method: "POST", body })
          : undefined;
      if (routed instanceof Error) throw routed;
      if (routed !== undefined) return routed;
      if (postPayload instanceof Error) throw postPayload;
      return postPayload ?? { ok: true, stages: [] };
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
  return {
    rf,
    nav,
    viewsContainer,
    viewsParent,
    activated,
    selected,
    requestedUrls,
    postedRequests,
    doc,
  };
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

  // ── Reprocess Document button ─────────────────────────────────────────────

  test("existing report view has a reprocess bar; missing report view does not", async () => {
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
        url: null,
      },
    ]);
    await ctx.rf.openReports();

    const janView = ctx.viewsContainer.querySelector("#rol-finance-report-jan");
    expect(janView.querySelector(".reprocess-bar")).not.toBeNull();
    expect(janView.querySelector(".reprocess-btn")).not.toBeNull();
    expect(janView.querySelector(".reprocess-status")).not.toBeNull();

    const febView = ctx.viewsContainer.querySelector("#rol-finance-report-feb");
    expect(febView.querySelector(".reprocess-bar")).toBeNull();
  });

  test("clicking Reprocess Document POSTs to the reprocess endpoint with the report URL", async () => {
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

    const btn = ctx.viewsContainer.querySelector(".reprocess-btn");
    btn.click();
    // postJSON is async; let the microtask queue drain
    await Promise.resolve();

    expect(ctx.postedRequests).toEqual([
      { url: "/api/reprocess-report", body: { report_url: "/r/jan.html" } },
    ]);
  });

  test("successful reprocess renders stage summary in the status span", async () => {
    const pipelineResult = {
      ok: true,
      stages: [
        {
          name: "classify",
          status: "done",
          doc_kind: "receipt",
          confidence: 0.95,
        },
        {
          name: "parse",
          status: "done",
          parsed: { merchant_name: "Goodwill" },
        },
        { name: "investigate", status: "delegated" },
        { name: "categorize", status: "delegated" },
        { name: "store", status: "delegated" },
      ],
    };
    const ctx = setup(
      [
        {
          key: "jan",
          label: "January",
          exists: true,
          status: "pass",
          url: "/r/jan.html",
        },
      ],
      { postPayload: pipelineResult },
    );
    await ctx.rf.openReports();

    const btn = ctx.viewsContainer.querySelector(".reprocess-btn");
    const statusEl = ctx.viewsContainer.querySelector(".reprocess-status");
    btn.click();
    await Promise.resolve();
    await Promise.resolve(); // second tick for async/await inside reprocessDocument

    expect(statusEl.textContent).toContain("classify");
    expect(statusEl.textContent).toContain("done");
    expect(statusEl.textContent).toContain("delegated");
  });

  test("failed reprocess renders the error message in the status span", async () => {
    const ctx = setup(
      [
        {
          key: "jan",
          label: "January",
          exists: true,
          status: "pass",
          url: "/r/jan.html",
        },
      ],
      { postPayload: new Error("source doc not found") },
    );
    await ctx.rf.openReports();

    const btn = ctx.viewsContainer.querySelector(".reprocess-btn");
    const statusEl = ctx.viewsContainer.querySelector(".reprocess-status");
    btn.click();
    await Promise.resolve();
    await Promise.resolve();

    expect(statusEl.textContent).toContain("source doc not found");
  });

  // ── Polling ───────────────────────────────────────────────────────────────

  test("startPolling is a no-op when setInterval is not injected", async () => {
    // Default constructor has no setInterval — calling startPolling must not throw
    const ctx = setup([]);
    expect(() => ctx.rf.startPolling()).not.toThrow();
    expect(ctx.rf._pollTimer).toBeNull();
  });

  // ── New Records ──────────────────────────────────────────────────────────

  test("buildOverview injects the New Records placeholder before Document Status", async () => {
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

    const overview = ctx.viewsContainer.querySelector(
      "#rol-finance-reports-overview",
    );
    expect(overview.children[0].id).toBe("rol-finance-recent-reports");
    expect(overview.innerHTML).toContain("Document Status");
  });

  test("renderRecentReportsHtml shows the latest report even when it's not in items, capped at 5 rows", () => {
    const ctx = setup([]);
    const latest = {
      key: "jan",
      label: "January",
      month_key: "jan-2025",
      status: "pass",
      needs_attention: false,
      url: "/r/jan.html",
    };
    const items = Array.from({ length: 5 }, (_, i) => ({
      key: `r${i}`,
      label: `Report ${i}`,
      month_key: "feb-2025",
      status: "review",
      needs_attention: true,
      url: `/r/${i}.html`,
    }));
    const html = ctx.rf.renderRecentReportsHtml({ latest, items });

    expect(html).toContain("New Records");
    expect(html).toContain("/r/jan.html");
    expect((html.match(/<tr/g) || []).length).toBe(5);
    // Latest (pass) bumped one item out of the queue to stay at 5 total.
    expect(html).not.toContain("/r/4.html");
  });

  test("renderRecentReportsHtml dedupes the latest report against items", () => {
    const ctx = setup([]);
    const shared = {
      key: "jan",
      label: "January",
      month_key: "jan-2025",
      status: "review",
      needs_attention: true,
      url: "/r/jan.html",
    };
    const html = ctx.rf.renderRecentReportsHtml({
      latest: shared,
      items: [shared],
    });
    expect((html.match(/<tr/g) || []).length).toBe(1);
  });

  test("renderRecentReportsHtml marks needs-attention rows and reports empty state", () => {
    const ctx = setup([]);
    const needsAttention = ctx.rf.renderRecentReportsHtml({
      latest: null,
      items: [
        {
          key: "r1",
          label: "Report 1",
          month_key: "jan-2025",
          status: "fail",
          needs_attention: true,
          url: "/r/1.html",
        },
      ],
    });
    expect(needsAttention).toContain("rol-recent-needs-attention");

    const empty = ctx.rf.renderRecentReportsHtml({ latest: null, items: [] });
    expect(empty).toContain("No records processed yet.");
  });

  test("refreshRecentReports fetches and fills the placeholder", async () => {
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
    ctx.requestedUrls.length = 0;

    await ctx.rf.refreshRecentReports();

    expect(ctx.requestedUrls).toEqual(["/api/rol-finance-recent-reports"]);
    const container = ctx.viewsContainer.querySelector(
      "#rol-finance-recent-reports",
    );
    expect(container.innerHTML).toContain("No records processed yet.");
  });

  test("refreshRecentReports renders a failure message on fetch error without throwing", async () => {
    const doc = new FakeDocument();
    const nav = doc.createElement("div");
    const viewsContainer = doc.createElement("div");
    let call = 0;
    const http = {
      getJSON: async () => {
        call += 1;
        if (call === 1) return [];
        throw new Error("boom");
      },
    };
    const rf = new RolFinanceReportsController({
      http,
      nav,
      viewsContainer,
      doc,
    });
    await rf.openReports();

    await rf.refreshRecentReports();

    const container = viewsContainer.querySelector(
      "#rol-finance-recent-reports",
    );
    expect(container.innerHTML).toContain("Failed to load New Records");
    expect(container.innerHTML).toContain("boom");
  });

  test("refreshRecentReports is a no-op when the placeholder isn't in the DOM", async () => {
    const ctx = setup([]);
    await expect(ctx.rf.refreshRecentReports()).resolves.toBeUndefined();
  });

  test("startPolling / stopPolling use injected timer functions", () => {
    const timers = [];
    const _setInterval = (fn, ms) => {
      timers.push({ fn, ms });
      return timers.length;
    };
    const cleared = [];
    const _clearInterval = (id) => cleared.push(id);

    const doc = new FakeDocument();
    const rf = new RolFinanceReportsController({
      http: { getJSON: async () => [], postJSON: async () => ({}) },
      nav: doc.createElement("div"),
      viewsContainer: doc.createElement("div"),
      doc,
      setInterval: _setInterval,
      clearInterval: _clearInterval,
    });

    rf.startPolling();
    expect(timers.length).toBe(1);
    expect(timers[0].ms).toBe(15_000);

    // Idempotent: second call does not start another timer.
    rf.startPolling();
    expect(timers.length).toBe(1);

    rf.stopPolling();
    expect(cleared).toEqual([1]);
    expect(rf._pollTimer).toBeNull();
  });

  test("refreshStatus colors month tabs green (done) / yellow (work to do)", async () => {
    const ctx = setup((url) => {
      if (url.startsWith("/api/rol-finance-month-status")) {
        return {
          months: [
            { month_key: "jan-2025", status: "green", uncategorized_count: 0 },
            { month_key: "feb-2025", status: "yellow", uncategorized_count: 3 },
          ],
        };
      }
      if (url.startsWith("/api/rol-finance-recent-scans")) {
        return { rows: [], queue_total: 0, limit: 5 };
      }
      return []; // report list
    });
    await ctx.rf.openReports();
    await ctx.rf.refreshStatus();

    const jan = ctx.nav.querySelector('[data-month-key="jan-2025"]');
    const feb = ctx.nav.querySelector('[data-month-key="feb-2025"]');
    expect(jan.classList.contains("status-green")).toBe(true);
    expect(jan.classList.contains("status-yellow")).toBe(false);
    expect(feb.classList.contains("status-yellow")).toBe(true);
    expect(feb.title).toContain("3");
  });

  test("refreshStatus renders the recently-scanned viewing area (≤5, newest first)", async () => {
    let rows = [
      {
        id: 42,
        vendor_key: "meijer",
        expense_date: "2025-01-22",
        amount: "18.40",
      },
      {
        id: 41,
        vendor_key: "circle_k",
        expense_date: "2025-01-21",
        amount: "5.00",
      },
    ];
    const ctx = setup((url) => {
      if (url.startsWith("/api/rol-finance-recent-scans")) {
        return { rows, queue_total: rows.length, limit: 5 };
      }
      if (url.startsWith("/api/rol-finance-month-status"))
        return { months: [] };
      return [];
    });
    await ctx.rf.openReports();
    await ctx.rf.refreshStatus();

    const panel = ctx.doc.getElementById("rol-finance-recent-scans");
    expect(panel).not.toBe(null);
    expect(panel.innerHTML).toContain("New Records");
    expect(panel.innerHTML).toContain("meijer");
    expect(panel.innerHTML).toContain("2 waiting");

    // Categorizing one elsewhere → it drops out; the panel backfills on refresh
    // and reuses the same panel element (no duplicate).
    rows = [
      {
        id: 41,
        vendor_key: "circle_k",
        expense_date: "2025-01-21",
        amount: "5.00",
      },
    ];
    await ctx.rf.refreshStatus();
    const panels = ctx.doc.querySelectorAll("#rol-finance-recent-scans");
    expect(panels.length).toBe(1);
    expect(panels[0].innerHTML).not.toContain("meijer");
    expect(panels[0].innerHTML).toContain("circle_k");
  });

  test("refreshStatus keeps prior state when an endpoint fails", async () => {
    const ctx = setup((url) => {
      if (url.startsWith("/api/rol-finance-month-status"))
        throw new Error("db down");
      if (url.startsWith("/api/rol-finance-recent-scans"))
        throw new Error("db down");
      return [];
    });
    await ctx.rf.openReports();
    // Must not throw even though both status endpoints fail.
    await ctx.rf.refreshStatus();
    const jan = ctx.nav.querySelector('[data-month-key="jan-2025"]');
    expect(jan.classList.contains("status-green")).toBe(false);
    expect(jan.classList.contains("status-yellow")).toBe(false);
  });

  test("month-status keeps prior colors on a 200+error payload (fail soft)", async () => {
    let payload = {
      months: [
        { month_key: "jan-2025", status: "yellow", uncategorized_count: 2 },
        { month_key: "feb-2025", status: "green" },
      ],
    };
    const ctx = setup((url) => {
      if (url.startsWith("/api/rol-finance-month-status")) return payload;
      if (url.startsWith("/api/rol-finance-recent-scans"))
        return { rows: [], queue_total: 0 };
      return [];
    });
    await ctx.rf.openReports();
    await ctx.rf.refreshStatus();
    const jan = ctx.nav.querySelector('[data-month-key="jan-2025"]');
    expect(jan.classList.contains("status-yellow")).toBe(true);

    // DB hiccup: endpoint returns HTTP 200 with {error}. Colors must persist.
    payload = { months: [], error: "db down" };
    await ctx.rf.refreshStatus();
    expect(jan.classList.contains("status-yellow")).toBe(true);
  });

  test("recent-scans keeps prior cards on a 200+error payload (no false all-clear)", async () => {
    let payload = {
      rows: [
        {
          id: 42,
          vendor_key: "meijer",
          expense_date: "2025-01-22",
          amount: "18.40",
        },
      ],
      queue_total: 1,
    };
    const ctx = setup((url) => {
      if (url.startsWith("/api/rol-finance-recent-scans")) return payload;
      if (url.startsWith("/api/rol-finance-month-status"))
        return { months: [] };
      return [];
    });
    await ctx.rf.openReports();
    await ctx.rf.refreshStatus();
    const panel = ctx.doc.getElementById("rol-finance-recent-scans");
    expect(panel.innerHTML).toContain("meijer");

    payload = { rows: [], error: "db down" };
    await ctx.rf.refreshStatus();
    expect(panel.innerHTML).toContain("meijer");
    expect(panel.innerHTML).not.toContain("Nothing waiting");
  });

  test("clicking a New Records card opens the Set Category dialog with reason + categories", async () => {
    const ctx = setup((url) => {
      if (url.startsWith("/api/rol-finance-categories")) {
        return {
          categories: [
            {
              name: "Travel & Vehicle",
              cls: "cat-travel-and-vehicle",
              bg: "#F4B683",
              fg: "#000000",
            },
            {
              name: "Uncategorized",
              cls: "cat-uncategorized",
              bg: "#BFBFBF",
              fg: "#000000",
            },
          ],
        };
      }
      return [];
    });
    const card = ctx.doc.createElement("div");
    card.className = "rol-recent-card cat-uncategorized";
    card.dataset = {
      expenseId: "42",
      vendorKey: "meijer",
      description: "MEIJER",
      signedAmount: "18.40",
      date: "2025-01-22",
      reason: "Categorization incomplete — no reporting category was assigned.",
      receiptPresent: "1",
    };
    await ctx.rf._openPicker(card);

    const dialog = ctx.doc.getElementById("rol-newrec-picker");
    expect(dialog).not.toBe(null);
    expect(dialog.classList.contains("open")).toBe(true);
    expect(dialog.querySelector(".cp-target").textContent).toContain("MEIJER");
    expect(dialog.querySelector(".cp-reason").textContent).toContain(
      "Categorization incomplete",
    );
    const squares = dialog.querySelectorAll(".cp-square");
    expect(squares.length).toBe(2);
    // The uncategorized square is marked as the current selection.
    expect(squares[1].classList.contains("current")).toBe(true);
  });

  test("picking a category posts a DB-only recategorize, closes, and backfills", async () => {
    let recentRows = [
      {
        id: 42,
        vendor_key: "meijer",
        expense_date: "2025-01-22",
        amount: "18.40",
        description: "MEIJER",
      },
    ];
    const ctx = setup((url, opts) => {
      if (
        opts.method === "POST" &&
        url.startsWith("/api/recategorize-expense")
      ) {
        recentRows = []; // categorized → drops out of New Records
        return { ok: true };
      }
      if (url.startsWith("/api/rol-finance-categories")) {
        return {
          categories: [
            {
              name: "Travel & Vehicle",
              cls: "cat-travel-and-vehicle",
              bg: "#F4B683",
              fg: "#000000",
            },
          ],
        };
      }
      if (url.startsWith("/api/rol-finance-recent-scans"))
        return { rows: recentRows, queue_total: recentRows.length };
      if (url.startsWith("/api/rol-finance-month-status"))
        return { months: [] };
      return [];
    });
    const card = ctx.doc.createElement("div");
    card.className = "rol-recent-card cat-uncategorized";
    card.dataset = {
      expenseId: "42",
      vendorKey: "meijer",
      description: "MEIJER",
      signedAmount: "18.40",
      date: "2025-01-22",
      reason: "x",
      receiptPresent: "0",
    };
    await ctx.rf._openPicker(card);
    await ctx.rf._pickCategory("Travel & Vehicle");

    const post = ctx.postedRequests.find((p) =>
      p.url.startsWith("/api/recategorize-expense"),
    );
    expect(post).not.toBe(undefined);
    expect(post.body.reporting_category).toBe("Travel & Vehicle");
    // DB-only: no report_path (these records have no static report.html row).
    expect("report_path" in post.body).toBe(false);

    const dialog = ctx.doc.getElementById("rol-newrec-picker");
    expect(dialog.classList.contains("open")).toBe(false);
    const panel = ctx.doc.getElementById("rol-finance-recent-scans");
    expect(panel.innerHTML).toContain("Nothing waiting");
  });
});
