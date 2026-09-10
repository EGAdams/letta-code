import { describe, expect, test } from "bun:test";

import { openScannerReportTab } from "../boot/bindings/scanner-report-tab.js";
import { FakeDocument } from "./_fake-dom.js";

const settle = async () => {
  await Promise.resolve();
  await Promise.resolve();
};

describe("Last Scan tab composition", () => {
  test("opens the terminal with the completed scan's conversation", async () => {
    const doc = new FakeDocument();
    const section = doc.add(doc.createElement("section"));
    section.id = "scanners-last-window";
    const iframe = doc.createElement("iframe");
    const thoughts = doc.add(doc.createElement("div"));
    thoughts.id = "scanners-last-window-mazda-detail";
    const terminal = doc.add(doc.createElement("div"));
    terminal.id = "scanners-last-window-mazda-terminal";
    const archive = doc.add(doc.createElement("div"));
    archive.id = "scanners-last-window-archive-verification";
    section.append(iframe, thoughts, terminal, archive);
    const tab = doc.createElement("button");
    tab.dataset.scannerReport = "window";
    tab.dataset.target = "scanners-last-window";
    const calls = [];
    const AM = {
      renderMazdaThoughtsInto: (...args) => calls.push(["thoughts", ...args]),
      showMazdaTerminalForScanner: (...args) =>
        calls.push(["terminal", ...args]),
      showArchiveVerificationForScanner: (...args) =>
        calls.push(["archive", ...args]),
      clearScannerCompletionViews: (...args) => calls.push(["clear", ...args]),
    };
    const cleared = [];

    openScannerReportTab({
      doc,
      tab,
      AM,
      RF: { loadScannerReportInto: () => {} },
      http: {
        getJSON: async () => ({
          ok: true,
          status: "pass",
          conversation_id: "conv-window-123",
          dispatched_at: 100,
        }),
      },
      setIntervalFn: () => 41,
      clearIntervalFn: (id) => cleared.push(id),
    });
    await settle();

    expect(calls).toContainEqual([
      "terminal",
      "#scanners-last-window-mazda-terminal",
      "conv-window-123",
    ]);
    expect(calls.some(([kind]) => kind === "archive")).toBe(true);
    expect(cleared).toEqual([41]);
  });

  test("a new scan clears the old terminal and rearms completion polling", async () => {
    const doc = new FakeDocument();
    const section = doc.add(doc.createElement("section"));
    section.id = "scanners-last-freezer";
    const iframe = doc.createElement("iframe");
    const terminal = doc.add(doc.createElement("div"));
    terminal.id = "scanners-last-freezer-mazda-terminal";
    const archive = doc.add(doc.createElement("div"));
    archive.id = "scanners-last-freezer-archive-verification";
    section.append(iframe, terminal, archive);
    const tab = doc.createElement("button");
    tab.dataset.scannerReport = "freezer";
    tab.dataset.target = "scanners-last-freezer";

    const calls = [];
    let statusRequest = 0;
    let intervalId = 0;
    const intervals = [];
    const clearedIntervals = [];
    const controller = openScannerReportTab({
      doc,
      tab,
      AM: {
        renderMazdaThoughtsInto: () => {},
        showMazdaTerminalForScanner: (...args) =>
          calls.push(["terminal", ...args]),
        showArchiveVerificationForScanner: (...args) =>
          calls.push(["archive", ...args]),
        clearScannerCompletionViews: (...args) =>
          calls.push(["clear", ...args]),
      },
      RF: { loadScannerReportInto: () => calls.push(["report"]) },
      http: {
        getJSON: async () => {
          statusRequest += 1;
          if (statusRequest <= 2) {
            return {
              ok: true,
              status: "pass",
              conversation_id: "conv-freezer-old",
              dispatched_at: 100,
            };
          }
          return {
            ok: true,
            status: "pass",
            conversation_id: "conv-freezer-new",
            dispatched_at: 200,
          };
        },
      },
      scannerFetch: async () => ({
        json: async () => ({ ok: true, status: "ready" }),
      }),
      setIntervalFn: (callback) => {
        intervalId += 1;
        intervals.push([intervalId, callback]);
        return intervalId;
      },
      clearIntervalFn: (id) => clearedIntervals.push(id),
    });
    await settle();

    expect(calls).toContainEqual([
      "terminal",
      "#scanners-last-freezer-mazda-terminal",
      "conv-freezer-old",
    ]);
    await controller.controls.runScan();
    await settle();

    expect(calls).toContainEqual([
      "clear",
      "#scanners-last-freezer-mazda-terminal",
      "#scanners-last-freezer-archive-verification",
    ]);
    expect(intervals).toHaveLength(2);
    expect(clearedIntervals).toEqual([1]);
    expect(statusRequest).toBe(2);

    // The immediate status still described the prior run, so it neither
    // reopened the old terminal nor stopped the newly armed interval.
    expect(calls.filter(([kind]) => kind === "terminal")).toHaveLength(1);
    await intervals[1][1]();
    await settle();

    expect(calls).toContainEqual([
      "terminal",
      "#scanners-last-freezer-mazda-terminal",
      "conv-freezer-new",
    ]);
    expect(clearedIntervals).toEqual([1, 2]);
    expect(statusRequest).toBe(3);
  });
});
