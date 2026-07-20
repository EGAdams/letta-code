import { describe, expect, test } from "bun:test";
import {
  ContinuousListener,
  ListenerState,
} from "../abstract/continuous-listener.interface.js";

/** Scripted listener: controls openListening success + emits scripted results. */
class FakeListener extends ContinuousListener {
  constructor({ canOpen = true, ...opts } = {}) {
    super(opts);
    this.canOpen = canOpen;
    this.events = [];
  }
  async openListening() {
    this.events.push("open");
    return this.canOpen;
  }
  closeListening() {
    this.events.push("close");
  }
  emit(text, isFinal) {
    this._emitResult(text, isFinal);
  }
}

describe("ContinuousListener (State machine)", () => {
  test("abstract primitives throw on the base", async () => {
    await expect(new ContinuousListener().start()).rejects.toThrow(
      /openListening\(\) is abstract/,
    );
  });

  test("happy path idle -> listening -> idle", async () => {
    const states = [];
    const l = new FakeListener({ onStateChange: (s) => states.push(s) });
    expect(await l.start()).toBe(true);
    expect(l.state).toBe(ListenerState.LISTENING);
    expect(l.isListening).toBe(true);
    l.stop();
    expect(l.state).toBe(ListenerState.IDLE);
    expect(states).toEqual([ListenerState.LISTENING, ListenerState.IDLE]);
    expect(l.events).toEqual(["open", "close"]);
  });

  test("start is a no-op when the session cannot open", async () => {
    const l = new FakeListener({ canOpen: false });
    expect(await l.start()).toBe(false);
    expect(l.state).toBe(ListenerState.IDLE);
  });

  test("start is a no-op when already listening", async () => {
    const l = new FakeListener();
    await l.start();
    expect(await l.start()).toBe(false);
    expect(l.events).toEqual(["open"]); // did not open twice
  });

  test("stop is a no-op when not listening", () => {
    const l = new FakeListener();
    l.stop();
    expect(l.events).toEqual([]);
  });

  test("toggle flips between start and stop", async () => {
    const l = new FakeListener();
    await l.toggle();
    expect(l.isListening).toBe(true);
    await l.toggle();
    expect(l.isListening).toBe(false);
  });

  test("onResult delivers interim and final chunks", async () => {
    const results = [];
    const l = new FakeListener({
      onResult: (text, isFinal) => results.push([text, isFinal]),
    });
    await l.start();
    l.emit("hello", false);
    l.emit("hello there", true);
    expect(results).toEqual([
      ["hello", false],
      ["hello there", true],
    ]);
  });

  test("setCallbacks re-binds without touching session state", async () => {
    const first = [];
    const second = [];
    const l = new FakeListener({ onResult: (t) => first.push(t) });
    await l.start();
    l.emit("a", true);
    l.setCallbacks({ onResult: (t) => second.push(t) });
    l.emit("b", true);
    expect(first).toEqual(["a"]);
    expect(second).toEqual(["b"]);
    expect(l.isListening).toBe(true); // session untouched by the rebind
  });
});
