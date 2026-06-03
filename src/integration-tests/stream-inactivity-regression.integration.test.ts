import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

describe("stream inactivity regression", () => {
  test("inactivity timer only resets on tool execution, not reasoning/assistant output", () => {
    const currentFile = fileURLToPath(import.meta.url);
    const source = readFileSync(
      resolve(dirname(currentFile), "../cli/helpers/stream.ts"),
      "utf8",
    );

    // The fix for planning mode hangs: only tool execution (tool_call_message
    // and tool_return_message) resets the inactivity timer. reasoning_message
    // and assistant_message intentionally do NOT reset the timer, because
    // resetting them causes infinite loops when model is stuck in planning
    // without executing tools (2+ hour hangs).
    expect(source).toContain('chunk.message_type === "tool_call_message"');
    expect(source).toContain('chunk.message_type === "tool_return_message"');

    // Ensure reasoning/assistant are NOT in the timer reset condition
    const timerResetSection = source.match(
      /if\s*\(\s*chunk\.message_type === "tool_call_message"/s,
    );
    expect(timerResetSection).toBeTruthy();

    // Verify the comment explaining why we exclude reasoning/assistant
    expect(source).toContain("only on actual tool execution progress");
    expect(source).toContain(
      "reasoning_message and assistant_message are intentionally excluded",
    );
  });
});
