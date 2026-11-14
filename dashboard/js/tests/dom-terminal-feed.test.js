import { describe, expect, test } from "bun:test";
import { buildTerminalEvents } from "../abstract/terminal-feed.js";
import { createTerminalFeed } from "../implementation/dom-terminal-feed.js";
import { fakeTerminalEnv } from "./terminal-feed-harness.js";

// A payload where every other source is present and unchanging, so only the
// task line itself varies between fixtures below — the other categories
// (escalation/requests/supervisor/workers/worker) always render identical
// text and so dedupe to zero new lines across polls, letting tests assert on
// deltas instead of brittle totals that track buildTerminalEvents internals.
const ledger = (status) => ({
  tasks_available: true,
  tasks: [
    {
      id: "t1",
      agent: "codex",
      operation: "build",
      status,
      last_update: "2026-11-10T00:00:00Z",
    },
  ],
  escalation: { available: true, alerts: [] },
  requests: {
    available: true,
    open: [],
    recently_closed: [],
    watch: { checked_seconds_ago: 1 },
  },
  supervisor: { checked_at: "t", status: "ok", action: "none", pid: 1 },
  workers: [{ lane: "general", installed: true, healthy: true }],
  worker: { status: "active", reason: "polling", observed_at: "t" },
  diagnostic: { status: "active", action: "none" },
});

function textOf(env) {
  return env.stream.children.map((c) => c.textContent);
}

describe("buildTerminalEvents bridge-worker line", () => {
  const withWorker = (status, observed_at) => ({
    ...ledger("running"),
    worker: { status: "active", reason: "polling", observed_at },
    diagnostic: {
      status,
      action:
        "No action indicated by local process, heartbeat, and queue observations.",
    },
  });
  const workerLines = (payload) =>
    buildTerminalEvents(payload).filter((l) => l.includes("[bridge-worker]"));

  test("stays quiet while the worker is healthy, whatever the timestamp", () => {
    expect(workerLines(withWorker("healthy", 1))).toEqual([]);
    expect(workerLines(withWorker("healthy", 2))).toEqual([]);
  });

  test("still prints when the worker is not healthy", () => {
    expect(workerLines(withWorker("stalled", 1))).toEqual([
      expect.stringContaining("stalled"),
    ]);
  });
});

describe("buildTerminalEvents supervisor line", () => {
  const withSupervisor = (status, checked_at, events = []) => ({
    ...ledger("running"),
    supervisor: {
      checked_at,
      status,
      action: "none",
      pid: 1,
      restarts_in_window: 0,
      max_restarts: 3,
      events,
    },
  });
  const supLines = (payload) =>
    buildTerminalEvents(payload).filter((l) =>
      l.includes("[bridge-worker-supervisor"),
    );

  test("stays quiet while healthy with nothing to do, whatever the timestamp", () => {
    expect(supLines(withSupervisor("healthy", 1))).toEqual([]);
    expect(supLines(withSupervisor("healthy", 2))).toEqual([]);
  });

  test("still prints when the supervisor sees a problem", () => {
    expect(supLines(withSupervisor("stalled", 1))).toEqual([
      expect.stringContaining("stalled"),
    ]);
  });

  test("an event keeps its own time, so it is identical across polls", () => {
    const event = { at: 100, status: "stalled", message: "restarted worker" };
    expect(supLines(withSupervisor("healthy", 1, [event]))).toEqual(
      supLines(withSupervisor("healthy", 2, [event])),
    );
    expect(supLines(withSupervisor("healthy", 1, [event]))[0]).toStartWith(
      "100 ",
    );
  });
});

describe("createTerminalFeed", () => {
  test("keeps the live display to the four newest task IDs as a task arrives", async () => {
    const payload = (ids) => ({
      tasks_available: true,
      tasks: ids.map((id, index) => ({
        id,
        operation: `job-${id}`,
        status: "running",
        last_update: `2026-11-10T00:0${index + 1}:00Z`,
      })),
      escalation: {
        available: true,
        alerts: [
          {
            task_id: "alert",
            tier: "urgent",
            recent_events: [{ time: "—", message: "important alert" }],
          },
        ],
      },
      requests: {
        available: true,
        open: [],
        recently_closed: [],
        watch: { checked_seconds_ago: 1 },
      },
      supervisor: {
        checked_at: "t",
        status: "healthy",
        action: "none",
        pid: 1,
      },
      workers: [{ lane: "general", installed: true, healthy: true }],
      worker: { status: "active", observed_at: "t" },
      diagnostic: { status: "healthy" },
    });
    const env = fakeTerminalEnv([
      payload(["t1", "t2", "t3", "t4"]),
      payload(["t1", "t2", "t3", "t4", "t5"]),
    ]);
    createTerminalFeed(env);
    await env.flush();
    await env.timers.at(-1).fn();
    await env.flush();
    const text = textOf(env).join("\n");
    expect(text).not.toContain("task:t1");
    expect(text).toContain("task:t2");
    expect(text).toContain("task:t5");
    expect(text).toContain("important alert");
  });

  test("renders every normalized line from the first poll and auto-scrolls to the bottom", async () => {
    const env = fakeTerminalEnv([ledger("running")]);
    createTerminalFeed(env);
    await env.flush();
    const expected = buildTerminalEvents(ledger("running"));
    expect(textOf(env)).toEqual(expected);
    expect(textOf(env)).toContainEqual(
      expect.stringContaining("[task:t1 agent:codex] build: running"),
    );
    expect(env.stream.scrollTop).toBe(env.stream.scrollHeight);
    expect(env.status.textContent).toContain("Connected");
  });

  test("never overlaps requests and keeps one live timer", async () => {
    const env = fakeTerminalEnv([ledger("running")]);
    const feed = createTerminalFeed(env);
    void feed.poll();
    expect(env.calls()).toBe(1);
    await env.flush();
    expect(env.timers.filter((t) => t.live).length).toBe(1);
  });

  test("deduplicates unchanged lines across polls and appends only what actually changed", async () => {
    const env = fakeTerminalEnv([
      ledger("running"),
      ledger("running"),
      ledger("failed"),
    ]);
    createTerminalFeed(env);
    await env.flush();
    const afterFirst = textOf(env).length;
    await env.timers.at(-1).fn();
    await env.flush();
    expect(textOf(env).length).toBe(afterFirst); // identical ledger: nothing new
    await env.timers.at(-1).fn();
    await env.flush();
    expect(textOf(env).length).toBe(afterFirst + 1); // only the task status actually changed
    expect(textOf(env).at(-1)).toContain("failed");
  });

  test("polls fast only while the Terminal view is active and visible", async () => {
    const env = fakeTerminalEnv([ledger("running")]);
    createTerminalFeed(env);
    await env.flush();
    expect(env.timers.at(-1).ms).toBe(20000);
    env.nodes.terminal.classList.active = true;
    await env.timers.at(-1).fn();
    await env.flush();
    expect(env.timers.at(-1).ms).toBe(5000);
  });

  test("backs off and reports reconnecting on fetch failure, then recovers without a reload", async () => {
    const env = fakeTerminalEnv([new Error("network down"), ledger("running")]);
    createTerminalFeed(env);
    await env.flush();
    expect(env.status.textContent).toContain("Reconnecting");
    expect(textOf(env)).toHaveLength(0);
    expect(env.timers.at(-1).ms).toBe(15000);
    await env.timers.at(-1).fn();
    await env.flush();
    expect(env.status.textContent).toContain("Connected");
    expect(textOf(env)).toEqual(buildTerminalEvents(ledger("running")));
  });

  test("Clear empties the view without resurrecting already-seen lines on the next identical poll", async () => {
    const env = fakeTerminalEnv([ledger("running"), ledger("running")]);
    const feed = createTerminalFeed(env);
    await env.flush();
    expect(textOf(env).length).toBeGreaterThan(0);
    feed.clear();
    expect(textOf(env)).toHaveLength(0);
    await env.timers.at(-1).fn();
    await env.flush();
    expect(textOf(env)).toHaveLength(0); // same ledger: deliberately not re-shown
  });

  test("Clear posts the shared signal and suppresses the old snapshot after an epoch change", async () => {
    const first = { ...ledger("running"), terminal_clear_epoch: 0 };
    const afterClear = { ...ledger("running"), terminal_clear_epoch: 1 };
    const changed = { ...ledger("failed"), terminal_clear_epoch: 1 };
    const env = fakeTerminalEnv([first, afterClear, changed]);
    const feed = createTerminalFeed(env);
    await env.flush();
    feed.clear();
    expect(env.posts).toEqual([{ url: "/api/terminal-clear", body: {} }]);
    await env.timers.at(-1).fn();
    await env.flush();
    expect(textOf(env)).toHaveLength(0);
    await env.timers.at(-1).fn();
    await env.flush();
    expect(textOf(env)).toContainEqual(expect.stringContaining("failed"));
    expect(textOf(env)).not.toContainEqual(expect.stringContaining("running"));
  });

  test("a reload at an existing clear epoch suppresses cached lines until a new change", async () => {
    const env = fakeTerminalEnv([
      { ...ledger("running"), terminal_clear_epoch: 7 },
    ]);
    createTerminalFeed(env);
    await env.flush();
    expect(textOf(env)).toHaveLength(0);
  });

  test("stops its timer on unmount and resumes polling when re-activated", async () => {
    const env = fakeTerminalEnv([ledger("running")]);
    const feed = createTerminalFeed(env);
    await env.flush();
    const timer = env.timers.at(-1);
    feed.stop();
    expect(timer.live).toBe(false);
    void feed.poll();
    expect(env.calls()).toBe(2);
  });

  test("stops following the bottom once the user scrolls up, and leaves scroll position alone", async () => {
    const env = fakeTerminalEnv([ledger("running"), ledger("failed")]);
    createTerminalFeed(env);
    await env.flush();
    const afterFirst = textOf(env).length;
    env.stream.scrollTop = 0; // user scrolled away from the bottom
    env.stream.listeners.scroll();
    await env.timers.at(-1).fn();
    await env.flush();
    expect(textOf(env).length).toBe(afterFirst + 1);
    expect(env.stream.scrollTop).toBe(0); // not forced back to bottom
  });
});
