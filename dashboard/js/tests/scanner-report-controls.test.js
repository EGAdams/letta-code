import { describe, expect, test } from "bun:test";

import { mountScannerReportControls } from "../boot/scanners/scanner-report-controls.js";
import { FakeDocument } from "./_fake-dom.js";

function setup({
  result = { ok: true, status: "ready" },
  scanner = "freezer",
} = {}) {
  const doc = new FakeDocument();
  const section = doc.createElement("section");
  const iframe = doc.createElement("iframe");
  section.appendChild(iframe);
  const calls = [];
  const progressCalls = [];
  let reloads = 0;

  const controller = mountScannerReportControls({
    doc,
    section,
    iframe,
    scanner,
    fetchImpl: async (...args) => {
      calls.push(args);
      return { json: async () => result };
    },
    onScanReady: () => {
      reloads += 1;
    },
    progressFactory: () => ({
      setProbing: (message) => progressCalls.push(["probing", message]),
      runProgress: (...args) => progressCalls.push(["progress", ...args]),
      setComplete: () => progressCalls.push(["complete"]),
      setBusy: (message) => progressCalls.push(["busy", message]),
      setFailed: (message) => progressCalls.push(["failed", message]),
    }),
  });

  return {
    controller,
    section,
    iframe,
    calls,
    progressCalls,
    reloads: () => reloads,
  };
}

describe("Last Scan report controls", () => {
  test("mounts a Windows-style Start Scan panel before the report", () => {
    const ctx = setup();
    expect(ctx.section.children[0]).toBe(ctx.controller.element);
    expect(ctx.section.children[1]).toBe(ctx.iframe);
    expect(
      ctx.controller.element.classList.contains("scanner-report-controls"),
    ).toBe(true);
    expect(
      ctx.controller.element.querySelector(".scanner-report-start").textContent,
    ).toBe("Start Scan");
    expect(ctx.controller.element.querySelector(".scanner-bar")).not.toBeNull();
  });

  test("starts the correct scanner and refreshes its report on success", async () => {
    const ctx = setup();

    await ctx.controller.runScan();

    expect(ctx.calls).toHaveLength(1);
    expect(ctx.calls[0][0]).toBe("/api/scanner-scan");
    expect(JSON.parse(ctx.calls[0][1].body)).toEqual({ scanner: "freezer" });
    expect(ctx.progressCalls).toEqual([
      ["probing", "Scanning…"],
      ["progress", 4, 88, 30_000],
      ["complete"],
    ]);
    expect(ctx.reloads()).toBe(1);
    expect(
      ctx.controller.element.querySelector(".scanner-report-start").disabled,
    ).toBe(false);
  });

  test("uses the Window Scanner's faster progress timing", async () => {
    const ctx = setup({ scanner: "window" });

    await ctx.controller.runScan();

    expect(JSON.parse(ctx.calls[0][1].body)).toEqual({ scanner: "window" });
    expect(ctx.progressCalls[1]).toEqual(["progress", 4, 96, 23_000]);
  });

  test("shows a failed scan without stranding the Start Scan button", async () => {
    const ctx = setup({
      result: { ok: false, status: "offline", error: "not reachable" },
    });

    await ctx.controller.runScan();

    expect(ctx.progressCalls.at(-1)).toEqual([
      "busy",
      "Restart the Scanner Please",
    ]);
    expect(ctx.reloads()).toBe(0);
    expect(
      ctx.controller.element.querySelector(".scanner-report-start").disabled,
    ).toBe(false);
  });

  test("does not mount a duplicate panel when the tab is reopened", () => {
    const ctx = setup();
    const second = mountScannerReportControls({
      doc: ctx.controller.element._doc,
      section: ctx.section,
      iframe: ctx.iframe,
      scanner: "freezer",
    });

    expect(second.element).toBe(ctx.controller.element);
    expect(
      ctx.section.querySelectorAll(".scanner-report-controls"),
    ).toHaveLength(1);
  });
});
