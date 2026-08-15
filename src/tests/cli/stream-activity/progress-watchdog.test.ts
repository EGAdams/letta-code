import { describe, expect, test } from "bun:test";
import {
  type ActivityMarks,
  DEFAULT_INACTIVITY_THRESHOLDS,
  evaluateInactivity,
  type InactivityReason,
  ProgressWatchdog,
} from "../../../cli/helpers/stream-activity";
import { FakeClock, ManualTicker } from "./fakes";

const T = DEFAULT_INACTIVITY_THRESHOLDS;

/** Marks with the idle default, so each test states only what it varies. */
function marks(over: Partial<ActivityMarks> = {}): ActivityMarks {
  return {
    lastContentMs: 0,
    lastToolProgressMs: 0,
    toolInFlight: false,
    ...over,
  };
}

describe("evaluateInactivity", () => {
  test("is quiet while both deadlines are alive", () => {
    expect(
      evaluateInactivity(
        1000,
        marks({ lastContentMs: 1000, lastToolProgressMs: 1000 }),
        T,
      ),
    ).toBeNull();
  });

  test("reports no_content once the short deadline passes", () => {
    expect(evaluateInactivity(T.noContentMs + 2, marks(), T)).toBe(
      "no_content",
    );
  });

  test("tolerates reasoning far past the short deadline", () => {
    // 5 minutes of continuous reasoning, last chunk 1s ago: the Mazda case.
    const now = 300_000;
    expect(
      evaluateInactivity(now, marks({ lastContentMs: now - 1000 }), T),
    ).toBeNull();
  });

  test("reports no_tool_progress when reasoning never reaches a tool", () => {
    const now = T.noToolProgressMs + 2;
    expect(
      evaluateInactivity(now, marks({ lastContentMs: now - 1000 }), T),
    ).toBe("no_tool_progress");
  });

  test("prefers the silence diagnosis when both deadlines have passed", () => {
    const now = T.noToolProgressMs + 2;
    expect(evaluateInactivity(now, marks(), T)).toBe("no_content");
  });

  test("boundary: exactly at the deadline is not yet a timeout", () => {
    expect(evaluateInactivity(T.noContentMs, marks(), T)).toBeNull();
  });

  // ── Regression: a slow tool is not a dead stream ────────────────────────
  // run_claude_code_sdk runs a nested Claude session on a remote executor and
  // emits nothing for minutes. Before the fix the 90s no-content deadline
  // fired mid-call and killed the run — Mazda's "Interrupted by user".

  test("silence while a tool is executing is not no_content", () => {
    const now = T.noContentMs * 3;
    expect(
      evaluateInactivity(
        now,
        marks({ toolInFlight: true, lastToolProgressMs: now - 1 }),
        T,
      ),
    ).toBeNull();
  });

  test("the short deadline re-arms once the tool returns", () => {
    const returnedAt = 1000;
    const now = returnedAt + T.noContentMs + 2;
    expect(
      evaluateInactivity(
        now,
        marks({ lastContentMs: returnedAt, lastToolProgressMs: returnedAt }),
        T,
      ),
    ).toBe("no_content");
  });

  test("a tool that never returns still trips its own backstop", () => {
    const now = T.stalledToolMs + 2;
    expect(evaluateInactivity(now, marks({ toolInFlight: true }), T)).toBe(
      "stalled_tool",
    );
  });

  test("a slow tool is not cut off at the planning-loop deadline", () => {
    // The stack allows 900s per call; 600s is the model-behaviour budget and
    // must not be applied to a tool that is legitimately still running.
    expect(T.stalledToolMs).toBeGreaterThan(T.noToolProgressMs);
    const now = T.noToolProgressMs + 2;
    expect(
      evaluateInactivity(now, marks({ toolInFlight: true }), T),
    ).toBeNull();
  });
});

describe("ProgressWatchdog", () => {
  function build(thresholds = T) {
    const clock = new FakeClock();
    const ticker = new ManualTicker();
    const fired: InactivityReason[] = [];
    const watchdog = new ProgressWatchdog({ clock, ticker, thresholds });
    return { clock, ticker, fired, watchdog };
  }

  test("polls on the configured interval", () => {
    const { ticker, watchdog, fired } = build();
    watchdog.start((r) => fired.push(r));
    expect(ticker.intervals).toEqual([T.pollIntervalMs]);
  });

  test("content activity holds off the short deadline indefinitely", () => {
    const { clock, ticker, watchdog, fired } = build();
    watchdog.start((r) => fired.push(r));

    for (let i = 0; i < 10; i++) {
      clock.advance(30_000);
      watchdog.record("content");
      ticker.tick();
    }

    expect(fired).toEqual([]);
    expect(watchdog.firedReason()).toBeNull();
  });

  test("content-only activity still trips the long deadline", () => {
    const { clock, ticker, watchdog, fired } = build();
    watchdog.start((r) => fired.push(r));

    for (let i = 0; i < 30; i++) {
      clock.advance(30_000);
      watchdog.record("content");
      ticker.tick();
    }

    expect(fired).toEqual(["no_tool_progress"]);
  });

  test("tool progress resets the long deadline", () => {
    const { clock, ticker, watchdog, fired } = build();
    watchdog.start((r) => fired.push(r));

    for (let i = 0; i < 60; i++) {
      clock.advance(30_000);
      // A balanced call/return every 10th iteration, content in between.
      if (i % 10 === 0) {
        watchdog.record("tool_started");
        watchdog.record("tool_finished");
      } else {
        watchdog.record("content");
      }
      ticker.tick();
    }

    expect(fired).toEqual([]);
  });

  test("survives a tool that runs far longer than the short deadline", () => {
    // The Mazda repro: dispatch run_claude_code_sdk, then total silence for
    // 5 minutes while it executes remotely, then the return arrives.
    const { clock, ticker, watchdog, fired } = build();
    watchdog.start((r) => fired.push(r));

    watchdog.record("tool_started");
    for (let i = 0; i < 10; i++) {
      clock.advance(30_000); // 300s of silence, no chunks at all
      ticker.tick();
    }
    watchdog.record("tool_finished");

    expect(fired).toEqual([]);
    expect(watchdog.firedReason()).toBeNull();
  });

  test("resumes guarding silence after the tool returns", () => {
    const { clock, ticker, watchdog, fired } = build();
    watchdog.start((r) => fired.push(r));

    watchdog.record("tool_started");
    clock.advance(T.noContentMs * 2);
    ticker.tick();
    watchdog.record("tool_finished");

    clock.advance(T.noContentMs + 1);
    ticker.tick();

    expect(fired).toEqual(["no_content"]);
  });

  test("stays armed until the LAST of several parallel tools returns", () => {
    const { clock, ticker, watchdog, fired } = build();
    watchdog.start((r) => fired.push(r));

    watchdog.record("tool_started");
    watchdog.record("tool_started");
    watchdog.record("tool_finished"); // one back, one still running

    clock.advance(T.noContentMs * 2);
    ticker.tick();
    expect(fired).toEqual([]); // still in flight → silence tolerated

    watchdog.record("tool_finished"); // now idle
    clock.advance(T.noContentMs + 1);
    ticker.tick();
    expect(fired).toEqual(["no_content"]);
  });

  test("an unmatched tool return cannot leave the count negative", () => {
    const { clock, ticker, watchdog, fired } = build();
    watchdog.start((r) => fired.push(r));

    watchdog.record("tool_finished"); // stray return, no matching call
    watchdog.record("tool_started");

    clock.advance(T.noContentMs * 2);
    ticker.tick();

    // If the stray return had driven the counter to -1, the real call would
    // land at 0 and this silence would have been misread as a dead stream.
    expect(fired).toEqual([]);
  });

  test("reports stalled_tool when a dispatched tool never returns", () => {
    const { clock, ticker, watchdog, fired } = build();
    watchdog.start((r) => fired.push(r));

    watchdog.record("tool_started");
    clock.advance(T.stalledToolMs + 1);
    ticker.tick();

    expect(fired).toEqual(["stalled_tool"]);
  });

  test("fires once and stops polling", () => {
    const { clock, ticker, watchdog, fired } = build();
    watchdog.start((r) => fired.push(r));

    clock.advance(T.noContentMs + 1);
    ticker.tick();
    ticker.tick();
    clock.advance(T.noContentMs + 1);
    ticker.tick();

    expect(fired).toEqual(["no_content"]);
    expect(watchdog.firedReason()).toBe("no_content");
    expect(ticker.running).toBe(0);
  });

  test("stop() ends polling without reporting a timeout", () => {
    const { clock, ticker, watchdog, fired } = build();
    watchdog.start((r) => fired.push(r));
    watchdog.stop();

    clock.advance(T.noToolProgressMs * 2);
    ticker.tick();

    expect(fired).toEqual([]);
    expect(watchdog.firedReason()).toBeNull();
    expect(ticker.running).toBe(0);
  });

  test("start() is idempotent", () => {
    const { ticker, watchdog, fired } = build();
    watchdog.start((r) => fired.push(r));
    watchdog.start((r) => fired.push(r));
    expect(ticker.running).toBe(1);
  });
});
