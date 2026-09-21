import { describe, expect, test } from "bun:test";
import { SpokenOutputPolicy } from "../../spoken-output-policy.js";
import { VoiceSession } from "../../voice_session/src/voice-session.ts";
import {
  ConversationCoordinator,
  DeterministicSentenceSegmenter,
  type SpeechSegment,
} from "../src/conversation-coordinator.ts";

describe("DeterministicSentenceSegmenter", () => {
  test("emits a sentence split across arbitrary provider deltas", () => {
    const segmenter = new DeterministicSentenceSegmenter();
    expect(segmenter.push("Hello there.")).toEqual([]);
    expect(segmenter.push(" How are")).toEqual(["Hello there."]);
    expect(segmenter.push(" you?")).toEqual([]);
    expect(segmenter.flush()).toBe("How are you?");
  });

  test("does not split decimal numbers or common abbreviations", () => {
    const segmenter = new DeterministicSentenceSegmenter();
    expect(segmenter.push("Dr. Rivera paid 3.50 today. Next item ")).toEqual([
      "Dr. Rivera paid 3.50 today.",
    ]);
    expect(segmenter.flush()).toBe("Next item");
  });

  test("uses a bounded phrase when punctuation takes too long", () => {
    const segmenter = new DeterministicSentenceSegmenter(40);
    const phrases = segmenter.push(
      "This deliberately long response has enough words to cross the latency boundary",
    );
    expect(phrases).toEqual([
      "This deliberately long response has",
      "enough words to cross the latency",
    ]);
    expect(segmenter.flush()).toBe("boundary");
  });
});

describe("ConversationCoordinator", () => {
  test("queues the first sentence before the agent emits its terminal event", async () => {
    const session = new VoiceSession();
    const order: string[] = [];
    const queued: SpeechSegment[] = [];
    let releaseTerminal!: () => void;
    const waitForTerminal = new Promise<void>((resolve) => {
      releaseTerminal = resolve;
    });
    const agent = {
      async *submit(_turn: unknown, generationId: string) {
        yield {
          kind: "assistant_text",
          text: "First sentence. ",
          generationId,
        };
        order.push("first-delta-delivered");
        await waitForTerminal;
        yield { kind: "terminal", text: "", generationId };
      },
      cancel() {},
    };
    const coordinator = new ConversationCoordinator({
      agent,
      session,
      spokenOutputPolicy: new SpokenOutputPolicy({ session }),
      sentenceSegmenter: new DeterministicSentenceSegmenter(),
      speechQueue: {
        enqueue(segment) {
          queued.push(segment);
          order.push("speech-queued");
        },
        async finish() {
          order.push("speech-finished");
        },
        cancel() {},
      },
    });

    const result = coordinator.start(
      { agent: "toyota", text: "hello" },
      { agentName: "Toyota", speak: true },
    );
    await Promise.resolve();
    await Promise.resolve();
    expect(queued.map((segment) => segment.text)).toEqual(["First sentence."]);
    expect(order).toEqual(["speech-queued", "first-delta-delivered"]);
    releaseTerminal();
    expect((await result).status).toBe("completed");
  });

  test("drops stale events and cancels agent plus audio on interruption", async () => {
    const session = new VoiceSession();
    const cancelled: string[] = [];
    let release!: () => void;
    const waiting = new Promise<void>((resolve) => {
      release = resolve;
    });
    const agent = {
      async *submit(_turn: unknown, generationId: string) {
        await waiting;
        yield { kind: "assistant_text", text: "late answer", generationId };
      },
      cancel(generationId: string) {
        cancelled.push(`agent:${generationId}`);
      },
    };
    const coordinator = new ConversationCoordinator({
      agent,
      session,
      spokenOutputPolicy: new SpokenOutputPolicy({ session }),
      sentenceSegmenter: new DeterministicSentenceSegmenter(),
      speechQueue: {
        enqueue() {},
        async finish() {},
        cancel(generationId) {
          cancelled.push(`speech:${generationId}`);
        },
      },
    });
    const result = coordinator.start(
      { agent: "toyota", text: "hello" },
      { agentName: "Toyota", speak: true },
    );
    await Promise.resolve();
    const generationId = session.currentGeneration;
    if (!generationId) throw new Error("expected an active generation");
    coordinator.interrupt();
    release();
    expect((await result).status).toBe("interrupted");
    expect(cancelled).toEqual([
      `agent:${generationId}`,
      `speech:${generationId}`,
    ]);
  });
});
