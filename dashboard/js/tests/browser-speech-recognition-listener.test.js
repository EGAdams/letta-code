import { describe, expect, test } from "bun:test";
import { ListenerState } from "../abstract/continuous-listener.interface.js";
import { BrowserSpeechRecognitionListener } from "../implementation/browser-speech-recognition-listener.js";

/** Minimal SpeechRecognition stand-in driven synchronously/manually. */
class FakeSpeechRecognition {
  constructor() {
    this.continuous = false;
    this.interimResults = false;
    this.lang = "";
    this.onresult = null;
    this.onend = null;
    this.started = 0;
    this.stopped = 0;
  }
  start() {
    this.started += 1;
  }
  stop() {
    this.stopped += 1;
    if (this.onend) this.onend();
  }
  /** Test helper: simulate a browser result event. */
  fire(results, resultIndex = 0) {
    if (this.onresult) {
      this.onresult({
        resultIndex,
        results: results.map((r) =>
          Object.assign([{ transcript: r.text }], { isFinal: r.isFinal }),
        ),
      });
    }
  }
}

function makeListener(opts = {}) {
  return new BrowserSpeechRecognitionListener({
    window: {},
    SpeechRecognition: FakeSpeechRecognition,
    ...opts,
  });
}

describe("BrowserSpeechRecognitionListener (concrete ContinuousListener)", () => {
  test("supported is false without a SpeechRecognition constructor", () => {
    const l = new BrowserSpeechRecognitionListener({
      window: {},
      SpeechRecognition: undefined,
    });
    expect(l.supported).toBe(false);
  });

  test("start opens a continuous, interim-enabled session", async () => {
    const l = makeListener();
    expect(await l.start()).toBe(true);
    expect(l.state).toBe(ListenerState.LISTENING);
    expect(l._recognition.continuous).toBe(true);
    expect(l._recognition.interimResults).toBe(true);
    expect(l._recognition.started).toBe(1);
  });

  test("start returns false when unsupported", async () => {
    const l = new BrowserSpeechRecognitionListener({
      window: {},
      SpeechRecognition: undefined,
    });
    expect(await l.start()).toBe(false);
    expect(l.state).toBe(ListenerState.IDLE);
  });

  test("onresult forwards interim and final chunks with isFinal", async () => {
    const results = [];
    const l = makeListener({ onResult: (t, f) => results.push([t, f]) });
    await l.start();
    l._recognition.fire([{ text: "hey there", isFinal: false }]);
    l._recognition.fire([{ text: "hey there Suzuki", isFinal: true }]);
    expect(results).toEqual([
      ["hey there", false],
      ["hey there Suzuki", true],
    ]);
  });

  test("auto-restarts on native onend while still meant to be listening", async () => {
    const l = makeListener();
    await l.start();
    const recognition = l._recognition;
    recognition.onend(); // browser silence timeout, NOT our stop()
    expect(recognition.started).toBe(2); // restarted
    expect(l.state).toBe(ListenerState.LISTENING); // our state is unaffected
  });

  test("stop() does not auto-restart", async () => {
    const l = makeListener();
    await l.start();
    const recognition = l._recognition;
    l.stop();
    expect(recognition.stopped).toBe(1);
    expect(recognition.started).toBe(1); // no restart after a real stop
    expect(l.state).toBe(ListenerState.IDLE);
  });
});
