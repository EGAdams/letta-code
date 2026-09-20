import { describe, expect, test } from "bun:test";
import { SessionState, VoiceSession } from "../src/voice-session.ts";

function speaking() {
  const session = new VoiceSession();
  session.startListening();
  const generation = session.beginTurn();
  session.beginSpeaking(generation);
  let cancels = 0;
  const playback = {
    cancel: () => {
      cancels += 1;
    },
  };
  expect(session.trackPlayback(generation, playback)).toBe(true);
  return {
    session,
    generation,
    get cancels() {
      return cancels;
    },
  };
}

describe("VoiceSession playback ownership", () => {
  test("close cancels active speech once and rejects its old generation", () => {
    const ctx = speaking();
    ctx.session.close();
    ctx.session.close();
    expect(ctx.cancels).toBe(1);
    expect(ctx.session.state).toBe(SessionState.CLOSED);
    expect(ctx.session.accepts(ctx.generation)).toBe(false);
  });

  test("a new listening turn stops the old speech before accepting new output", () => {
    const ctx = speaking();
    ctx.session.startListening();
    const next = ctx.session.beginTurn();
    expect(ctx.cancels).toBe(1);
    expect(ctx.session.accepts(ctx.generation)).toBe(false);
    expect(ctx.session.accepts(next)).toBe(true);
  });

  test("normal completion releases the handle without cancelling it", () => {
    const ctx = speaking();
    expect(ctx.session.completeTurn(ctx.generation)).toBe(true);
    expect(ctx.cancels).toBe(0);
    expect(ctx.session.state).toBe(SessionState.LISTENING);
    expect(ctx.session.trackPlayback(ctx.generation, { cancel() {} })).toBe(
      false,
    );
  });

  test("a stale or non-speaking generation cannot claim playback", () => {
    const session = new VoiceSession();
    session.startListening();
    const generation = session.beginTurn();
    expect(session.trackPlayback(generation, { cancel() {} })).toBe(false);
    expect(session.beginSpeaking(generation)).toBe(true);
    expect(session.trackPlayback("wrong", { cancel() {} })).toBe(false);
  });
});
