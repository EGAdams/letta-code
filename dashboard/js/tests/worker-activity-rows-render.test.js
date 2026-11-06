import { describe, expect, test } from "bun:test";
import {
  latestEventForTask,
  renderWorkerActivityRows,
} from "../abstract/worker-activity-rows-render.js";

const ledger = (tasks, extra = {}) => ({
  tasks_available: true,
  tasks,
  ...extra,
});

describe("Worker Activity five-row view", () => {
  test("renders exactly five rows, one per real task, in priority order", () => {
    const html = renderWorkerActivityRows(
      ledger([
        {
          id: "ok-1",
          status: "succeeded",
          agent: "codex",
          last_update: "2026-11-05T01:00:00Z",
        },
        {
          id: "fail-1",
          status: "failed",
          agent: "adw",
          last_update: "2026-11-05T02:00:00Z",
        },
      ]),
    );
    const rowIndexes = [...html.matchAll(/data-worker-row-index="(\d)"/g)].map(
      (m) => Number(m[1]),
    );
    expect(rowIndexes).toEqual([0, 1, 2, 3, 4]);
    const taskIds = [
      ...html.matchAll(/data-worker-row-task-id="([^"]*)"/g),
    ].map((m) => m[1]);
    expect(taskIds).toEqual(["fail-1", "ok-1"]);
    expect(html).toContain("No further active or recent job to display.");
  });

  test("binds each row to its own real task id and status, never duplicating one task", () => {
    const html = renderWorkerActivityRows(
      ledger([
        { id: "a", status: "running", agent: "codex" },
        { id: "b", status: "running", agent: "adw" },
        { id: "a", status: "running", agent: "codex-duplicate-row" },
      ]),
    );
    expect([...html.matchAll(/data-worker-row-task-id="a"/g)]).toHaveLength(1);
    expect(html).not.toContain("codex-duplicate-row");
  });

  test("gives each row a distinguishable status indicator matching its real status group", () => {
    const html = renderWorkerActivityRows(
      ledger([
        { id: "f", status: "failed" },
        { id: "r", status: "running" },
        { id: "q", status: "queued", attempts: 2 },
        { id: "c", status: "succeeded" },
      ]),
    );
    expect(html).toContain('worker-activity-row is-failed"');
    expect(html).toContain('worker-activity-row is-running"');
    expect(html).toContain('worker-activity-row is-queued"');
    expect(html).toContain('worker-activity-row is-completed"');
    expect(html).toContain("worker-activity-row-status is-failed");
    expect(html).toContain("worker-activity-row-status is-running");
  });

  test("marks only rows whose task really transitioned, never a fabricated row", () => {
    const payload = ledger([
      { id: "t1", status: "running" },
      { id: "t2", status: "queued", attempts: 1 },
    ]);
    expect(renderWorkerActivityRows(payload)).not.toContain("is-changed");

    const changed = renderWorkerActivityRows(payload, {
      changedIds: new Set(["t1"]),
    });
    expect(changed).toContain(
      'class="worker-activity-row is-running is-changed" data-worker-row-index="0" data-worker-row-task-id="t1"',
    );
    expect(changed).toContain(
      'class="worker-activity-row is-queued" data-worker-row-index="1" data-worker-row-task-id="t2"',
    );
  });

  test("shows an explicit unavailable banner, with the real four-station rows still present, when there is no ledger", () => {
    const html = renderWorkerActivityRows({
      tasks_available: false,
      tasks_error: "The configured worker task ledger is not present.",
    });
    expect(html).toContain("Top active jobs unavailable");
    expect(html).toContain("The configured worker task ledger is not present.");
    expect(html).toContain("<svg");
    expect(html.match(/data-worker-row-index/g)?.length).toBe(5);
    expect(html).not.toContain('data-worker-row-task-id="'); // no real task bound in any slot
  });

  test("keeps the original first-row id so existing consumers of the id stay valid", () => {
    const html = renderWorkerActivityRows(
      ledger([{ id: "t1", status: "running" }]),
    );
    expect(html).toContain('id="worker-activity-arrow"');
  });

  test("latestEventForTask reports the real latest event, or an explicit absence", () => {
    const task = {
      id: "t1",
      status: "running",
      started_at: "2026-11-05T09:00:00Z",
      events: [{ timestamp: "2026-11-05T09:05:00Z", message: "ran build" }],
    };
    const event = latestEventForTask(task, []);
    expect(event.message).toBe("ran build");
    expect(latestEventForTask({ id: "t2", status: "queued" }, [])).toBeNull();
    expect(latestEventForTask(null, [])).toBeNull();
  });

  test("reflects a latest-event absence explicitly in the row text", () => {
    const html = renderWorkerActivityRows(
      ledger([{ id: "t1", status: "running" }]),
    );
    expect(html).toContain("No event detail reported for this task.");
  });
});
