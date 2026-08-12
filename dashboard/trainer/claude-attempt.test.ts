import { describe, expect, test } from "bun:test";
import {
  ClaudeAttemptCompletionObservedError,
  runWithAbortTimeout,
} from "./claude-attempt";

describe("runWithAbortTimeout completion observer", () => {
  test("aborts a model session as soon as its deliverable exists", async () => {
    let complete = false;
    let aborted = false;
    const run = (signal: AbortSignal) =>
      new Promise<string>(() => {
        signal.addEventListener("abort", () => {
          aborted = true;
        });
      });
    setTimeout(() => {
      complete = true;
    }, 10);

    await expect(
      runWithAbortTimeout(run, 5_000, () => complete),
    ).rejects.toBeInstanceOf(ClaudeAttemptCompletionObservedError);
    expect(aborted).toBe(true);
  });
});
