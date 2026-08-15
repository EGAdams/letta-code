import { describe, expect, test } from "bun:test";

import {
  ClaudeAttemptCompletionObservedError,
  ClaudeAttemptTimeoutError,
  runWithAbortTimeout,
} from "./claude-attempt.ts";

describe("Trainer Claude attempt deadline", () => {
  test("returns the session result when it finishes in time", async () => {
    const result = await runWithAbortTimeout(
      async () => "PASS report written",
      5_000,
    );
    expect(result).toBe("PASS report written");
  });

  test("hands the run an AbortSignal (the only abort channel the SDK honours)", async () => {
    let seen: AbortSignal | undefined;
    await runWithAbortTimeout(async (signal) => {
      seen = signal;
      return "ok";
    }, 5_000);
    expect(seen).toBeInstanceOf(AbortSignal);
    expect(seen?.aborted).toBe(false);
  });

  // The regression: claude-code-sdk-ts@0.3.3 ignores .withTimeout(), so a stuck
  // `claude` child used to hang asText() forever — the watchdog loop never ran,
  // codex never took over, and no report was ever written.
  test("rejects with a timeout error when the session never settles", async () => {
    const started = Date.now();
    const never = () => new Promise<string>(() => {});
    const err = await runWithAbortTimeout(never, 50).catch((e) => e);
    expect(err).toBeInstanceOf(ClaudeAttemptTimeoutError);
    expect((err as ClaudeAttemptTimeoutError).timeoutMs).toBe(50);
    expect(Date.now() - started).toBeLessThan(2_000);
  });

  test("aborts the signal on timeout so the claude child is torn down", async () => {
    let seen: AbortSignal | undefined;
    await runWithAbortTimeout((signal) => {
      seen = signal;
      return new Promise<string>(() => {});
    }, 50).catch(() => {});
    expect(seen?.aborted).toBe(true);
  });

  test("a post-abort SDK rejection still surfaces as a timeout, not an AbortError", async () => {
    const err = await runWithAbortTimeout(
      (signal) =>
        new Promise<string>((_resolve, reject) => {
          signal.addEventListener("abort", () =>
            reject(new Error("AbortError")),
          );
        }),
      50,
    ).catch((e) => e);
    expect(err).toBeInstanceOf(ClaudeAttemptTimeoutError);
  });

  test("a real session failure propagates unchanged so codex fallback keeps its reason", async () => {
    const err = await runWithAbortTimeout(async () => {
      throw new Error("Credit balance is too low");
    }, 5_000).catch((e) => e);
    expect(err).toBeInstanceOf(Error);
    expect((err as Error).message).toBe("Credit balance is too low");
    expect(err).not.toBeInstanceOf(ClaudeAttemptTimeoutError);
  });

  test("a non-positive deadline means no deadline", async () => {
    expect(await runWithAbortTimeout(async () => "ok", 0)).toBe("ok");
  });
});

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
