import { describe, expect, test } from "bun:test";
import {
  RecorderState,
  VoiceRecorder,
} from "../abstract/voice-recorder.interface.js";

/** Scripted recorder: controls openStream success + transcription result. */
class FakeRecorder extends VoiceRecorder {
  constructor({ canOpen = true, result = { ok: true }, ...opts } = {}) {
    super(opts);
    this.canOpen = canOpen;
    this.result = result;
    this.events = [];
  }
  async openStream() {
    this.events.push("open");
    return this.canOpen;
  }
  beginCapture() {
    this.events.push("begin");
  }
  async endCapture() {
    this.events.push("end");
    return { size: 10 };
  }
  async transcribe(blob) {
    this.events.push(`transcribe:${blob.size}`);
    return this.result;
  }
}

describe("VoiceRecorder (State machine)", () => {
  test("abstract primitives throw on the base", async () => {
    await expect(new VoiceRecorder().start()).rejects.toThrow(
      /openStream\(\) is abstract/,
    );
  });

  test("happy path idle -> recording -> processing -> idle", async () => {
    const states = [];
    const r = new FakeRecorder({ onStateChange: (s) => states.push(s) });
    expect(await r.start()).toBe(true);
    expect(r.state).toBe(RecorderState.RECORDING);
    const result = await r.stop();
    expect(result).toEqual({ ok: true });
    expect(r.state).toBe(RecorderState.IDLE);
    expect(states).toEqual([
      RecorderState.RECORDING,
      RecorderState.PROCESSING,
      RecorderState.IDLE,
    ]);
    expect(r.events).toEqual(["open", "begin", "end", "transcribe:10"]);
  });

  test("start is a no-op when mic cannot open", async () => {
    const r = new FakeRecorder({ canOpen: false });
    expect(await r.start()).toBe(false);
    expect(r.state).toBe(RecorderState.IDLE);
    expect(r.events).toEqual(["open"]); // never began capture
  });

  test("stop when not recording returns null", async () => {
    const r = new FakeRecorder();
    expect(await r.stop()).toBeNull();
  });

  test("returns to idle even if transcribe throws", async () => {
    class Boom extends FakeRecorder {
      async transcribe() {
        throw new Error("network");
      }
    }
    const r = new Boom();
    await r.start();
    await expect(r.stop()).rejects.toThrow("network");
    expect(r.state).toBe(RecorderState.IDLE);
  });

  test("toggle flips between start and stop", async () => {
    const r = new FakeRecorder();
    await r.toggle();
    expect(r.isRecording).toBe(true);
    await r.toggle();
    expect(r.isRecording).toBe(false);
  });
});
