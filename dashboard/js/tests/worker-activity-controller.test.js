import { describe, expect, test } from "bun:test";
import { createWorkerActivity } from "../boot/worker-activity.js";

import { fakeEnv, ledger } from "./worker-activity-harness.js";

describe("Worker Activity controller", () => {
  test("never overlaps requests and keeps one live timer", async () => {
    const env = fakeEnv([ledger("running")]);
    const wkr = createWorkerActivity(env);
    void wkr.open();
    void wkr.poll();
    expect(env.calls()).toBe(1);
    await env.flush();
    expect(env.timers.filter((t) => t.live).length).toBe(1);
  });

  test("polls fast only while the page is active", async () => {
    const env = fakeEnv([ledger("running")]);
    createWorkerActivity(env);
    await env.flush();
    expect(env.timers.at(-1).ms).toBe(20000);
    env.nodes["worker-activity"].classList.add("active");
    await env.timers.at(-1).fn();
    await env.flush();
    expect(env.timers.at(-1).ms).toBe(5000);
  });

  test("stops its timer and observer on unmount, then resumes on activation", async () => {
    const env = fakeEnv([ledger("running")]);
    const wkr = createWorkerActivity(env);
    await env.flush();
    const timer = env.timers.at(-1);
    wkr.stop();
    expect(timer.live).toBe(false);
    expect(env.timers.filter((t) => t.live).length).toBe(0);
    env.nodes["worker-activity"].classList.add("active");
    void wkr.open();
    expect(env.calls()).toBe(2);
  });

  test("updates legend and SVG on change only, and feeds subscribers", async () => {
    const env = fakeEnv([
      ledger("running"),
      ledger("running"),
      ledger("failed"),
    ]);
    const wkr = createWorkerActivity(env);
    const seen = [];
    wkr.subscribe((p) => seen.push(p.tasks[0].status));
    await env.flush();
    expect(env.nodes["worker-legend"].innerHTML).toContain("running");
    expect(env.nodes["worker-activity-body"].innerHTML).toContain("<svg");
    expect(env.nodes["worker-activity-body"].innerHTML).toContain(
      "Worker event output",
    );
    void wkr.poll();
    await env.flush();
    expect(env.parts.workflow?.writes ?? 0).toBe(0); // same tasks: no redraw
    void wkr.poll();
    await env.flush();
    expect(env.parts.workflow.writes).toBe(1);
    expect(env.parts.workflow.innerHTML).toContain("is-failed");
    expect(env.nodes["worker-legend"].innerHTML).toContain("failed");
    expect(seen).toEqual(["running", "running", "failed"]);
  });

  test("shows last refresh and stops the running indicator at completion", async () => {
    const env = fakeEnv([ledger("running"), ledger("succeeded")]);
    const wkr = createWorkerActivity(env);
    await env.flush();
    expect(env.nodes["worker-activity-body"].innerHTML).toContain(
      "Last refresh",
    );
    expect(env.nodes["worker-activity-body"].innerHTML).toContain(
      "bridge-running-indicator",
    );
    void wkr.poll();
    await env.flush();
    expect(env.nodes["worker-activity-body"].innerHTML).toContain("Succeeded");
    expect(env.nodes["worker-activity-body"].innerHTML).not.toContain(
      "bridge-running-indicator",
    );
  });

  test("renders real ledger status safely in the terminal panel", async () => {
    const env = fakeEnv([
      {
        ...ledger("running"),
        tasks: [
          {
            id: "t1",
            agent: "adw-one",
            operation: "build <report>",
            status: "failed",
            last_update: "2026-11-03T12:00:00Z",
            error: "bad & unsafe",
          },
        ],
      },
    ]);
    createWorkerActivity(env);
    await env.flush();
    const html = env.nodes["worker-activity-body"].innerHTML;
    expect(html).toContain(
      "2026-11-03T12:00:00Z [adw-one] build &lt;report&gt;: failed — bad &amp; unsafe",
    );
    expect(html).not.toContain("build <report>");
  });

  test("updates the live terminal in place across polls when tasks have no explicit events", async () => {
    // Status-only tasks (no events/progress_events) make renderWorkerTerminal
    // emit a second "unavailable" <p> before <pre>. The old regex-splice live
    // update only tolerated one <p> and silently failed to strip the
    // section/pre wrapper, nesting a whole extra <section><pre> inside the
    // terminal element on every poll after the first.
    const env = fakeEnv([
      {
        ...ledger("running"),
        tasks: [{ id: "t1", agent: "codex", status: "running" }],
      },
      {
        ...ledger("running"),
        tasks: [{ id: "t1", agent: "codex", status: "succeeded" }],
      },
    ]);
    const wkr = createWorkerActivity(env);
    await env.flush();
    void wkr.poll();
    await env.flush();
    const terminal = env.parts.terminal.terminal;
    expect(terminal.innerHTML).not.toContain("<section");
    expect(terminal.innerHTML).not.toContain("<pre");
    expect(terminal.innerHTML).toContain("succeeded");
  });

  test("follows output, pauses on manual scroll, and resumes at the bottom", async () => {
    const env = fakeEnv([
      { ...ledger("running"), tasks: [{ id: "t1", status: "running" }] },
      {
        ...ledger("running"),
        tasks: [
          { id: "t1", status: "running" },
          { id: "t2", status: "running" },
        ],
      },
      {
        ...ledger("running"),
        tasks: [
          { id: "t1", status: "running" },
          { id: "t2", status: "running" },
          { id: "t3", status: "running" },
        ],
      },
    ]);
    const wkr = createWorkerActivity(env);
    await env.flush();
    const terminal = env.parts.terminal.terminal;
    terminal.scrollTop = 300;
    terminal.dispatchEvent({ type: "scroll" });
    void wkr.poll();
    await env.flush();
    expect(terminal.scrollTop).toBe(300);
    terminal.scrollTop = 792;
    terminal.dispatchEvent({ type: "scroll" });
    void wkr.poll();
    await env.flush();
    expect(terminal.scrollTop).toBe(1000);
  });

  test("resets follow mode when the ledger is cleared", async () => {
    const env = fakeEnv([
      { ...ledger("running"), tasks: [{ id: "t1", status: "running" }] },
      { ...ledger("running"), tasks: [] },
    ]);
    const wkr = createWorkerActivity(env);
    await env.flush();
    const terminal = env.parts.terminal.terminal;
    terminal.scrollTop = 300;
    terminal.dispatchEvent({ type: "scroll" });
    void wkr.poll();
    await env.flush();
    expect(terminal.scrollTop).toBe(1000);
    expect(wkr.terminalFollow).toBe(true);
  });

  test("shows provider selection as disabled when the bridge has no provider contract", async () => {
    const env = fakeEnv([ledger("running")]);
    const wkr = createWorkerActivity(env);
    await env.flush();
    expect(env.nodes["worker-activity-body"].innerHTML).toContain(
      "Provider availability and current selection are not exposed",
    );
    expect(env.nodes["worker-activity-body"].innerHTML).toContain(
      'disabled aria-disabled="true">Codex</button>',
    );
    expect(env.nodes["worker-activity-body"].innerHTML).toContain(
      "Claude Sonnet",
    );
    expect(env.nodes["worker-activity-body"].innerHTML).toContain(
      "Selection is unavailable",
    );
    void wkr;
  });

  test("renders only explicit future provider availability and selection", async () => {
    const env = fakeEnv([
      {
        ...ledger("running"),
        provider_selection: {
          current: "codex",
          providers: [
            { id: "codex", label: "Codex", available: true },
            { id: "claude-sonnet", label: "Claude Sonnet", available: false },
          ],
        },
      },
    ]);
    createWorkerActivity(env);
    await env.flush();
    const html = env.nodes["worker-activity-body"].innerHTML;
    expect(html).toContain("Codex — selected");
    expect(html).toContain("Claude Sonnet — unavailable");
    expect(html).toContain("Switching is not supported");
  });

  test("a failed request keeps the SVG and says why", async () => {
    const env = fakeEnv([new Error("HTTP 502")]);
    createWorkerActivity(env);
    await env.flush();
    const html = env.nodes["worker-activity-body"].innerHTML;
    expect(html).toContain("<svg");
    expect(html).toContain("HTTP 502");
    expect(
      env.nodes["btn-worker-activity"].classList.contains("poll-disabled"),
    ).toBe(true);
  });

  test("renders five rows bound to real, unique task ids, ranked deterministically", async () => {
    const env = fakeEnv([
      {
        ...ledger("running"),
        tasks: [
          {
            id: "ok-1",
            status: "succeeded",
            last_update: "2026-11-05T01:00:00Z",
          },
          {
            id: "fail-1",
            status: "failed",
            last_update: "2026-11-05T02:00:00Z",
          },
          {
            id: "run-1",
            status: "running",
            last_update: "2026-11-05T03:00:00Z",
          },
        ],
      },
    ]);
    createWorkerActivity(env);
    await env.flush();
    const html = env.nodes["worker-activity-body"].innerHTML;
    expect(html.match(/data-worker-row-index="\d"/g)?.length).toBe(5);
    const taskIds = [
      ...html.matchAll(/data-worker-row-task-id="([^"]*)"/g),
    ].map((m) => m[1]);
    expect(taskIds).toEqual(["fail-1", "run-1", "ok-1"]);
    expect(new Set(taskIds).size).toBe(taskIds.length);
    expect(html).toContain("No further active or recent job to display.");
  });

  test("flashes only the row whose status really transitioned on the next 5-second poll", async () => {
    const env = fakeEnv([
      {
        ...ledger("running"),
        tasks: [
          { id: "t1", status: "running" },
          { id: "t2", status: "queued", attempts: 1 },
        ],
      },
      {
        ...ledger("running"),
        tasks: [
          { id: "t1", status: "failed" },
          { id: "t2", status: "queued", attempts: 1 },
        ],
      },
    ]);
    const wkr = createWorkerActivity(env);
    await env.flush();
    expect(env.nodes["worker-activity-body"].innerHTML).not.toContain(
      "is-changed",
    );
    void wkr.poll();
    await env.flush();
    const html = env.nodes["worker-activity-body"].innerHTML;
    expect(html).toContain('data-worker-row-task-id="t1"');
    expect(html).toMatch(
      /is-failed is-changed" data-worker-row-index="0" data-worker-row-task-id="t1"/,
    );
    expect(html).not.toMatch(
      /is-changed" data-worker-row-index="\d" data-worker-row-task-id="t2"/,
    );
  });

  test("recovers on the next poll after a request failure", async () => {
    const env = fakeEnv([new Error("temporary outage"), ledger("running")]);
    const wkr = createWorkerActivity(env);
    await env.flush();
    expect(env.nodes["worker-activity-body"].innerHTML).toContain(
      "temporary outage",
    );
    void wkr.poll();
    await env.flush();
    expect(env.nodes["worker-activity-body"].innerHTML).toContain("running");
    expect(
      env.nodes["btn-worker-activity"].classList.contains("poll-disabled"),
    ).toBe(false);
  });
});
