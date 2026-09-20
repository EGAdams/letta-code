import { describe, expect, test } from "bun:test";
import {
  AgentEventKind,
  TurnCancelledError,
} from "../../../abstract/conversation-agent.interface.js";
import { TestChatAgentAdapter } from "../../../implementation/test-chat-agent-adapter.js";
import { runConversationAgentContract } from "../../../tests/conversation-agent-contract.js";

const turn = { agent: "agent-scissari", text: "hello" };

async function eventsFor(reply: unknown) {
  const agent = new TestChatAgentAdapter({
    http: { postJSON: async () => reply },
  });
  const events = [];
  for await (const event of agent.submit(turn, "gen-1")) events.push(event);
  return events;
}

runConversationAgentContract(
  "legacy chat test endpoint",
  (replyText: string) =>
    new TestChatAgentAdapter({
      http: {
        postJSON: async () => ({
          replies: [{ type: "assistant_message", text: replyText }],
        }),
      },
    }),
);

describe("TestChatAgentAdapter", () => {
  test("preserves /api/test request and maps only public text to speech", async () => {
    const calls: unknown[] = [];
    const agent = new TestChatAgentAdapter({
      http: {
        postJSON: async (...args: unknown[]) => {
          calls.push(args);
          return {
            replies: [
              { type: "reasoning_message", text: "private thought" },
              { type: "tool_call_message", text: "secret args" },
              { type: "tool_return_message", text: "tool output" },
              { type: "assistant_message", text: "Hello there" },
            ],
          };
        },
      },
    });
    const events = [];
    for await (const event of agent.submit(turn, "gen-2")) events.push(event);
    expect(calls).toEqual([["/api/test", turn]]);
    expect(events.map((event) => event.kind)).toEqual([
      AgentEventKind.REASONING,
      AgentEventKind.TOOL_CALL,
      AgentEventKind.TOOL_RESULT,
      AgentEventKind.ASSISTANT_TEXT,
      AgentEventKind.TERMINAL,
    ]);
    expect(events[3].text).toBe("Hello there");
  });

  test("unknown and malformed rows fail closed", async () => {
    const events = await eventsFor({
      replies: [
        { type: "mystery", text: "never speak" },
        { type: "assistant_message", text: { nested: "bad" } },
        null,
        { type: "error", text: "unavailable" },
      ],
    });
    expect(events.map((event) => event.kind)).toEqual([
      AgentEventKind.STATUS,
      AgentEventKind.TERMINAL,
    ]);
    expect(events[0].detail?.replyType).toBe("error");
  });

  test("a malformed response rejects the turn instead of guessing an answer", async () => {
    const agent = new TestChatAgentAdapter({
      http: { postJSON: async () => ({ replies: "not an array" }) },
    });
    const next = agent.submit(turn, "gen-invalid").next();
    expect(next).rejects.toThrow("Chat returned invalid replies.");
  });

  test("cancelled in-flight response yields no late event", async () => {
    let release!: (value: unknown) => void;
    const response = new Promise((resolve) => {
      release = resolve;
    });
    const agent = new TestChatAgentAdapter({
      http: { postJSON: () => response },
    });
    const next = agent.submit(turn, "gen-late").next();
    agent.cancel("gen-late");
    release({ replies: [{ type: "assistant_message", text: "late" }] });
    expect(next).rejects.toBeInstanceOf(TurnCancelledError);
  });
});
