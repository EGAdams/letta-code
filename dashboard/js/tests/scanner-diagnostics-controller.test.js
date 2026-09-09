import { afterEach, describe, expect, test } from "bun:test";
import { createScannerStatusMonitor } from "../boot/scanners/scanner-status-monitor.js";
import { ScannerDiagnosticsController } from "../implementation/scanner-diagnostics-controller.js";

// Minimal esc double — good enough to prove escaping happens without a DOM.
const esc = (s) =>
  String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

const fakeHttp = (result) => {
  const calls = [];
  return {
    calls,
    getJSON: async (url, opts) => {
      calls.push({ url, opts });
      if (result instanceof Error) throw result;
      return result;
    },
  };
};

// Tiny stand-in for a DOM element (only what the controller touches).
const fakeEl = () => {
  const classes = new Set();
  return {
    innerHTML: "",
    classList: {
      add: (c) => classes.add(c),
      remove: (c) => classes.delete(c),
      has: (c) => classes.has(c),
    },
  };
};

describe("ScannerDiagnosticsController", () => {
  test("requires an http client and an escaper", () => {
    expect(() => new ScannerDiagnosticsController()).toThrow(/requires/);
    expect(() => new ScannerDiagnosticsController({ http: {}, esc })).toThrow(
      /requires/,
    );
    expect(
      () =>
        new ScannerDiagnosticsController({
          http: { getJSON: () => {} },
          scanner: "window",
        }),
    ).toThrow(/requires/);
  });

  test("maps every state onto its LED class", () => {
    const c = ScannerDiagnosticsController;
    expect(c.stateClass("ok")).toBe("diag-ok");
    expect(c.stateClass("warn")).toBe("diag-warn");
    expect(c.stateClass("bad")).toBe("diag-bad");
    expect(c.stateClass("unknown")).toBe("diag-unknown");
    expect(c.stateClass(undefined)).toBe("diag-unknown");
  });

  test("rowHtml escapes label and detail", () => {
    const html = ScannerDiagnosticsController.rowHtml(
      { state: "bad", label: "A<b>", detail: "x & y" },
      esc,
    );
    expect(html).toContain("diag-bad");
    expect(html).toContain("A&lt;b&gt;");
    expect(html).toContain("x &amp; y");
  });

  test("renders one row per check", () => {
    const el = fakeEl();
    const ctrl = new ScannerDiagnosticsController({
      http: fakeHttp({}),
      scanner: "freezer",
      esc,
    });
    ctrl.render(el, {
      checks: [
        { id: "bridge", label: "WSL Bridge", state: "ok", detail: "fine" },
        { id: "online", label: "Scanner Online", state: "bad", detail: "off" },
      ],
    });
    expect((el.innerHTML.match(/scanner-diag-row/g) || []).length).toBe(2);
    expect(el.innerHTML).toContain("diag-ok");
    expect(el.innerHTML).toContain("diag-bad");
  });

  test("render surfaces a server error payload as a red row", () => {
    const el = fakeEl();
    const ctrl = new ScannerDiagnosticsController({
      http: fakeHttp({}),
      scanner: "window",
      esc,
    });
    ctrl.render(el, { error: "Unknown scanner: nope" });
    expect(el.innerHTML).toContain("diag-bad");
    expect(el.innerHTML).toContain("Unknown scanner");
  });

  test("refresh fetches the scanner's endpoint with a long timeout", async () => {
    const http = fakeHttp({
      checks: [{ id: "bridge", state: "ok", label: "x", detail: "y" }],
    });
    const ctrl = new ScannerDiagnosticsController({
      http,
      scanner: "freezer",
      esc,
    });
    const el = fakeEl();
    await ctrl.refresh(el);
    expect(http.calls[0].url).toBe("/api/scanner-diagnostics?scanner=freezer");
    expect(http.calls[0].opts.timeout).toBeGreaterThan(30000);
    expect(el.innerHTML).toContain("diag-ok");
  });

  test("refresh shows a grey row when the endpoint is unreachable", async () => {
    const ctrl = new ScannerDiagnosticsController({
      http: fakeHttp(new Error("boom")),
      scanner: "window",
      esc,
    });
    const el = fakeEl();
    await ctrl.refresh(el);
    expect(el.innerHTML).toContain("diag-unknown");
    expect(el.innerHTML).toContain("boom");
  });
});

describe("scanner status recovery monitor", () => {
  const originalFetch = globalThis.fetch;
  const originalSetTimeout = globalThis.setTimeout;
  const originalClearTimeout = globalThis.clearTimeout;
  const flush = () => new Promise((resolve) => originalSetTimeout(resolve, 0));
  const progress = {
    setProbing() {},
    runProgress() {},
    stopProgress() {},
    setBusy() {},
  };

  afterEach(() => {
    globalThis.fetch = originalFetch;
    globalThis.setTimeout = originalSetTimeout;
    globalThis.clearTimeout = originalClearTimeout;
  });

  test("URL-encodes the scanner key and uses read-only GET", async () => {
    const requests = [];
    globalThis.fetch = async (...args) => {
      requests.push(args);
      return { json: async () => ({ status: "idle", ok: true }) };
    };
    const monitor = createScannerStatusMonitor({
      scanner: "window & freezer",
      enabled: true,
      progress,
      applyResult: (data) => data.status,
    });

    monitor.start();
    await flush();

    expect(requests).toEqual([
      ["/api/scanner-status?scanner=window%20%26%20freezer"],
    ]);
  });

  test("preserves intake_busy polling and stops on idle", async () => {
    const statuses = ["intake_busy", "idle"];
    const scheduled = [];
    const applied = [];
    globalThis.fetch = async () => ({
      json: async () => ({ status: statuses.shift(), ok: false }),
    });
    globalThis.setTimeout = (callback) => {
      scheduled.push(callback);
      return scheduled.length;
    };
    globalThis.clearTimeout = () => {};
    const monitor = createScannerStatusMonitor({
      scanner: "window",
      enabled: true,
      progress,
      applyResult: (data) => {
        applied.push(data.status);
        return data.status;
      },
    });

    monitor.start();
    await flush();
    expect(applied).toEqual(["intake_busy"]);
    expect(scheduled).toHaveLength(1);

    scheduled.shift()();
    await flush();
    expect(applied).toEqual(["intake_busy", "idle"]);
    expect(scheduled).toHaveLength(0);
  });
});
