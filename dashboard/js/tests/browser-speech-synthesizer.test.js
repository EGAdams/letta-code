import { describe, expect, test } from "bun:test";
import { BrowserSpeechSynthesizer } from "../implementation/browser-speech-synthesizer.js";

function fakeWindow() {
  const spoken = [];
  let cancels = 0;
  class FakeUtterance {
    constructor(text) {
      this.text = text;
    }
  }
  return {
    spoken,
    get cancels() {
      return cancels;
    },
    speechSynthesis: {
      onvoiceschanged: null,
      getVoices: () => [{ lang: "en-US", name: "Google US English" }],
      speak: (u) => spoken.push(u),
      cancel: () => {
        cancels += 1;
      },
    },
    SpeechSynthesisUtterance: FakeUtterance,
  };
}

describe("BrowserSpeechSynthesizer (concrete SpeechSynthesizer)", () => {
  test("unsupported when the window has no speechSynthesis", () => {
    const s = new BrowserSpeechSynthesizer({});
    expect(s.supported).toBe(false);
    expect(s.speak("hi")).toBeNull();
  });

  test("wires the engine + utterance factory and cancels before speaking", () => {
    const win = fakeWindow();
    const s = new BrowserSpeechSynthesizer(win);
    const u = s.speak("**Hello** there");
    expect(win.cancels).toBe(1); // cancel-before-speak policy
    expect(win.spoken.length).toBe(1);
    expect(u.text).toBe("Hello there"); // markdown stripped by base clean()
    expect(s.voice.name).toBe("Google US English");
  });

  test("bindVoiceChanges picks a voice and registers the callback", () => {
    const win = fakeWindow();
    const s = new BrowserSpeechSynthesizer(win);
    s.bindVoiceChanges();
    expect(s.voice).not.toBeNull();
    expect(typeof win.speechSynthesis.onvoiceschanged).toBe("function");
  });
});
