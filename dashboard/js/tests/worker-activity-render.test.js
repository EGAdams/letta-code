import { describe, expect, test } from "bun:test";
import {
  renderWorkerActivity,
  workerTabClass,
} from "../abstract/worker-activity-render.js";

describe("Worker Activity rendering", () => {
  test("makes missing task data visibly unavailable", () => {
    const html = renderWorkerActivity({
      tasks_available: false,
      tasks_error: "No task ledger is configured.",
      worker: {
        status: "active",
        reason: "polling",
        service: { active: "active" },
      },
    });
    expect(html).toContain("Task activity unavailable");
    expect(html).toContain("No task ledger is configured.");
    expect(html).toContain("not inferred");
    expect(workerTabClass({ tasks_available: false })).toBe("server-concern");
  });

  test("renders task fields and warns on zero-attempt queued work", () => {
    const html = renderWorkerActivity({
      tasks_available: true,
      worker: {
        status: "active",
        reason: "polling",
        service: { active: "active" },
      },
      tasks: [
        {
          id: "t-1",
          agent: "Codex",
          operation: "build",
          workspace: "/tmp/ws",
          status: "queued",
          attempts: 0,
          error: "",
        },
      ],
    });
    expect(html).toContain("t-1");
    expect(html).toContain("zero attempts may be stagnant");
    expect(html).toContain("Queue age");
  });
});
