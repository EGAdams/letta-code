import { describe, expect, test } from "bun:test";
import {
  renderWorkerActivity,
  workerTabClass,
} from "../abstract/worker-activity-render.js";

const worker = {
  status: "active",
  reason: "polling",
  service: { active: "active" },
};

describe("Worker Activity rendering", () => {
  test("keeps the SVG and makes missing task data visibly unavailable", () => {
    const html = renderWorkerActivity({
      tasks_available: false,
      tasks_error: "No task ledger is configured.",
      worker,
    });
    expect(html).toContain("<svg");
    expect(html).toContain("Task activity unavailable");
    expect(html).toContain("No task ledger is configured.");
    expect(html).toContain("not inferred");
    expect(workerTabClass({ tasks_available: false })).toBe("server-concern");
  });

  test("a failed request still draws the SVG with the reason", () => {
    const html = renderWorkerActivity({
      ok: false,
      tasks_available: false,
      fetch_error: "HTTP 502",
      tasks_error: "Worker telemetry request failed: HTTP 502",
    });
    expect(html).toContain("<svg");
    expect(html).toContain("HTTP 502");
    expect(workerTabClass({ ok: false })).toBe("poll-disabled");
  });

  test("renders task fields and warns on zero-attempt queued work", () => {
    const html = renderWorkerActivity({
      tasks_available: true,
      worker,
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
    expect(html).toContain('id="worker-activity-arrow"');
  });

  test("surfaces failure details from the ledger", () => {
    const html = renderWorkerActivity({
      tasks_available: true,
      worker,
      tasks: [
        {
          id: "t-9",
          agent: "codex-writer",
          operation: "implement",
          workspace: "letta_code",
          status: "failed",
          attempts: 1,
          error: "codex exited 1: stream disconnected",
        },
        { id: "t-8", agent: "codex", status: "succeeded", attempts: 1 },
      ],
    });
    expect(html).toContain("Recent failures");
    expect(html).toContain("codex exited 1: stream disconnected");
    expect(html).toMatch(/Failed <strong>1<\/strong>/);
    expect(html).toMatch(/Completed <strong>1<\/strong>/);
    expect(workerTabClass({ ok: true, tasks_available: true })).toBe(
      "server-up",
    );
  });
});
