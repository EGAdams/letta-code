import { describe, expect, test } from "bun:test";
import type { Line } from "../../cli/helpers/accumulator";
import { selectUserVisibleResultText } from "../../headless";

describe("headless result selection", () => {
  test("does not expose reasoning-only output as a final result", () => {
    const lines: Line[] = [
      {
        kind: "reasoning",
        id: "reasoning-1",
        text: "I should search the web before answering.",
        phase: "finished",
      },
    ];

    expect(selectUserVisibleResultText(lines, "")).toBe("");
    expect(
      selectUserVisibleResultText(lines, "No assistant response found"),
    ).toBe("No assistant response found");
  });

  test("prefers assistant text over tool results", () => {
    const lines: Line[] = [
      {
        kind: "tool_call",
        id: "tool-1",
        toolCallId: "call-1",
        name: "web_search_exa",
        resultText: "tool result",
        resultOk: true,
        phase: "finished",
      },
      {
        kind: "assistant",
        id: "assistant-1",
        text: "final assistant answer",
        phase: "finished",
      },
    ];

    expect(selectUserVisibleResultText(lines, "fallback")).toBe(
      "final assistant answer",
    );
  });

  test("uses tool result when no assistant text exists", () => {
    const lines: Line[] = [
      {
        kind: "reasoning",
        id: "reasoning-1",
        text: "I should call a tool.",
        phase: "finished",
      },
      {
        kind: "tool_call",
        id: "tool-1",
        toolCallId: "call-1",
        name: "send_message_to_agent_and_wait_for_reply",
        resultText: "Hailey replied with the answer.",
        resultOk: true,
        phase: "finished",
      },
    ];

    expect(selectUserVisibleResultText(lines, "fallback")).toBe(
      "Hailey replied with the answer.",
    );
  });
});
