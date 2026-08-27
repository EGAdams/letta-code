import { describe, expect, test } from "bun:test";
import {
  AgentEventKind,
  agentEvent,
  parseAgentEvent,
} from "../abstract/conversation-agent.interface.js";
import { SequentialIdSource } from "../abstract/session-clock.js";
import {
  RejectionReason,
  SpokenOutputPolicy,
} from "../abstract/spoken-output-policy.js";
import { VoiceSession } from "../abstract/voice-session.js";

function build() {
  const session = new VoiceSession({ idSource: new SequentialIdSource() });
  session.startListening();
  const generation = session.beginTurn();
  return { session, generation, policy: new SpokenOutputPolicy({ session }) };
}

describe("SpokenOutputPolicy", () => {
  test("speaks current assistant text", () => {
    const { policy, generation } = build();
    const verdict = policy.admit(
      agentEvent(
        AgentEventKind.ASSISTANT_TEXT,
        "  we spent $412  ",
        generation,
      ),
    );
    expect(verdict.speak).toBe(true);
    expect(verdict.text).toBe("we spent $412");
  });

  test("never speaks reasoning, tool calls, tool results or status", () => {
    const { policy, generation } = build();
    for (const kind of [
      AgentEventKind.REASONING,
      AgentEventKind.TOOL_CALL,
      AgentEventKind.TOOL_RESULT,
      AgentEventKind.STATUS,
      AgentEventKind.TERMINAL,
    ]) {
      const verdict = policy.admit(
        agentEvent(kind, "internal chatter", generation),
      );
      expect(verdict.speak).toBe(false);
      expect(verdict.reason).toBe(RejectionReason.NOT_SPEAKABLE);
    }
  });

  test("discards the answer to a question the user moved on from", () => {
    const { session, policy, generation: march } = build();
    const marchAnswer = agentEvent(
      AgentEventKind.ASSISTANT_TEXT,
      "in March you spent $412",
      march,
    );
    session.startListening();
    const april = session.beginTurn();

    expect(policy.admit(marchAnswer).speak).toBe(false);
    expect(policy.admit(marchAnswer).reason).toBe(RejectionReason.SUPERSEDED);
    expect(
      policy.admit(
        agentEvent(AgentEventKind.ASSISTANT_TEXT, "in April, $88", april),
      ).speak,
    ).toBe(true);
  });

  test("a stale event is reported as stale, not as empty", () => {
    const { session, policy, generation } = build();
    const blankAndStale = {
      kind: AgentEventKind.ASSISTANT_TEXT,
      text: "   ",
      generationId: generation,
    };
    session.interrupt();
    expect(policy.admit(blankAndStale).reason).toBe(RejectionReason.SUPERSEDED);
  });

  test("rejects non-events instead of throwing", () => {
    const { policy } = build();
    for (const junk of [null, undefined, "text", 42]) {
      expect(policy.admit(junk).speak).toBe(false);
    }
    expect(policy.admit(null).reason).toBe(RejectionReason.NOT_AN_EVENT);
  });

  test("admitAll keeps order and drops everything unspeakable", () => {
    const { policy, generation } = build();
    const spoken = policy.admitAll([
      agentEvent(AgentEventKind.REASONING, "let me check", generation),
      agentEvent(AgentEventKind.ASSISTANT_TEXT, "first", generation),
      agentEvent(AgentEventKind.TOOL_CALL, "grep", generation),
      agentEvent(AgentEventKind.ASSISTANT_TEXT, "second", generation),
      agentEvent(AgentEventKind.TERMINAL, "", generation),
    ]);
    expect(spoken).toEqual(["first", "second"]);
  });

  test("isTerminal names the end of the stream", () => {
    const { generation } = build();
    expect(
      SpokenOutputPolicy.isTerminal(
        agentEvent(AgentEventKind.TERMINAL, "", generation),
      ),
    ).toBe(true);
    expect(SpokenOutputPolicy.isTerminal(null)).toBe(false);
  });
});

describe("parseAgentEvent — untrusted adapter output", () => {
  test("drops unknown kinds rather than guessing", () => {
    expect(
      parseAgentEvent({ kind: "whatever", text: "hi" }, "gen-1"),
    ).toBeNull();
    expect(parseAgentEvent(null, "gen-1")).toBeNull();
    expect(parseAgentEvent({ kind: "status" }, "")).toBeNull();
  });

  test("drops blank assistant text — a spoken blank is worse than silence", () => {
    expect(
      parseAgentEvent({ kind: "assistant_text", text: "   " }, "gen-1"),
    ).toBeNull();
    expect(parseAgentEvent({ kind: "status", text: "" }, "gen-1")).toEqual({
      kind: "status",
      text: "",
      generationId: "gen-1",
    });
  });

  test("carries tool names and adapter detail through untouched", () => {
    const event = parseAgentEvent(
      {
        kind: "tool_result",
        text: "3 files",
        name: "grep",
        detail: { exit: 0 },
      },
      "gen-1",
    );
    expect(event.name).toBe("grep");
    expect(event.detail).toEqual({ exit: 0 });
  });
});
