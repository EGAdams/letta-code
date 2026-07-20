import { describe, expect, test } from "bun:test";
import { VendorReviewController } from "../implementation/vendor-review-controller.js";

// Fake HttpClient that records calls and returns scripted results per URL.
const fakeHttp = (responses) => {
  const calls = [];
  return {
    calls,
    getJSON: async (url) => {
      calls.push({ method: "GET", url });
      const r = responses[url];
      if (r instanceof Error) throw r;
      return r;
    },
    postJSON: async (url, body) => {
      calls.push({ method: "POST", url, body });
      const r = responses[url];
      if (r instanceof Error) throw r;
      return r;
    },
  };
};

// Recording VendorReviewView double.
const fakeView = () => {
  const events = [];
  return {
    events,
    renderPending: (rows) => events.push({ type: "pending", rows }),
    renderError: (m) => events.push({ type: "error", message: m }),
  };
};

describe("VendorReviewController (Command)", () => {
  test("validates injected ports", () => {
    expect(() => new VendorReviewController({})).toThrow(/http/);
    expect(
      () => new VendorReviewController({ http: { getJSON() {} } }),
    ).toThrow(/view/);
  });

  test("refresh() fetches pending rows and renders them", async () => {
    const rows = [
      { expense_id: 1, expense_date: "2026-05-10", amount: "40.77" },
    ];
    const http = fakeHttp({ "/api/pending-vendor-review": { ok: true, rows } });
    const view = fakeView();
    const c = new VendorReviewController({ http, view });

    const result = await c.refresh();

    expect(result).toEqual(rows);
    expect(view.events).toEqual([{ type: "pending", rows }]);
  });

  test("refresh() renders an error on transport failure", async () => {
    const http = fakeHttp({
      "/api/pending-vendor-review": new Error("HTTP 502"),
    });
    const view = fakeView();
    const c = new VendorReviewController({ http, view });

    const result = await c.refresh();

    expect(result).toEqual([]);
    expect(view.events).toEqual([{ type: "error", message: "HTTP 502" }]);
  });

  test("refresh() treats a not-ok response as an empty list", async () => {
    const http = fakeHttp({
      "/api/pending-vendor-review": { ok: false, error: "DB error" },
    });
    const view = fakeView();
    const c = new VendorReviewController({ http, view });

    const result = await c.refresh();

    expect(result).toEqual([]);
    expect(view.events).toEqual([{ type: "pending", rows: [] }]);
  });

  test("listVendorKeys() fetches once and caches the result", async () => {
    const vendorKeys = [{ vendor_key: "costco", category_id: 130 }];
    const http = fakeHttp({
      "/api/vendor-keys": { ok: true, vendor_keys: vendorKeys },
    });
    const view = fakeView();
    const c = new VendorReviewController({ http, view });

    const first = await c.listVendorKeys();
    const second = await c.listVendorKeys();

    expect(first).toEqual(vendorKeys);
    expect(second).toEqual(vendorKeys);
    expect(http.calls.length).toBe(1); // cached on the second call
  });

  test("pickVendor() posts the pick then refreshes on success", async () => {
    const http = fakeHttp({
      "/api/set-receipt-vendor": { ok: true, expense_id: 1, category_id: 130 },
      "/api/pending-vendor-review": { ok: true, rows: [] },
    });
    const view = fakeView();
    const c = new VendorReviewController({ http, view });

    const result = await c.pickVendor(1, "costco");

    expect(result).toEqual({ ok: true, expense_id: 1, category_id: 130 });
    expect(http.calls).toEqual([
      {
        method: "POST",
        url: "/api/set-receipt-vendor",
        body: { expense_id: 1, vendor_key: "costco" },
      },
      { method: "GET", url: "/api/pending-vendor-review" },
    ]);
    expect(view.events).toEqual([{ type: "pending", rows: [] }]);
  });

  test("pickVendor() does not refresh when the pick fails", async () => {
    const http = fakeHttp({
      "/api/set-receipt-vendor": { ok: false, error: "Unknown vendor_key: x" },
    });
    const view = fakeView();
    const c = new VendorReviewController({ http, view });

    const result = await c.pickVendor(1, "x");

    expect(result).toEqual({ ok: false, error: "Unknown vendor_key: x" });
    expect(http.calls.length).toBe(1);
    expect(view.events).toEqual([]);
  });
});
