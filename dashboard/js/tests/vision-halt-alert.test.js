import { describe, expect, test } from "bun:test";
import { VisionHaltAlert } from "../implementation/vision-halt-alert.js";
import { FakeDocument } from "./_fake-dom.js";

function setup(serverHealth) {
  const doc = new FakeDocument();
  const mkBtn = (id) => {
    const el = doc.createElement("button");
    el.id = id;
    return el;
  };
  const modal = mkBtn("vision-halted-modal");
  modal.classList.add("hidden");
  const detail = mkBtn("vision-halted-detail");
  const retry = mkBtn("vision-halted-retry");
  const dismiss = mkBtn("vision-halted-dismiss");

  const windowTab = doc.createElement("button");
  windowTab.dataset.target = "scanners-window";
  doc.add(windowTab);
  const freezerTab = doc.createElement("button");
  freezerTab.dataset.target = "scanners-freezer";
  doc.add(freezerTab);

  const calls = [];
  const http = {
    getJSON: async (url) => {
      calls.push(url);
      if (serverHealth instanceof Error) throw serverHealth;
      return typeof serverHealth === "function" ? serverHealth() : serverHealth;
    },
  };
  const alert = new VisionHaltAlert({ http, doc, setInterval: () => 1 });
  return {
    alert,
    doc,
    modal,
    detail,
    retry,
    dismiss,
    windowTab,
    freezerTab,
    calls,
  };
}

const DOWN_HEALTH = {
  servers: [
    {
      key: "document-vision",
      name: "Document Vision (Scan Classify)",
      status: "down",
    },
  ],
};
const UP_HEALTH = {
  servers: [
    {
      key: "document-vision",
      name: "Document Vision (Scan Classify)",
      status: "up",
    },
  ],
};

describe("VisionHaltAlert", () => {
  test("requires an HttpClient", () => {
    expect(() => new VisionHaltAlert({})).toThrow();
  });

  test("shows the modal and reddens both scanner tabs when down", async () => {
    const ctx = setup(DOWN_HEALTH);
    ctx.alert.start();
    await ctx.alert.poll();
    expect(ctx.modal.classList.contains("hidden")).toBe(false);
    expect(ctx.windowTab.classList.contains("server-down")).toBe(true);
    expect(ctx.freezerTab.classList.contains("server-down")).toBe(true);
    expect(ctx.detail.textContent).toContain("Document Vision");
  });

  test("stays hidden and tabs stay clean when up", async () => {
    const ctx = setup(UP_HEALTH);
    ctx.alert.start();
    await ctx.alert.poll();
    expect(ctx.modal.classList.contains("hidden")).toBe(true);
    expect(ctx.windowTab.classList.contains("server-down")).toBe(false);
  });

  test("Dismiss hides the modal but leaves tabs red until it actually recovers", async () => {
    const ctx = setup(DOWN_HEALTH);
    ctx.alert.start();
    await ctx.alert.poll();
    ctx.dismiss.click();
    expect(ctx.modal.classList.contains("hidden")).toBe(true);
    expect(ctx.windowTab.classList.contains("server-down")).toBe(true);
    // still down on next poll -> stays dismissed, doesn't re-pop
    await ctx.alert.poll();
    expect(ctx.modal.classList.contains("hidden")).toBe(true);
  });

  test("recovering clears the dismissal and the red tabs", async () => {
    let down = true;
    const ctx = setup(() => (down ? DOWN_HEALTH : UP_HEALTH));
    ctx.alert.start();
    await ctx.alert.poll();
    ctx.dismiss.click();
    down = false;
    await ctx.alert.poll();
    expect(ctx.windowTab.classList.contains("server-down")).toBe(false);
    expect(ctx.modal.classList.contains("hidden")).toBe(true);
    // now go down again -> should re-show since dismissal was cleared
    down = true;
    await ctx.alert.poll();
    expect(ctx.modal.classList.contains("hidden")).toBe(false);
  });

  test("Retry Now forces an immediate poll", async () => {
    const ctx = setup(UP_HEALTH);
    ctx.alert.start();
    const before = ctx.calls.length;
    ctx.retry.click();
    await Promise.resolve();
    expect(ctx.calls.length).toBeGreaterThan(before);
  });

  test("a fetch failure is swallowed", async () => {
    const ctx = setup(new Error("boom"));
    ctx.alert.start();
    await expect(ctx.alert.poll()).resolves.toBeUndefined();
  });

  test("missing document-vision entry is treated as not-down", async () => {
    const ctx = setup({ servers: [] });
    ctx.alert.start();
    await ctx.alert.poll();
    expect(ctx.modal.classList.contains("hidden")).toBe(true);
  });
});
