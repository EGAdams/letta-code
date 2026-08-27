import { describe, expect, test } from "bun:test";
import {
  AgentEventKind,
  isSpeakable,
  TurnCancelledError,
} from "../abstract/conversation-agent.interface.js";

/**
 * The shared IConversationAgent contract suite.
 *
 * The plan's Liskov requirement: a fake and a real adapter must be
 * indistinguishable to a caller. That is only true if the same tests run
 * against both, so this file holds the tests and each adapter's own test file
 * calls it. A new adapter (a local model, a different cloud agent) becomes
 * trustworthy by adding one line here, not by re-deriving what "correct" means.
 *
 * @param {string} name  what shows up in the test output
 * @param {(replyText: string) => import("../abstract/conversation-agent.interface.js").ConversationAgent} makeAgent
 *   build an agent that will answer any turn with `replyText`
 */
export function runConversationAgentContract(name, makeAgent) {
  const turn = { agent: "agent-1", text: "what did we spend in March?" };

  const drain = async (agent, generationId, before = null) => {
    const events = [];
    for await (const event of agent.submit(turn, generationId)) {
      events.push(event);
      if (before) await before(event);
    }
    return events;
  };

  describe(`IConversationAgent contract: ${name}`, () => {
    test("a turn ends with exactly one terminal event", async () => {
      const events = await drain(makeAgent("we spent $412"), "gen-1");
      const terminals = events.filter(
        (e) => e.kind === AgentEventKind.TERMINAL,
      );
      expect(terminals).toHaveLength(1);
      expect(events.at(-1).kind).toBe(AgentEventKind.TERMINAL);
    });

    test("every event carries the generation it was submitted with", async () => {
      const events = await drain(makeAgent("we spent $412"), "gen-7");
      expect(events.length).toBeGreaterThan(0);
      for (const event of events) expect(event.generationId).toBe("gen-7");
    });

    test("the answer arrives as speakable assistant text", async () => {
      const events = await drain(makeAgent("we spent $412"), "gen-1");
      const spoken = events.filter((e) => isSpeakable(e.kind));
      expect(spoken.map((e) => e.text)).toEqual(["we spent $412"]);
    });

    test("nothing but assistant text is speakable", async () => {
      const events = await drain(makeAgent("we spent $412"), "gen-1");
      for (const event of events) {
        if (event.kind !== AgentEventKind.ASSISTANT_TEXT) {
          expect(isSpeakable(event.kind)).toBe(false);
        }
      }
    });

    test("a cancelled turn delivers nothing", async () => {
      const agent = makeAgent("we spent $412");
      agent.cancel("gen-9");
      const events = [];
      let thrown = null;
      try {
        for await (const event of agent.submit(turn, "gen-9")) {
          events.push(event);
        }
      } catch (e) {
        thrown = e;
      }
      expect(thrown).toBeInstanceOf(TurnCancelledError);
      expect(thrown.generationId).toBe("gen-9");
      expect(events.filter((e) => isSpeakable(e.kind))).toHaveLength(0);
    });

    test("cancelling a generation that was never submitted is safe", () => {
      const agent = makeAgent("we spent $412");
      expect(() => agent.cancel("gen-never")).not.toThrow();
      expect(() => agent.cancel("gen-never")).not.toThrow();
    });
  });
}
