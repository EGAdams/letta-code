import { describe, expect, test } from "bun:test";
import { PausableAudioGate } from "../implementation/pausable-audio-gate.js";

function fakeAudio() {
  const audio = {
    plays: 0,
    pauses: 0,
    listeners: {},
    play() {
      audio.plays += 1;
      return Promise.resolve();
    },
    pause() {
      audio.pauses += 1;
    },
    addEventListener(type, fn) {
      audio.listeners[type] = fn;
    },
  };
  return audio;
}

const tick = () => new Promise((r) => setTimeout(r, 0));

describe("PausableAudioGate", () => {
  test("starts paused and holds a new clip until resume", async () => {
    const audio = fakeAudio();
    const gate = new PausableAudioGate({ createAudio: () => audio });
    expect(gate.paused).toBe(true);
    const el = gate.audioFactory("blob:x");
    let started = false;
    el.play().then(() => {
      started = true;
    });
    await tick();
    expect(audio.plays).toBe(0);
    expect(started).toBe(false);
    gate.resume();
    await tick();
    expect(audio.plays).toBe(1);
    expect(started).toBe(true);
  });

  test("pause stops the playing clip and resume continues the same clip", async () => {
    const audio = fakeAudio();
    const gate = new PausableAudioGate({
      paused: false,
      createAudio: () => audio,
    });
    const el = gate.audioFactory("blob:x");
    await el.play();
    gate.pause();
    expect(audio.pauses).toBe(1);
    gate.resume();
    await tick();
    expect(audio.plays).toBe(2);
  });

  test("synthesizer cancelling a held clip rejects its play()", async () => {
    const audio = fakeAudio();
    const gate = new PausableAudioGate({ createAudio: () => audio });
    const el = gate.audioFactory("blob:x");
    const p = el.play();
    el.pause();
    await expect(p).rejects.toThrow();
    gate.resume();
    await tick();
    expect(audio.plays).toBe(0);
  });

  test("Pause while a clip is still loading waits for Play instead of failing", async () => {
    // Chrome rejects a pending play() when pause() lands before it starts.
    const audio = fakeAudio();
    let abortLoad = null;
    audio.play = () => {
      audio.plays += 1;
      if (audio.plays > 1) return Promise.resolve();
      return new Promise((_resolve, reject) => {
        abortLoad = () =>
          reject(
            Object.assign(new Error("interrupted"), { name: "AbortError" }),
          );
      });
    };
    audio.pause = () => {
      audio.pauses += 1;
      abortLoad?.();
    };
    const gate = new PausableAudioGate({
      paused: false,
      createAudio: () => audio,
    });
    const el = gate.audioFactory("blob:x");
    let outcome = "waiting";
    el.play().then(
      () => {
        outcome = "started";
      },
      () => {
        outcome = "failed";
      },
    );
    await tick();
    gate.pause();
    await tick();
    expect(outcome).toBe("waiting");
    gate.resume();
    await tick();
    expect(audio.plays).toBe(2);
    expect(outcome).toBe("started");
  });

  test("a real playback failure still reaches the synthesizer", async () => {
    const audio = fakeAudio();
    audio.play = () => Promise.reject(new Error("decode failed"));
    const gate = new PausableAudioGate({
      paused: false,
      createAudio: () => audio,
    });
    const el = gate.audioFactory("blob:x");
    await expect(el.play()).rejects.toThrow("decode failed");
  });

  test("a finished clip is not replayed on resume", async () => {
    const audio = fakeAudio();
    const gate = new PausableAudioGate({
      paused: false,
      createAudio: () => audio,
    });
    const el = gate.audioFactory("blob:x");
    await el.play();
    audio.listeners.ended();
    gate.pause();
    gate.resume();
    await tick();
    expect(audio.plays).toBe(1);
  });

  test("notifies listeners on toggle", () => {
    const gate = new PausableAudioGate({ createAudio: fakeAudio });
    const seen = [];
    gate.onChange((p) => seen.push(p));
    gate.toggle();
    gate.toggle();
    expect(seen).toEqual([false, true]);
  });
});
