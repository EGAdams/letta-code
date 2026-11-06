import { describe, expect, test } from "bun:test";
import {
  renderWorkerActivity,
  renderWorkerTerminal,
  renderWorkerTerminalContent,
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
    expect(html).toMatch(/Succeeded <strong>1<\/strong>/);
    expect(workerTabClass({ ok: true, tasks_available: true })).toBe(
      "server-up",
    );
  });

  test("renders producer events and identifies dashboard observations", () => {
    const html = renderWorkerActivity({
      tasks_available: true,
      tasks: [
        {
          id: "t-2",
          agent: "adw",
          operation: "intake",
          status: "running",
          last_update: "2026-11-04T12:00:00Z",
          events: [
            { timestamp: "2026-11-04T11:59:00Z", message: "validated input" },
          ],
        },
      ],
      activity_events: [
        {
          time: "2026-11-04T12:00:01Z",
          taskId: "t-2",
          agent: "adw",
          message: "Dashboard observed task status: running",
          source: "dashboard",
        },
      ],
    });
    expect(html).toContain("validated input (worker event)");
    expect(html).toContain(
      "Dashboard observed task status: running (dashboard observation)",
    );
    expect(html).toContain("Task t-2 · adw · intake · running");
  });

  test("renders only worker-supplied lifecycle phases and says when detail is unavailable", () => {
    const html = renderWorkerActivity({
      tasks_available: true,
      tasks: [
        {
          id: "t-3",
          agent: "adw",
          operation: "ship",
          status: "running",
          queued_at: "2026-11-04T12:00:00Z",
          started_at: "2026-11-04T12:00:02Z",
        },
      ],
    });
    expect(html).toContain("queued status update (worker event)");
    expect(html).toContain("started status update (worker event)");
    expect(html).toContain("Detailed step logs are unavailable");
    expect(html).toContain(
      "internal thoughts and model activity are not exposed",
    );
  });

  test("states when the feed has no detailed events", () => {
    const html = renderWorkerActivity({
      tasks_available: true,
      tasks: [{ id: "t-4", status: "succeeded" }],
    });
    expect(html).toContain("Detailed step logs are unavailable");
  });

  test("terminal content is pre-ready even when the two unavailable-note paragraphs precede it", () => {
    // This is the exact shape that broke the old splice-by-regex live update:
    // two <p> tags between <h3> and <pre> (the am-dim note plus the
    // "unavailable" note) because the task has no events/progress_events.
    const payload = {
      tasks_available: true,
      tasks: [{ id: "t-5", agent: "codex", status: "running" }],
    };
    const section = renderWorkerTerminal(payload);
    const content = renderWorkerTerminalContent(payload);
    expect(section).toContain("<p");
    expect(section.match(/<p(?:\s[^>]*)?>/g)?.length).toBe(2);
    expect(section).toContain(
      `<pre class="worker-activity-terminal" role="log" aria-live="polite">${content}</pre>`,
    );
    expect(content).not.toContain("<section");
    expect(content).not.toContain("<pre");
  });

  test("terminal content never contains the section/pre wrapper, with or without explicit events", () => {
    const withEvents = {
      tasks_available: true,
      tasks: [
        {
          id: "t-6",
          agent: "adw",
          status: "running",
          events: [{ timestamp: "t", message: "ran tool" }],
        },
      ],
    };
    const unavailable = { tasks_available: false, tasks_error: "no ledger" };
    for (const payload of [withEvents, unavailable]) {
      const content = renderWorkerTerminalContent(payload);
      expect(content).not.toContain("<section");
      expect(content).not.toContain("<pre");
      expect(content).not.toContain("</section>");
    }
    expect(renderWorkerTerminalContent(withEvents)).toContain("ran tool");
  });
});
