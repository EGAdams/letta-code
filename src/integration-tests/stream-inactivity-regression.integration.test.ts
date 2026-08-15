import { describe, expect, test } from "bun:test";
import {
  classifyStreamActivity,
  DEFAULT_INACTIVITY_THRESHOLDS,
  evaluateInactivity,
} from "../cli/helpers/stream-activity";

const T = DEFAULT_INACTIVITY_THRESHOLDS;

/**
 * Both hangs this policy exists to prevent, asserted against the real module.
 *
 * This used to grep stream.ts for a literal `if (chunk.message_type === ...)`.
 * That assertion broke the moment the policy was extracted into
 * ./stream-activity — it was testing where the code lived, not what it does,
 * so it failed while the behavior it guarded was perfectly intact. The rules
 * below are the actual contract.
 */
describe("stream inactivity regression", () => {
  test("planning loops: reasoning alone never clears the tool-progress deadline", () => {
    // The original hang — the model reasons for hours without calling a tool.
    // Only real tool execution counts as progress against the long deadline.
    expect(classifyStreamActivity("reasoning_message")).toBe("content");
    expect(classifyStreamActivity("assistant_message")).toBe("content");

    const now = T.noToolProgressMs + 2;
    expect(
      evaluateInactivity(
        now,
        {
          lastContentMs: now - 1000, // still reasoning right up to now
          lastToolProgressMs: 0, // but no tool has ever run
          toolInFlight: false,
        },
        T,
      ),
    ).toBe("no_tool_progress");
  });

  test("slow tools: silence during a tool call is not a dead stream", () => {
    // The Mazda hang — run_claude_code_sdk executes remotely for minutes and
    // emits nothing. The short deadline must stay suspended until it returns.
    expect(classifyStreamActivity("tool_call_message")).toBe("tool_started");
    expect(classifyStreamActivity("tool_return_message")).toBe("tool_finished");

    const now = T.noContentMs * 3;
    expect(
      evaluateInactivity(
        now,
        { lastContentMs: 0, lastToolProgressMs: 0, toolInFlight: true },
        T,
      ),
    ).not.toBe("no_content");
  });
});
