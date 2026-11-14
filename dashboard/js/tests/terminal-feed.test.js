import { describe, expect, test } from "bun:test";
import {
  buildTerminalEvents,
  formatTerminalTimestamp,
} from "../abstract/terminal-feed.js";

describe("formatTerminalTimestamp", () => {
  test("formats fractional ISO milliseconds in the browser's local 12-hour time", () => {
    const value = "2026-11-10T17:17:05.123Z";
    const expected = new Intl.DateTimeFormat("en-US", {
      hour: "numeric",
      minute: "2-digit",
      second: "2-digit",
      fractionalSecondDigits: 3,
      hour12: true,
    }).format(new Date(value));
    expect(formatTerminalTimestamp(value)).toBe(expected);
    expect(formatTerminalTimestamp(value)).toMatch(/:\d{2}\.123 [AP]M$/);
  });

  test("handles midnight and noon with the expected 12-hour labels", () => {
    expect(formatTerminalTimestamp("2026-11-10T00:00:00.000Z")).toBe(
      new Intl.DateTimeFormat("en-US", {
        hour: "numeric",
        minute: "2-digit",
        second: "2-digit",
        fractionalSecondDigits: 3,
        hour12: true,
      }).format(new Date("2026-11-10T00:00:00.000Z")),
    );
    expect(formatTerminalTimestamp("2026-11-10T12:00:00.000Z")).toBe(
      new Intl.DateTimeFormat("en-US", {
        hour: "numeric",
        minute: "2-digit",
        second: "2-digit",
        fractionalSecondDigits: 3,
        hour12: true,
      }).format(new Date("2026-11-10T12:00:00.000Z")),
    );
  });

  test("preserves invalid and non-ISO values", () => {
    expect(formatTerminalTimestamp("not-a-timestamp")).toBe("not-a-timestamp");
    expect(formatTerminalTimestamp(100)).toBe(100);
    expect(formatTerminalTimestamp(null)).toBe(null);
  });
});

describe("buildTerminalEvents", () => {
  test("shows only the four most recent distinct tasks, with all events per task chronological", () => {
    const tasks = [1, 2, 3, 4, 5].map((id) => ({
      id: `t${id}`,
      agent: "codex",
      operation: `job-${id}`,
      status: "running",
      started_at: `2026-11-10T00:0${id}:00.000Z`,
      events: [
        {
          timestamp: `2026-11-10T00:0${id}:01.000Z`,
          message: `progress-${id}`,
        },
      ],
    }));
    const lines = buildTerminalEvents({ tasks_available: true, tasks });
    expect(
      lines
        .filter((line) => line.includes("[task:"))
        .map((line) => line.match(/\[task:(t\d+)/)?.[1]),
    ).toEqual(["t2", "t2", "t3", "t3", "t4", "t4", "t5", "t5"]);
    expect(lines.join("\n")).not.toContain("task:t1");
    expect(
      lines.findIndex((line) => line.includes("progress-2")),
    ).toBeGreaterThan(lines.findIndex((line) => line.includes("job-2")));
  });

  test("keeps fewer than four distinct tasks", () => {
    const lines = buildTerminalEvents({
      tasks_available: true,
      tasks: [
        {
          id: "only",
          operation: "one",
          status: "done",
          last_update: "2026-11-10T00:00:00Z",
        },
      ],
    });
    expect(lines).toContainEqual(expect.stringContaining("[task:only"));
  });

  test("reports an unavailable payload as a gap, never silently empty", () => {
    const lines = buildTerminalEvents(null);
    expect(lines).toHaveLength(1);
    expect(lines[0]).toContain("[gap:worker-activity]");
  });

  test("reports a gap per unavailable source instead of hiding it", () => {
    const lines = buildTerminalEvents({
      tasks_available: false,
      tasks_error: "The worker task ledger is not present.",
      escalation: {
        available: false,
        reason: "adw_supervisor has not written a state file",
      },
      requests: { available: false, reason: "no worker token on this machine" },
    });
    expect(lines).toContainEqual(
      expect.stringContaining(
        "[gap:tasks] The worker task ledger is not present.",
      ),
    );
    expect(lines).toContainEqual(
      expect.stringContaining(
        "[gap:escalation] adw_supervisor has not written a state file",
      ),
    );
    expect(lines).toContainEqual(
      expect.stringContaining("[gap:requests] no worker token on this machine"),
    );
    expect(lines).toContainEqual(
      expect.stringContaining("[gap:bridge-worker-supervisor]"),
    );
    expect(lines).toContainEqual(expect.stringContaining("[gap:worker-lanes]"));
    expect(lines).toContainEqual(
      expect.stringContaining("[gap:bridge-worker]"),
    );
  });

  test("surfaces explicit worker events with task/agent identity, never inventing fields", () => {
    const lines = buildTerminalEvents({
      tasks_available: true,
      tasks: [
        {
          id: "t1",
          agent: "adw-one",
          operation: "build report",
          status: "running",
          started_at: "2026-11-10T12:00:00Z",
          events: [
            { timestamp: "2026-11-10T12:00:05Z", message: "wrote 3 files" },
          ],
        },
      ],
    });
    expect(lines).toContainEqual(
      expect.stringContaining(
        `${formatTerminalTimestamp("2026-11-10T12:00:00Z")} [task:t1 agent:adw-one started] build report`,
      ),
    );
    expect(lines).toContainEqual(
      expect.stringContaining(
        `${formatTerminalTimestamp("2026-11-10T12:00:05Z")} [task:t1 agent:adw-one] wrote 3 files`,
      ),
    );
  });

  test("falls back to a plain status line only when a task has no explicit events", () => {
    const lines = buildTerminalEvents({
      tasks_available: true,
      tasks: [
        {
          id: "t2",
          agent: "codex",
          operation: "deploy",
          status: "failed",
          error: "exit 1",
          last_update: "now",
        },
      ],
    });
    expect(lines).toContainEqual(
      expect.stringContaining(
        "now [task:t2 agent:codex] deploy: failed — exit 1",
      ),
    );
  });

  test("flattens a supervised request and its child ADW tasks (parent/child identity)", () => {
    const lines = buildTerminalEvents({
      tasks_available: false,
      requests: {
        available: true,
        open: [
          {
            request_id: "r1",
            title: "print the deed",
            phase: "running",
            timer: "ok",
            since_progress: "5s",
            child_tasks: [
              { task_id: "c1", operation: "print", state: "queued" },
            ],
          },
        ],
        recently_closed: [
          {
            request_id: "r0",
            title: "earlier ask",
            state: "completed",
            outcome: "printed",
          },
        ],
        watch: { checked_seconds_ago: 12 },
      },
    });
    expect(lines).toContainEqual(
      expect.stringContaining("[request:r1 parent] print the deed"),
    );
    expect(lines.join("\n")).not.toContain("since progress");
    expect(lines).toContainEqual(
      expect.stringContaining("[request:r1 child:c1] print — queued"),
    );
    expect(lines).toContainEqual(
      expect.stringContaining(
        "[request:r0 parent closed] earlier ask — completed: printed",
      ),
    );
  });

  test("reports ledger errors and stale snapshots explicitly", () => {
    const lines = buildTerminalEvents({
      tasks_available: true,
      tasks: [],
      ledger_error: "ledger read failed",
      ledger_stale: "ledger is stale",
    });
    expect(lines).toContainEqual(
      expect.stringContaining("[gap:ledger_error] ledger read failed"),
    );
    expect(lines).toContainEqual(
      expect.stringContaining("[gap:ledger_stale] ledger is stale"),
    );
  });

  test("surfaces the adw_supervisor's escalation alerts and recorded events", () => {
    const lines = buildTerminalEvents({
      tasks_available: false,
      escalation: {
        available: true,
        alerts: [
          {
            task_id: "t9",
            tier: "diagnose",
            recent_events: [
              { time: "2026-11-10T00:00:00Z", message: "no recorded progress" },
            ],
          },
        ],
      },
    });
    expect(lines).toContainEqual(
      expect.stringContaining(
        `${formatTerminalTimestamp("2026-11-10T00:00:00Z")} [adw-supervisor task:t9 tier:diagnose] no recorded progress`,
      ),
    );
  });

  test("includes the bridge worker supervisor's own restart/deploy events", () => {
    const lines = buildTerminalEvents({
      tasks_available: false,
      supervisor: {
        checked_at: "2026-11-10T00:00:00Z",
        status: "ok",
        action: "restart",
        pid: 123,
        events: ["restarted after silence"],
      },
    });
    expect(lines).toContainEqual(
      expect.stringContaining(
        `${formatTerminalTimestamp("2026-11-10T00:00:00Z")} [bridge-worker-supervisor pid:123] ok action=restart`,
      ),
    );
    expect(lines).toContainEqual(
      expect.stringContaining(
        "[bridge-worker-supervisor pid:123] restarted after silence",
      ),
    );
  });

  test("never throws on malformed nested shapes", () => {
    expect(() =>
      buildTerminalEvents({
        tasks_available: true,
        tasks: [null, "not-an-object", { id: "t1" }],
        escalation: {
          available: true,
          alerts: [null, 42, { recent_events: ["not-an-object"] }],
        },
        requests: {
          available: true,
          open: [null, { child_tasks: [null] }],
          recently_closed: [42],
        },
        supervisor: { events: [null, 42] },
        workers: [null, 42],
      }),
    ).not.toThrow();
  });
});
