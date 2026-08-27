import { describe, expect, test } from "bun:test";
import { ManualClock, SequentialIdSource } from "../abstract/session-clock.js";
import {
  IllegalTransitionError,
  SessionState,
  VoiceSession,
} from "../abstract/voice-session.js";

function build({ onStateChange } = {}) {
  const clock = new ManualClock(1000);
  const session = new VoiceSession({
    clock,
    idSource: new SequentialIdSource(),
    onStateChange,
  });
  return { session, clock };
}

describe("VoiceSession — generation fencing", () => {
  test("output from a superseded generation is rejected", () => {
    // The headline case from the plan: EG asks about March, changes to April
    // mid-flight, and the slow March answer must not be spoken.
    const { session } = build();
    session.startListening();
    const march = session.beginTurn();
    expect(session.accepts(march)).toBe(true);

    session.startListening();
    const april = session.beginTurn();

    expect(session.accepts(april)).toBe(true);
    expect(session.accepts(march)).toBe(false);
  });

  test("interrupting makes the live turn stale immediately", () => {
    const { session } = build();
    session.startListening();
    const gen = session.beginTurn();
    session.beginSpeaking(gen);

    expect(session.interrupt()).toBe(gen);
    expect(session.state).toBe(SessionState.INTERRUPTED);
    expect(session.currentGeneration).toBeNull();
    expect(session.accepts(gen)).toBe(false);
  });

  test("accepts() fails closed on ids it never issued", () => {
    const { session } = build();
    session.startListening();
    session.beginTurn();
    expect(session.accepts("gen-from-another-session")).toBe(false);
    expect(session.accepts(null)).toBe(false);
    expect(session.accepts("")).toBe(false);
    expect(session.accepts(undefined)).toBe(false);
  });

  test("a closed session accepts nothing, including its own live turn", () => {
    const { session } = build();
    session.startListening();
    const gen = session.beginTurn();
    session.close();
    expect(session.accepts(gen)).toBe(false);
    expect(session.issued(gen)).toBe(true);
  });

  test("completing a turn retires its generation", () => {
    const { session } = build();
    session.startListening();
    const gen = session.beginTurn();
    expect(session.completeTurn(gen)).toBe(true);
    expect(session.state).toBe(SessionState.LISTENING);
    expect(session.accepts(gen)).toBe(false);
    // Completing it twice is a no-op, not a second transition.
    expect(session.completeTurn(gen)).toBe(false);
  });

  test("a superseded generation cannot start speaking", () => {
    const { session } = build();
    session.startListening();
    const stale = session.beginTurn();
    session.startListening();
    session.beginTurn();
    expect(session.beginSpeaking(stale)).toBe(false);
    expect(session.state).toBe(SessionState.THINKING);
  });
});

describe("VoiceSession — transition legality", () => {
  test("speaking -> interrupted is legal", () => {
    const { session } = build();
    session.startListening();
    const gen = session.beginTurn();
    session.beginSpeaking(gen);
    expect(() => session.interrupt()).not.toThrow();
  });

  test("closed -> listening is not", () => {
    const { session } = build();
    session.close();
    expect(() => session.startListening()).toThrow(IllegalTransitionError);
    expect(session.state).toBe(SessionState.CLOSED);
  });

  test("a turn cannot begin before the session is listening", () => {
    const { session } = build();
    expect(() => session.beginTurn()).toThrow(IllegalTransitionError);
  });

  test("an idle session has nothing to interrupt", () => {
    const { session } = build();
    expect(() => session.interrupt()).toThrow(IllegalTransitionError);
  });

  test("close() is legal from any state and is idempotent", () => {
    for (const reach of [
      (s) => s,
      (s) => {
        s.startListening();
        return s;
      },
      (s) => {
        s.startListening();
        s.beginTurn();
        return s;
      },
    ]) {
      const { session } = build();
      reach(session);
      session.close();
      session.close();
      expect(session.state).toBe(SessionState.CLOSED);
    }
  });
});

describe("VoiceSession — identity and observation", () => {
  test("ids come from the injected source, so tests can name them", () => {
    const { session } = build();
    expect(session.id).toBe("session-1");
    session.startListening();
    expect(session.beginTurn()).toBe("gen-2");
  });

  test("state changes are reported with the clock's time", () => {
    const seen = [];
    const { session, clock } = build({
      onStateChange: (change) => seen.push(change),
    });
    session.startListening();
    clock.advance(250);
    const gen = session.beginTurn();

    expect(seen.map((c) => `${c.from}->${c.to}`)).toEqual([
      "idle->listening",
      "listening->thinking",
    ]);
    expect(seen[0].at).toBe(1000);
    expect(seen[1].at).toBe(1250);
    // The generation is minted after the transition lands, so the change that
    // announced "thinking" does not yet name it.
    expect(seen[1].generation).toBeNull();
    expect(session.currentGeneration).toBe(gen);
  });
});
