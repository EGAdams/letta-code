import { describe, expect, test } from "bun:test";
import { context, observerFixture } from "./_fixtures.ts";

describe("ConversationLatencyObserver trace lifecycle", () => {
  test("begins independent traces with deterministic identities", async () => {
    const { observer } = await observerFixture(100);

    expect(observer.begin(context)).toBe("trace-1");
    expect(
      observer.begin({
        ...context,
        generationId: "generation-2",
      }),
    ).toBe("trace-2");
  });

  test("records only the first occurrence of a milestone", async () => {
    const { subject, clock, observer } = await observerFixture(100);
    const traceId = observer.begin(context);
    clock.set(125);

    expect(
      observer.mark(traceId, subject.LatencyMilestone.AGENT_REQUESTED),
    ).toBe(true);
    clock.set(175);
    expect(
      observer.mark(traceId, subject.LatencyMilestone.AGENT_REQUESTED),
    ).toBe(false);

    const report = observer.finish(traceId, subject.LatencyOutcome.COMPLETED);
    expect(report.samples[subject.LatencyMilestone.AGENT_REQUESTED].atMs).toBe(
      125,
    );
  });

  test("rejects marks for an unknown trace without throwing", async () => {
    const { subject, observer } = await observerFixture();

    expect(
      observer.mark("missing", subject.LatencyMilestone.FIRST_AGENT_DELTA),
    ).toBe(false);
  });

  test("finishes once, publishes once, and rejects later events", async () => {
    const { subject, clock, sink, observer } = await observerFixture(10);
    const traceId = observer.begin(context);
    clock.set(20);
    const report = observer.finish(traceId, subject.LatencyOutcome.COMPLETED);

    expect(report.traceId).toBe(traceId);
    expect(report.startedAtMs).toBe(10);
    expect(report.finishedAtMs).toBe(20);
    expect(report.outcome).toBe(subject.LatencyOutcome.COMPLETED);
    expect(sink.reports).toEqual([report]);
    expect(observer.finish(traceId, subject.LatencyOutcome.FAILED)).toBeNull();
    expect(
      observer.mark(traceId, subject.LatencyMilestone.FIRST_AGENT_DELTA),
    ).toBe(false);
    expect(sink.reports).toHaveLength(1);
  });

  test("publishes interrupted and failed outcomes", async () => {
    const { subject, observer, sink } = await observerFixture();
    const interrupted = observer.begin(context);
    const failed = observer.begin({
      ...context,
      generationId: "generation-2",
    });

    observer.finish(interrupted, subject.LatencyOutcome.INTERRUPTED);
    observer.finish(failed, subject.LatencyOutcome.FAILED);

    expect(sink.reports.map((report: any) => report.outcome)).toEqual([
      subject.LatencyOutcome.INTERRUPTED,
      subject.LatencyOutcome.FAILED,
    ]);
  });

  test("discards an active trace without publishing it", async () => {
    const { subject, observer, sink } = await observerFixture();
    const traceId = observer.begin(context);

    expect(observer.discard(traceId, "superseded before request")).toBe(true);
    expect(observer.discard(traceId, "again")).toBe(false);
    expect(
      observer.finish(traceId, subject.LatencyOutcome.COMPLETED),
    ).toBeNull();
    expect(sink.reports).toEqual([]);
  });

  test("keeps concurrent traces isolated", async () => {
    const { subject, clock, observer } = await observerFixture();
    const first = observer.begin(context);
    const second = observer.begin({
      ...context,
      generationId: "generation-2",
    });
    clock.set(10);
    observer.mark(first, subject.LatencyMilestone.AGENT_REQUESTED);
    clock.set(20);
    observer.mark(second, subject.LatencyMilestone.AGENT_REQUESTED);

    const secondReport = observer.finish(
      second,
      subject.LatencyOutcome.COMPLETED,
    );
    const firstReport = observer.finish(
      first,
      subject.LatencyOutcome.COMPLETED,
    );

    expect(
      firstReport.samples[subject.LatencyMilestone.AGENT_REQUESTED].atMs,
    ).toBe(10);
    expect(
      secondReport.samples[subject.LatencyMilestone.AGENT_REQUESTED].atMs,
    ).toBe(20);
  });
});
