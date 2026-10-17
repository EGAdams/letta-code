import { describe, expect, test } from "bun:test";
import {
  context,
  loadSubject,
  ManualClock,
  observerFixture,
  RecordingSink,
  SequentialTraceIds,
} from "./_fixtures.ts";

describe("ConversationLatencyObserver boundary validation", () => {
  test("rejects missing clock, trace id source, and report sink dependencies", async () => {
    const subject = await loadSubject();
    const clock = new ManualClock();
    const traceIds = new SequentialTraceIds();
    const sink = new RecordingSink();

    expect(
      () =>
        new subject.ConversationLatencyObserver({
          clock: null,
          traceIds,
          sink,
        } as never),
    ).toThrow("requires a monotonic clock");
    expect(
      () =>
        new subject.ConversationLatencyObserver({
          clock,
          traceIds: null,
          sink,
        } as never),
    ).toThrow("requires a trace id source");
    expect(
      () =>
        new subject.ConversationLatencyObserver({
          clock,
          traceIds,
          sink: null,
        } as never),
    ).toThrow("requires a report sink");
  });

  test("rejects empty, non-string, and unsupported trace context fields", async () => {
    const { observer } = await observerFixture();
    const invalidContexts = [
      { ...context, sessionId: " " },
      { ...context, generationId: "" },
      { ...context, agentId: 7 },
      { ...context, inputMode: "telephone" },
    ];

    for (const invalid of invalidContexts) {
      expect(() => observer.begin(invalid as never)).toThrow(
        "invalid latency trace context",
      );
    }
  });

  test("rejects empty or previously issued trace identities", async () => {
    const subject = await loadSubject();
    const sink = new RecordingSink();
    const clock = new ManualClock();
    const ids = ["", "trace-reused", "trace-reused"];
    const observer = new subject.ConversationLatencyObserver({
      clock,
      sink,
      traceIds: { next: () => ids.shift() ?? "trace-fallback" },
    });

    expect(() => observer.begin(context)).toThrow("invalid or active id");
    const traceId = observer.begin(context);
    observer.finish(traceId, subject.LatencyOutcome.COMPLETED);
    expect(() => observer.begin(context)).toThrow("invalid or active id");
  });

  test("contains invalid clock readings and clock failures", async () => {
    const subject = await loadSubject();
    let reading = 10;
    let fail = false;
    const observer = new subject.ConversationLatencyObserver({
      clock: {
        now() {
          if (fail) throw new Error("clock offline");
          return reading;
        },
      },
      traceIds: new SequentialTraceIds(),
      sink: new RecordingSink(),
    });
    const traceId = observer.begin(context);

    reading = Number.NaN;
    expect(
      observer.mark(traceId, subject.LatencyMilestone.AGENT_REQUESTED),
    ).toBe(false);
    reading = Number.POSITIVE_INFINITY;
    expect(
      observer.mark(traceId, subject.LatencyMilestone.AGENT_REQUESTED),
    ).toBe(false);
    fail = true;
    expect(() =>
      observer.mark(traceId, subject.LatencyMilestone.AGENT_REQUESTED),
    ).not.toThrow();
    expect(
      observer.mark(traceId, subject.LatencyMilestone.AGENT_REQUESTED),
    ).toBe(false);
    expect(() =>
      observer.finish(traceId, subject.LatencyOutcome.FAILED),
    ).not.toThrow();
  });

  test("rejects invalid milestone detail and removes unexpected text", async () => {
    const { subject, observer } = await observerFixture();
    const traceId = observer.begin(context);

    expect(
      observer.mark(traceId, subject.LatencyMilestone.FIRST_TTS_REQUESTED, {
        sequence: -1,
      }),
    ).toBe(false);
    expect(
      observer.mark(traceId, subject.LatencyMilestone.FIRST_TTS_REQUESTED, {
        transport: 42,
      } as never),
    ).toBe(false);
    expect(
      observer.mark(traceId, subject.LatencyMilestone.FIRST_TTS_REQUESTED, {
        sequence: 1,
        transport: "edge_tts",
        text: "private assistant reply",
      } as never),
    ).toBe(true);

    const report = observer.finish(traceId, subject.LatencyOutcome.COMPLETED);
    expect(
      report?.samples[subject.LatencyMilestone.FIRST_TTS_REQUESTED]?.detail,
    ).toEqual({ sequence: 1, transport: "edge_tts" });
  });

  test("an invalid outcome leaves the trace active and recoverable", async () => {
    const { subject, observer, sink } = await observerFixture();
    const traceId = observer.begin(context);

    expect(observer.finish(traceId, "timed_out" as never)).toBeNull();
    expect(sink.reports).toHaveLength(0);
    expect(
      observer.mark(traceId, subject.LatencyMilestone.AGENT_REQUESTED),
    ).toBe(true);
    expect(
      observer.finish(traceId, subject.LatencyOutcome.FAILED)?.outcome,
    ).toBe(subject.LatencyOutcome.FAILED);
    expect(sink.reports).toHaveLength(1);
  });
});
