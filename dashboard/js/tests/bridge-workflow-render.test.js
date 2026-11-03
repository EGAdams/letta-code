import { describe, expect, test } from "bun:test";
import {
  coarseStage,
  normalizeWorkers,
  renderBridgeWorkflow,
  renderWorkerLegend,
} from "../abstract/bridge-workflow-render.js";

describe("bridge workflow telemetry mapping", () => {
  test("assigns stable requested colors and maps coarse states", () => {
    const workers = normalizeWorkers({
      tasks_available: true,
      tasks: [
        { id: "a", worker_id: "worker1", status: "queued" },
        { id: "b", worker_id: "worker2", status: "running" },
        { id: "c", worker_id: "worker3", status: "succeeded" },
      ],
    });
    expect(workers.map((worker) => worker.className)).toEqual([
      "worker-yellow",
      "worker-white",
      "worker-orange",
    ]);
    expect(coarseStage("queued")).toBe(2);
    expect(coarseStage("running")).toBe(3);
    expect(coarseStage("succeeded")).toBe(4);
  });

  test("keeps simultaneous workers independent in the SVG and legend", () => {
    const payload = {
      tasks_available: true,
      tasks: [
        { id: "a", worker_id: "worker1", status: "running" },
        { id: "b", worker_id: "worker2", status: "running" },
      ],
    };
    const html = renderBridgeWorkflow(payload);
    expect(html.match(/class="bridge-worker-marker worker-/g)?.length).toBe(2);
    expect(renderWorkerLegend(payload)).toContain("task a");
    expect(renderWorkerLegend(payload)).toContain("task b");
  });

  test("does not imply activity when the real task ledger is absent or empty", () => {
    expect(
      renderBridgeWorkflow({
        tasks_available: false,
        tasks_error: "not configured",
      }),
    ).toContain("Telemetry unavailable");
    expect(
      renderBridgeWorkflow({ tasks_available: true, tasks: [] }),
    ).toContain("0 workers observed");
    expect(renderWorkerLegend({ tasks_available: false })).toContain(
      "no worker activity inferred",
    );
  });
});
