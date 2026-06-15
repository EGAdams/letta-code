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

  test("pickVoice prefers a female voice over a male natural/neural voice", () => {
    const engine = fakeEngine([
      { lang: "en-US", name: "Microsoft Guy Online (Natural)" },
      { lang: "en-US", name: "Microsoft Zira" },
    ]);
    const s = new SpeechSynthesizer(engine);
    s.pickVoice();
    expect(s.voice.name).toBe("Microsoft Zira");
  });

  test("pickVoice avoids an identifiably-male voice when no female exists", () => {
    const engine = fakeEngine([
      { lang: "en-US", name: "Microsoft David" },
      { lang: "en-US", name: "Microsoft Plain" },
    ]);
    const s = new SpeechSynthesizer(engine);
    s.pickVoice();
    // No female voice available, so it skips the male "David" for the neutral one.
    expect(s.voice.name).toBe("Microsoft Plain");
  });

  test("refreshVoices re-picks and clears per-agent assignments", () => {
    const engine = fakeEngine([
      { lang: "en-US", name: "Microsoft Zira" },
      { lang: "en-US", name: "Microsoft Aria" },
    ]);
    const s = new SpeechSynthesizer(engine);
    s.speak("hi", "Scissari");
    s.refreshVoices();
    expect(s.voice).not.toBeNull();
    // After a reset Scissari re-derives its preferred voice cleanly.
    expect(s.speak("hi", "Scissari").voice.name).toBe("Microsoft Zira");
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

  test("speak with an agentName uses that agent's catalog voice", () => {
    const engine = fakeEngine([
      { lang: "en-US", name: "Microsoft Zira" },
      { lang: "en-US", name: "Microsoft Aria" },
    ]);
    const s = new SpeechSynthesizer(engine);
    const scissari = s.speak("hi", "Scissari");
    const mazda = s.speak("hi", "Mazda");
    expect(scissari.voice.name).toBe("Microsoft Zira");
    expect(mazda.voice.name).toBe("Microsoft Aria");
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
