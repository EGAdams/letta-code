/**
 * Regression test for the false-positive inactivity abort seen with Mazda:
 *
 *   ✻ Thinking… (long multi-step design reasoning, no tools yet)
 *   ● Patch(…)  ⎿ Interrupted by user
 *   ⚠ Stopped after 90 seconds without tool progress.
 *
 * The watchdog used to reset only on tool_call_message / tool_return_message,
 * so a model that was visibly streaming reasoning for more than 90s — normal
 * for a large refactor plan — had its run cancelled mid-thought.
 *
 * Continuous reasoning must keep a run alive; a silent stream and a model that
 * never reaches a tool must still be cancelled. All three are pinned here,
 * through drainStream itself, with the clock and poll timer injected.
 */
import { describe, expect, test } from "bun:test";
import type { Stream } from "@letta-ai/letta-client/core/streaming";
import type { LettaStreamingResponse } from "@letta-ai/letta-client/resources/agents/messages";
import { createBuffers } from "../../cli/helpers/accumulator";
import { drainStream } from "../../cli/helpers/stream";
import {
  ProgressWatchdog,
  DEFAULT_INACTIVITY_THRESHOLDS as T,
} from "../../cli/helpers/stream-activity";
import { FakeClock, ManualTicker } from "./stream-activity/fakes";

function reasoningChunk(step: number): LettaStreamingResponse {
  return {
    id: `msg-reasoning-${step}`,
    message_type: "reasoning_message",
    reasoning: `Designing modular service extraction (step ${step})`,
  } as unknown as LettaStreamingResponse;
}

function toolCallChunk(): LettaStreamingResponse {
  return {
    id: "msg-tool-1",
    message_type: "tool_call_message",
    tool_call: {
      name: "Patch",
      arguments: '{"file_path":"supporting_document_service.py"}',
      tool_call_id: "call-1",
    },
  } as unknown as LettaStreamingResponse;
}

function stopChunk(reason: string): LettaStreamingResponse {
  return {
    message_type: "stop_reason",
    stop_reason: reason,
  } as unknown as LettaStreamingResponse;
}

/**
 * Minimal stand-in for the SDK stream: exposes `controller` (which drainStream
 * aborts) and throws on the next pull once aborted, like the real SDK does.
 */
function fakeStream(
  chunks: () => AsyncGenerator<LettaStreamingResponse>,
): Stream<LettaStreamingResponse> & { controller: AbortController } {
  const controller = new AbortController();
  const stream = {
    controller,
    async *[Symbol.asyncIterator]() {
      for await (const chunk of chunks()) {
        if (controller.signal.aborted) {
          throw new Error("The operation was aborted.");
        }
        yield chunk;
      }
    },
  };
  return stream as unknown as Stream<LettaStreamingResponse> & {
    controller: AbortController;
  };
}

/**
 * Drives drainStream with a hand-cranked clock, so a 10-minute scenario runs
 * in milliseconds and asserts on the real policy rather than a stub of it.
 */
function harness() {
  const clock = new FakeClock();
  const ticker = new ManualTicker();
  const watchdog = new ProgressWatchdog({ clock, ticker, thresholds: T });

  /** Move time forward and let the watchdog poll, as the real timer would. */
  const advance = (ms: number) => {
    clock.advance(ms);
    ticker.tick();
  };

  const drain = (stream: Stream<LettaStreamingResponse>) =>
    drainStream(
      stream,
      createBuffers("agent-test"),
      () => {},
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      { watchdog },
    );

  return { advance, drain };
}

describe("drainStream inactivity watchdog", () => {
  test("does not cancel a run that is continuously streaming reasoning", async () => {
    const { advance, drain } = harness();
    // 6 reasoning chunks, 30s apart => 180s of visible model progress before
    // the first tool call. Nothing is stuck; the model is thinking.
    const stream = fakeStream(async function* () {
      for (let step = 0; step < 6; step++) {
        yield reasoningChunk(step);
        advance(30_000);
      }
      yield toolCallChunk();
      yield stopChunk("end_turn");
    });

    const result = await drain(stream);

    expect(result.inactivityTimedOut).toBe(false);
    expect(result.inactivityReason).toBeUndefined();
    expect(result.stopReason).toBe("end_turn");
    expect(stream.controller.signal.aborted).toBe(false);
  });

  test("still cancels a stream that goes silent past the threshold", async () => {
    const { advance, drain } = harness();
    const stream = fakeStream(async function* () {
      advance(T.noContentMs + 1000); // no chunk has ever arrived
      yield reasoningChunk(0);
      yield stopChunk("end_turn");
    });

    const result = await drain(stream);

    expect(result.inactivityTimedOut).toBe(true);
    expect(result.inactivityReason).toBe("no_content");
    expect(result.stopReason).toBe("cancelled");
  });

  test("still cancels when reasoning stops mid-run and nothing follows", async () => {
    const { advance, drain } = harness();
    const stream = fakeStream(async function* () {
      yield reasoningChunk(0);
      advance(30_000);
      yield reasoningChunk(1);
      advance(T.noContentMs + 1000); // model went quiet after its last thought
      yield reasoningChunk(2);
      yield stopChunk("end_turn");
    });

    const result = await drain(stream);

    expect(result.inactivityTimedOut).toBe(true);
    expect(result.inactivityReason).toBe("no_content");
    expect(result.stopReason).toBe("cancelled");
  });

  test("cancels a model that reasons forever without ever running a tool", async () => {
    const { advance, drain } = harness();
    // The 2hr-hang case the watchdog was originally built for: steady
    // reasoning, no tool call, ever.
    const stream = fakeStream(async function* () {
      for (let step = 0; step < 60; step++) {
        yield reasoningChunk(step);
        advance(30_000);
      }
      yield stopChunk("end_turn");
    });

    const result = await drain(stream);

    expect(result.inactivityTimedOut).toBe(true);
    expect(result.inactivityReason).toBe("no_tool_progress");
    expect(result.stopReason).toBe("cancelled");
  });
});
