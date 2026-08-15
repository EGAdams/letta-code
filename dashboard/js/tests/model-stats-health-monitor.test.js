import { describe, expect, test } from "bun:test";
import { ModelStatsHealthMonitor } from "../implementation/model-stats-health-monitor.js";
import { FakeDocument } from "./_fake-dom.js";

function setup(statuses) {
  const doc = new FakeDocument();
  const nav = doc.createElement("nav");
  nav.id = "nav-model-stats";
  for (const source of Object.keys(statuses)) {
    const tab = doc.createElement("button");
    tab.dataset.source = source;
    nav.appendChild(tab);
  }
  const modelStats = doc.createElement("button");
  modelStats.id = "btn-model-stats";
  const systemStatus = doc.createElement("button");
  systemStatus.id = "btn-system-status";
  const http = {
    getJSON: async (url) => ({
      status:
        statuses[new URL(url, "http://dashboard").searchParams.get("source")],
    }),
  };
  return {
    doc,
    nav,
    modelStats,
    systemStatus,
    monitor: new ModelStatsHealthMonitor({ http, doc, setInterval: null }),
  };
}

describe("ModelStatsHealthMonitor", () => {
  test("a red OAuth source blinks its source and both parent tabs red", async () => {
    const ctx = setup({ "r46-claude": "up", "w11-claude": "down" });
    await ctx.monitor.poll();

    const source = ctx.nav.querySelector('[data-source="w11-claude"]');
    expect(source.classList.contains("server-down")).toBe(true);
    expect(source.classList.contains("tab-alert-red")).toBe(true);
    expect(ctx.modelStats.classList.contains("tab-alert-red")).toBe(true);
    expect(ctx.systemStatus.classList.contains("tab-alert-red")).toBe(true);
  });

  test("clears the inherited red blink after all sources recover", async () => {
    const statuses = { "w11-claude": "down" };
    const ctx = setup(statuses);
    await ctx.monitor.poll();
    statuses["w11-claude"] = "up";
    await ctx.monitor.poll();

    expect(ctx.modelStats.classList.contains("tab-alert-red")).toBe(false);
    expect(ctx.systemStatus.classList.contains("tab-alert-red")).toBe(false);
    expect(ctx.modelStats.classList.contains("server-up")).toBe(true);
    expect(ctx.systemStatus.classList.contains("server-up")).toBe(true);
  });

  test("a concern rolls up as a yellow blink", async () => {
    const ctx = setup({ "w11-claude": "concern" });
    await ctx.monitor.poll();

    expect(ctx.modelStats.classList.contains("tab-alert")).toBe(true);
    expect(ctx.systemStatus.classList.contains("tab-alert")).toBe(true);
  });
});
