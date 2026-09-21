import { describe, expect, test } from "bun:test";
import { SequentialSpeechQueue } from "../src/sequential-speech-queue.ts";

describe("SequentialSpeechQueue", () => {
  test("waits for one sentence to finish before starting the next", async () => {
    const calls: string[] = [];
    const releases: Array<() => void> = [];
    const queue = new SequentialSpeechQueue({
      speech: {
        speak(text) {
          calls.push(text);
          let release!: () => void;
          const finished = new Promise<void>((resolve) => {
            release = resolve;
          });
          releases.push(release);
          return { pending: Promise.resolve({}), finished, cancel() {} };
        },
        cancel() {},
      },
    });
    queue.enqueue(
      { generationId: "gen-1", sequence: 0, text: "First.", final: false },
      "Toyota",
    );
    queue.enqueue(
      { generationId: "gen-1", sequence: 1, text: "Second.", final: true },
      "Toyota",
    );
    await Promise.resolve();
    expect(calls).toEqual(["First."]);
    releases[0]?.();
    await Bun.sleep(0);
    expect(calls).toEqual(["First.", "Second."]);
    releases[1]?.();
    await queue.finish("gen-1");
  });

  test("cancellation prevents later queued sentences from playing", async () => {
    const calls: string[] = [];
    let release!: () => void;
    let cancelCount = 0;
    const queue = new SequentialSpeechQueue({
      speech: {
        speak(text) {
          calls.push(text);
          return {
            pending: Promise.resolve({}),
            finished: new Promise<void>((resolve) => {
              release = resolve;
            }),
            cancel() {},
          };
        },
        cancel() {
          cancelCount += 1;
        },
      },
    });
    queue.enqueue(
      { generationId: "gen-1", sequence: 0, text: "First.", final: false },
      "Toyota",
    );
    queue.enqueue(
      { generationId: "gen-1", sequence: 1, text: "Late.", final: true },
      "Toyota",
    );
    await Promise.resolve();
    queue.cancel("gen-1");
    release();
    await Promise.resolve();
    await Promise.resolve();
    expect(calls).toEqual(["First."]);
    expect(cancelCount).toBe(1);
  });
});
