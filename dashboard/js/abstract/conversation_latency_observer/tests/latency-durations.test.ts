import { describe, expect, test } from "bun:test";
import { context, observerFixture } from "./_fixtures.ts";

describe("ConversationLatencyObserver derived durations", () => {
  test("calculates every actionable first-audio interval", async () => {
    const { subject, clock, observer } = await observerFixture(0);
    const traceId = observer.begin(context);
    const marks = [
      [subject.LatencyMilestone.SPEECH_ENDED, 10],
      [subject.LatencyMilestone.TRANSCRIPT_READY, 40],
      [subject.LatencyMilestone.AGENT_REQUESTED, 50],
      [subject.LatencyMilestone.FIRST_AGENT_DELTA, 150],
      [subject.LatencyMilestone.FIRST_SENTENCE_QUEUED, 175],
      [subject.LatencyMilestone.FIRST_TTS_REQUESTED, 180],
      [subject.LatencyMilestone.FIRST_AUDIO_READY, 260],
      [subject.LatencyMilestone.FIRST_AUDIO_PLAYING, 275],
    ] as const;
    for (const [milestone, atMs] of marks) {
      clock.set(atMs);
      observer.mark(traceId, milestone);
    }
    clock.set(300);

    const report = observer.finish(traceId, subject.LatencyOutcome.COMPLETED);

    expect(report.durationsMs).toEqual({
      speechToTranscript: 30,
      agentToFirstDelta: 100,
      firstDeltaToSentence: 25,
      ttsToAudioReady: 80,
      audioReadyToPlayback: 15,
      agentToFirstAudio: 225,
      speechToFirstAudio: 265,
    });
  });

  test("omits a duration when either endpoint is missing", async () => {
    const { subject, clock, observer } = await observerFixture();
    const traceId = observer.begin(context);
    clock.set(20);
    observer.mark(traceId, subject.LatencyMilestone.AGENT_REQUESTED);
    clock.set(50);
    observer.mark(traceId, subject.LatencyMilestone.FIRST_AUDIO_PLAYING);

    const report = observer.finish(traceId, subject.LatencyOutcome.INTERRUPTED);

    expect(report.durationsMs).toEqual({ agentToFirstAudio: 30 });
  });

  test("preserves legitimate zero-duration measurements", async () => {
    const { subject, observer } = await observerFixture(50);
    const traceId = observer.begin(context);
    observer.mark(traceId, subject.LatencyMilestone.AGENT_REQUESTED);
    observer.mark(traceId, subject.LatencyMilestone.FIRST_AGENT_DELTA);

    const report = observer.finish(traceId, subject.LatencyOutcome.COMPLETED);

    expect(report.durationsMs.agentToFirstDelta).toBe(0);
  });

  test("rejects a clock regression and preserves the last valid sample", async () => {
    const { subject, clock, observer } = await observerFixture(100);
    const traceId = observer.begin(context);
    clock.set(150);
    expect(
      observer.mark(traceId, subject.LatencyMilestone.AGENT_REQUESTED),
    ).toBe(true);
    clock.set(140);

    expect(
      observer.mark(traceId, subject.LatencyMilestone.FIRST_AGENT_DELTA),
    ).toBe(false);
    clock.set(175);
    const report = observer.finish(traceId, subject.LatencyOutcome.COMPLETED);
    expect(report.samples[subject.LatencyMilestone.FIRST_AGENT_DELTA]).toBe(
      undefined,
    );
  });

  test("retains typed milestone detail without using reply text", async () => {
    const { subject, observer } = await observerFixture();
    const traceId = observer.begin(context);
    observer.mark(traceId, subject.LatencyMilestone.FIRST_TTS_REQUESTED, {
      sequence: 1,
      transport: "edge_tts",
    });

    const report = observer.finish(traceId, subject.LatencyOutcome.COMPLETED);
    expect(
      report.samples[subject.LatencyMilestone.FIRST_TTS_REQUESTED].detail,
    ).toEqual({ sequence: 1, transport: "edge_tts" });
  });
});
