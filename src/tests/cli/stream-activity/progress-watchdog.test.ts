import { describe, expect, test } from "bun:test";
import {
  DEFAULT_INACTIVITY_THRESHOLDS,
  evaluateInactivity,
  type InactivityReason,
  ProgressWatchdog,
} from "../../../cli/helpers/stream-activity";
import { FakeClock, ManualTicker } from "./fakes";

const T = DEFAULT_INACTIVITY_THRESHOLDS;

describe("evaluateInactivity", () => {
  test("is quiet while both deadlines are alive", () => {
    expect(
      evaluateInactivity(
        1000,
        { lastContentMs: 1000, lastToolProgressMs: 1000 },
        T,
      ),
    ).toBeNull();
  });

  test("reports no_content once the short deadline passes", () => {
    expect(
      evaluateInactivity(
        T.noContentMs + 2,
        { lastContentMs: 0, lastToolProgressMs: 0 },
        T,
      ),
    ).toBe("no_content");
  });

  test("tolerates reasoning far past the short deadline", () => {
    // 5 minutes of continuous reasoning, last chunk 1s ago: the Mazda case.
    const now = 300_000;
    expect(
      evaluateInactivity(
        now,
        { lastContentMs: now - 1000, lastToolProgressMs: 0 },
        T,
      ),
    ).toBeNull();
  });

  test("reports no_tool_progress when reasoning never reaches a tool", () => {
    const now = T.noToolProgressMs + 2;
    expect(
      evaluateInactivity(
        now,
        { lastContentMs: now - 1000, lastToolProgressMs: 0 },
        T,
      ),
    ).toBe("no_tool_progress");
  });

  test("prefers the silence diagnosis when both deadlines have passed", () => {
    const now = T.noToolProgressMs + 2;
    expect(
      evaluateInactivity(now, { lastContentMs: 0, lastToolProgressMs: 0 }, T),
    ).toBe("no_content");
  });

  test("boundary: exactly at the deadline is not yet a timeout", () => {
    expect(
      evaluateInactivity(
        T.noContentMs,
        { lastContentMs: 0, lastToolProgressMs: 0 },
        T,
      ),
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
      watchdog.record(i % 10 === 0 ? "tool_progress" : "content");
      ticker.tick();
    }

    expect(fired).toEqual([]);
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
