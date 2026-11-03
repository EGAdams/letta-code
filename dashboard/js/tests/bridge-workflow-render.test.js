import { describe, expect, test } from "bun:test";
import {
  coarseStage,
  normalizeWorkers,
  renderBridgeWorkflow,
  renderWorkerLegend,
  statusGroup,
  summarizeTasks,
} from "../abstract/bridge-workflow-render.js";

const ledger = (tasks) => ({ tasks_available: true, tasks });

describe("bridge workflow telemetry mapping", () => {
  test("assigns stable requested colors and maps coarse states", () => {
    const workers = normalizeWorkers(
      ledger([
        { id: "a", worker_id: "worker1", status: "queued" },
        { id: "b", worker_id: "worker2", status: "running" },
        { id: "c", worker_id: "worker3", status: "succeeded" },
      ]),
    );
    expect(workers.map((worker) => worker.className)).toEqual([
      "worker-yellow",
      "worker-white",
      "worker-orange",
    ]);
    expect(coarseStage("queued")).toBe(2);
    expect(coarseStage("running")).toBe(3);
    expect(coarseStage("succeeded")).toBe(4);
    expect(coarseStage("failed")).toBe(4);
    expect(coarseStage("mystery")).toBe(0);
    expect(statusGroup("timed_out")).toBe("failed");
  });

  test("one entry per agent; current task is open work first, else the newest", () => {
    const workers = normalizeWorkers(
      ledger([
        {
          id: "old",
          agent: "codex",
          status: "succeeded",
          last_update: "2026-11-03T09:00:00-05:00",
        },
        {
          id: "new",
          agent: "codex",
          status: "failed",
          last_update: "2026-11-03T10:00:00-05:00",
        },
        {
          id: "w1",
          agent: "codex-writer",
          status: "succeeded",
          last_update: "2026-11-03T08:00:00-05:00",
        },
        {
          id: "w2",
          agent: "codex-writer",
          status: "running",
          last_update: "2026-11-03T07:00:00-05:00",
        },
      ]),
    );
    expect(workers.map((w) => [w.name, w.taskIds[0], w.group])).toEqual([
      ["codex", "new", "failed"],
      ["codex-writer", "w2", "running"],
    ]);
    expect(workers[0].counts).toMatchObject({
      completed: 1,
      failed: 1,
      total: 2,
    });
  });

  test("counts every ledger status group", () => {
    expect(
      summarizeTasks(
        ledger([
          { status: "queued" },
          { status: "running" },
          { status: "succeeded" },
          { status: "failed" },
          { status: "failed" },
        ]),
      ),
    ).toMatchObject({
      queued: 1,
      running: 1,
      completed: 1,
      failed: 2,
      total: 5,
    });
  });

  test("keeps simultaneous workers independent in the SVG and legend", () => {
    const payload = ledger([
      { id: "a", worker_id: "worker1", status: "running" },
      { id: "b", worker_id: "worker2", status: "running" },
    ]);
    const html = renderBridgeWorkflow(payload);
    expect(html.match(/class="bridge-worker-marker worker-/g)?.length).toBe(2);
    expect(html).toContain("is-processing");
    expect(html).toContain("bridge-loop is-active");
    expect(renderWorkerLegend(payload)).toContain("task a");
    expect(renderWorkerLegend(payload)).toContain("task b");
  });

  test("markers sit inside the box for their stage", () => {
    const html = renderBridgeWorkflow(
      ledger([
        { id: "q", agent: "x", status: "queued" },
        { id: "f", agent: "y", status: "failed" },
      ]),
    );
    const cx = [...html.matchAll(/<circle[^>]*cx="(\d+)"/g)].map((m) =>
      Number(m[1]),
    );
    expect(cx[0]).toBeGreaterThan(240); // box 2: 240..420
    expect(cx[0]).toBeLessThan(420);
    expect(cx[1]).toBeGreaterThan(680); // box 4: 680..860
    expect(html).toContain("is-failed");
  });

  test("ids are prefixed so two pages can render it at once", () => {
    const a = renderBridgeWorkflow(ledger([]), { idPrefix: "abp" });
    const b = renderBridgeWorkflow(ledger([]), { idPrefix: "worker-activity" });
    expect(a).toContain('id="abp-arrow"');
    expect(a).toContain("url(#abp-arrow)");
    expect(b).toContain('id="worker-activity-arrow"');
    expect(b).not.toContain('id="abp-arrow"');
  });

  test("does not imply activity when the real task ledger is absent or empty", () => {
    const html = renderBridgeWorkflow({
      tasks_available: false,
      tasks_error: "not configured",
      worker: { status: "active" },
    });
    expect(html).toContain("<svg");
    expect(html).toContain("Telemetry unavailable");
    expect(html).toContain("not configured");
    expect(html).not.toContain("bridge-worker-marker");
    expect(renderBridgeWorkflow(ledger([]))).toContain("0 workers observed");
    expect(renderWorkerLegend({ tasks_available: false })).toContain(
      "no worker activity inferred",
    );
  });
});
