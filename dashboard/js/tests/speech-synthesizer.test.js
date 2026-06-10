import { describe, expect, test } from "bun:test";
import { SpeechSynthesizer } from "../abstract/speech-synthesizer.interface.js";

/** Fake SpeechSynthesis engine recording interactions. */
function fakeEngine(voices = []) {
  return {
    voices,
    spoken: [],
    cancels: 0,
    getVoices() {
      return this.voices;
    },
    speak(u) {
      this.spoken.push(u);
    },
    cancel() {
      this.cancels += 1;
    },
  };
}

describe("SpeechSynthesizer (Facade)", () => {
  test("unsupported when no engine injected", () => {
    const s = new SpeechSynthesizer(null);
    expect(s.supported).toBe(false);
    expect(s.speak("hi")).toBeNull();
    expect(() => s.cancel()).not.toThrow();
  });

  test("pickVoice prefers en-US natural/neural voices", () => {
    const engine = fakeEngine([
      { lang: "fr-FR", name: "Thomas" },
      { lang: "en-US", name: "Google US English Neural" },
      { lang: "en-US", name: "Plain" },
    ]);
    const s = new SpeechSynthesizer(engine);
    s.pickVoice();
    expect(s.voice.name).toBe("Google US English Neural");
  });

  test("speak cancels in-flight speech first, then speaks cleaned text", () => {
    const engine = fakeEngine([{ lang: "en-US", name: "Plain" }]);
    const s = new SpeechSynthesizer(engine);
    const u = s.speak("**Hello** world");
    expect(engine.cancels).toBe(1);
    expect(engine.spoken).toHaveLength(1);
    expect(u.text).toBe("Hello world");
    expect(u.voice.name).toBe("Plain");
    expect(u.rate).toBe(1.0);
  });

  test("speak with only-markdown text says nothing", () => {
    const engine = fakeEngine([]);
    const s = new SpeechSynthesizer(engine);
    expect(s.speak("**``##**")).toBeNull();
    expect(engine.spoken).toHaveLength(0);
  });

  test("cancel delegates to the engine", () => {
    const engine = fakeEngine();
    new SpeechSynthesizer(engine).cancel();
    expect(engine.cancels).toBe(1);
  });
});
