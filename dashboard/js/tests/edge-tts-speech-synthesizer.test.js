import { describe, expect, test } from "bun:test";
import { EdgeTtsSpeechSynthesizer } from "../implementation/edge-tts-speech-synthesizer.js";

function fakeAudioFactory() {
  const created = [];
  const factory = (url) => {
    const audio = {
      url,
      played: 0,
      paused: 0,
      onended: null,
      play() {
        this.played += 1;
        return Promise.resolve();
      },
      pause() {
        this.paused += 1;
      },
    };
    created.push(audio);
    return audio;
  };
  return { created, factory };
}

function okAudioResponse() {
  return {
    ok: true,
    status: 200,
    headers: { get: () => "audio/mpeg" },
    blob: () => Promise.resolve(new Blob([new Uint8Array([1, 2, 3])])),
  };
}

function fakeSpeechWindow() {
  const spoken = [];
  class FakeUtterance {
    constructor(text) {
      this.text = text;
    }
  }
  return {
    spoken,
    speechSynthesis: {
      onvoiceschanged: null,
      getVoices: () => [{ lang: "en-US", name: "Google US English" }],
      speak: (u) => spoken.push(u),
      cancel: () => {},
    },
    SpeechSynthesisUtterance: FakeUtterance,
  };
}

describe("EdgeTtsSpeechSynthesizer", () => {
  test("supported via server tts even without Web Speech", () => {
    const { factory } = fakeAudioFactory();
    const s = new EdgeTtsSpeechSynthesizer(
      {},
      { fetchFn: async () => okAudioResponse(), audioFactory: factory },
    );
    expect(s.supported).toBe(true);
  });

  test("unsupported with neither server tts nor Web Speech", () => {
    const s = new EdgeTtsSpeechSynthesizer({});
    expect(s.supported).toBe(false);
    expect(s.speak("hi")).toBeNull();
  });

  test("POSTs cleaned text to /api/tts and plays the returned audio", async () => {
    const calls = [];
    const { created, factory } = fakeAudioFactory();
    const s = new EdgeTtsSpeechSynthesizer(
      {},
      {
        fetchFn: async (url, opts) => {
          calls.push({ url, opts });
          return okAudioResponse();
        },
        audioFactory: factory,
      },
    );
    const token = s.speak("**Hello** there", "Frita");
    expect(token.text).toBe("Hello there"); // markdown stripped
    expect(await token.pending).toBe("edge-tts");
    expect(calls.length).toBe(1);
    expect(calls[0].url).toBe("/api/tts");
    expect(JSON.parse(calls[0].opts.body)).toEqual({ text: "Hello there" });
    expect(created.length).toBe(1);
    expect(created[0].played).toBe(1);
  });

  test("includes the voice override in the request body when set", async () => {
    const calls = [];
    const { factory } = fakeAudioFactory();
    const s = new EdgeTtsSpeechSynthesizer(
      {},
      {
        fetchFn: async (url, opts) => {
          calls.push({ url, opts });
          return okAudioResponse();
        },
        audioFactory: factory,
        voice: "en-GB-SoniaNeural",
      },
    );
    await s.speak("hi").pending;
    expect(JSON.parse(calls[0].opts.body)).toEqual({
      text: "hi",
      voice: "en-GB-SoniaNeural",
    });
  });

  test("falls back to the browser engine when the server replies non-audio", async () => {
    const win = fakeSpeechWindow();
    const { factory } = fakeAudioFactory();
    const s = new EdgeTtsSpeechSynthesizer(win, {
      fetchFn: async () => ({
        ok: true,
        status: 200,
        headers: { get: () => "application/json" },
        blob: () => Promise.resolve(new Blob([])),
      }),
      audioFactory: factory,
    });
    const token = s.speak("hello");
    expect(await token.pending).toBe("browser");
    expect(win.spoken.length).toBe(1);
    expect(win.spoken[0].text).toBe("hello");
  });

  test("falls back to the browser engine when fetch rejects", async () => {
    const win = fakeSpeechWindow();
    const { factory } = fakeAudioFactory();
    const s = new EdgeTtsSpeechSynthesizer(win, {
      fetchFn: async () => {
        throw new Error("network down");
      },
      audioFactory: factory,
    });
    expect(await s.speak("hello").pending).toBe("browser");
    expect(win.spoken.length).toBe(1);
  });

  test("cancel stops current audio and a newer speak supersedes an in-flight one", async () => {
    const { created, factory } = fakeAudioFactory();
    let release;
    const gate = new Promise((resolve) => {
      release = resolve;
    });
    const s = new EdgeTtsSpeechSynthesizer(
      {},
      {
        fetchFn: async () => {
          await gate;
          return okAudioResponse();
        },
        audioFactory: factory,
      },
    );
    const first = s.speak("first");
    s.cancel(); // supersedes the in-flight fetch
    release();
    expect(await first.pending).toBeNull(); // never played, no fallback either
    expect(created.length).toBe(0);
  });

  test("speak cancels prior playing audio (replies never overlap)", async () => {
    const { created, factory } = fakeAudioFactory();
    const s = new EdgeTtsSpeechSynthesizer(
      {},
      { fetchFn: async () => okAudioResponse(), audioFactory: factory },
    );
    await s.speak("one").pending;
    await s.speak("two").pending;
    expect(created.length).toBe(2);
    expect(created[0].paused).toBe(1);
    expect(created[1].played).toBe(1);
  });
});
