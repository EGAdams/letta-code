import { describe, expect, test } from "bun:test";
import {
  context,
  loadSubject,
  ManualClock,
  observerFixture,
  RecordingSink,
  SequentialTraceIds,
} from "./_fixtures.ts";

describe("ConversationLatencyObserver report safety", () => {
  test("copies caller-owned context and milestone detail", async () => {
    const { subject, observer } = await observerFixture();
    const mutableContext = { ...context };
    const detail = { sequence: 1, transport: "edge_tts" };
    const traceId = observer.begin(mutableContext);
    observer.mark(
      traceId,
      subject.LatencyMilestone.FIRST_TTS_REQUESTED,
      detail,
    );
    mutableContext.agentId = "changed";
    detail.sequence = 99;

    const report = observer.finish(traceId, subject.LatencyOutcome.COMPLETED);
    expect(report.context.agentId).toBe("toyota");
    expect(
      report.samples[subject.LatencyMilestone.FIRST_TTS_REQUESTED].detail,
    ).toEqual({ sequence: 1, transport: "edge_tts" });
  });

  test("returns a deeply immutable report", async () => {
    const { subject, observer } = await observerFixture();
    const traceId = observer.begin(context);
    observer.mark(traceId, subject.LatencyMilestone.AGENT_REQUESTED);
    const report = observer.finish(traceId, subject.LatencyOutcome.COMPLETED);

    expect(Object.isFrozen(report)).toBe(true);
    expect(Object.isFrozen(report.context)).toBe(true);
    expect(Object.isFrozen(report.samples)).toBe(true);
    expect(Object.isFrozen(report.durationsMs)).toBe(true);
    expect(
      Object.isFrozen(report.samples[subject.LatencyMilestone.AGENT_REQUESTED]),
    ).toBe(true);
  });

  test("a failing report sink cannot break the conversation", async () => {
    const subject = await loadSubject();
    const observer = new subject.ConversationLatencyObserver({
      clock: new ManualClock(10),
      traceIds: new SequentialTraceIds(),
      sink: {
        publish() {
          throw new Error("telemetry offline");
        },
      },
    });
    const traceId = observer.begin(context);

    expect(() =>
      observer.finish(traceId, subject.LatencyOutcome.COMPLETED),
    ).not.toThrow();
  });

  test("does not share mutable report state between sink and caller", async () => {
    const subject = await loadSubject();
    const sink = new RecordingSink();
    const observer = new subject.ConversationLatencyObserver({
      clock: new ManualClock(),
      traceIds: new SequentialTraceIds(),
      sink,
    });
    const traceId = observer.begin(context);
    const report = observer.finish(traceId, subject.LatencyOutcome.COMPLETED);

    expect(sink.reports[0]).toBe(report);
    expect(Object.isFrozen(sink.reports[0])).toBe(true);
  });

  test("rejects malformed runtime milestones without closing the trace", async () => {
    const { subject, observer } = await observerFixture();
    const traceId = observer.begin(context);

    expect(observer.mark(traceId, "made_up_stage" as never)).toBe(false);
    expect(
      observer.finish(traceId, subject.LatencyOutcome.COMPLETED)?.traceId,
    ).toBe(traceId);
  });
});
