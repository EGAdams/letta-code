import { describe, expect, test } from "bun:test";
import { AgentEventKind } from "../abstract/conversation-agent.interface.js";
import { FakeConversationAgent } from "../implementation/fake-conversation-agent.js";
import { runConversationAgentContract } from "./conversation-agent-contract.js";

runConversationAgentContract(
  "FakeConversationAgent",
  (replyText) =>
    new FakeConversationAgent({
      events: [{ kind: AgentEventKind.ASSISTANT_TEXT, text: replyText }],
    }),
);

describe("FakeConversationAgent", () => {
  test("scripts a whole turn, including unspeakable kinds", async () => {
    const agent = new FakeConversationAgent({
      events: [
        { kind: AgentEventKind.REASONING, text: "checking the ledger" },
        { kind: AgentEventKind.TOOL_CALL, text: "read_expenses", name: "read" },
        { kind: AgentEventKind.ASSISTANT_TEXT, text: "$412" },
      ],
    });
    const kinds = [];
    for await (const event of agent.submit(
      { agent: "a", text: "?" },
      "gen-1",
    )) {
      kinds.push(event.kind);
    }
    expect(kinds).toEqual([
      "reasoning",
      "tool_call",
      "assistant_text",
      "terminal",
    ]);
  });

  test("answers per turn when given a script function", async () => {
    const agent = new FakeConversationAgent({
      script: (turn) => [
        { kind: AgentEventKind.ASSISTANT_TEXT, text: `heard: ${turn.text}` },
      ],
    });
    const texts = [];
    for await (const e of agent.submit({ agent: "a", text: "hello" }, "g1")) {
      texts.push(e.text);
    }
    expect(texts[0]).toBe("heard: hello");
    expect(agent.submitted).toHaveLength(1);
    expect(agent.submitted[0].generationId).toBe("g1");
  });

  test("does not append a second terminal when the script has one", async () => {
    const agent = new FakeConversationAgent({
      events: [{ kind: AgentEventKind.TERMINAL }],
    });
    const events = [];
    for await (const e of agent.submit({ agent: "a", text: "?" }, "g1")) {
      events.push(e);
    }
    expect(events).toHaveLength(1);
  });

  test("drops malformed script entries exactly as a real adapter would", async () => {
    const agent = new FakeConversationAgent({
      events: [
        { kind: "not_a_kind", text: "junk" },
        { kind: AgentEventKind.ASSISTANT_TEXT, text: "   " },
        { kind: AgentEventKind.ASSISTANT_TEXT, text: "real" },
      ],
    });
    const texts = [];
    for await (const e of agent.submit({ agent: "a", text: "?" }, "g1")) {
      texts.push(e.text);
    }
    expect(texts).toEqual(["real", ""]);
  });

  test("cancelling mid-stream stops delivery at the next event", async () => {
    const agent = new FakeConversationAgent({
      events: [
        { kind: AgentEventKind.ASSISTANT_TEXT, text: "first" },
        { kind: AgentEventKind.ASSISTANT_TEXT, text: "second" },
      ],
    });
    const delivered = [];
    let thrown = null;
    try {
      for await (const e of agent.submit({ agent: "a", text: "?" }, "g1")) {
        delivered.push(e.text);
        agent.cancel("g1");
      }
    } catch (e) {
      thrown = e;
    }
    expect(delivered).toEqual(["first"]);
    expect(thrown?.name).toBe("TurnCancelledError");
    expect(agent.wasCancelled("g1")).toBe(true);
  });
});
