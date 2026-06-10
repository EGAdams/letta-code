import { describe, expect, test } from "bun:test";
import { RecorderState } from "../abstract/voice-recorder.interface.js";
import { MediaRecorderVoiceRecorder } from "../implementation/media-recorder-voice-recorder.js";

/** Minimal MediaRecorder stand-in driven synchronously. */
class FakeMediaRecorder {
  constructor(stream) {
    this.stream = stream;
    this.state = "inactive";
    this.mimeType = "audio/webm";
    this.ondataavailable = null;
    this.onstop = null;
  }
  start() {
    this.state = "recording";
    if (this.ondataavailable) this.ondataavailable({ data: { size: 4 } });
  }
  stop() {
    this.state = "inactive";
    if (this.onstop) this.onstop();
  }
}

function makeDeps({ canOpen = true, voiceResult = { ok: true } } = {}) {
  const tracks = [
    {
      stop: () => {
        tracks.stopped = true;
      },
    },
  ];
  return {
    navigator: {
      mediaDevices: {
        getUserMedia: async () => {
          if (!canOpen) throw new Error("denied");
          return { getTracks: () => tracks };
        },
      },
    },
    MediaRecorder: FakeMediaRecorder,
    Blob: class {
      constructor(parts, opts) {
        this.parts = parts;
        this.type = opts.type;
        this.size = parts.length;
      }
    },
    fetch: async () => ({ json: async () => voiceResult }),
    _tracks: tracks,
  };
}

describe("MediaRecorderVoiceRecorder (concrete VoiceRecorder)", () => {
  test("full capture: idle -> recording -> processing -> idle", async () => {
    const states = [];
    const deps = makeDeps({ voiceResult: { ok: true, cleaned_text: "hello" } });
    const r = new MediaRecorderVoiceRecorder({
      ...deps,
      onStateChange: (s) => states.push(s),
    });

    expect(await r.start()).toBe(true);
    expect(r.state).toBe(RecorderState.RECORDING);

    const result = await r.stop();
    expect(result).toEqual({ ok: true, cleaned_text: "hello" });
    expect(r.state).toBe(RecorderState.IDLE);
    expect(deps._tracks.stopped).toBe(true); // stream released
    expect(states).toEqual([
      RecorderState.RECORDING,
      RecorderState.PROCESSING,
      RecorderState.IDLE,
    ]);
  });

  test("openStream returns false when getUserMedia is unavailable", async () => {
    const r = new MediaRecorderVoiceRecorder({ navigator: {} });
    expect(await r.start()).toBe(false);
    expect(r.state).toBe(RecorderState.IDLE);
  });

  test("openStream returns false when permission is denied", async () => {
    const r = new MediaRecorderVoiceRecorder(makeDeps({ canOpen: false }));
    expect(await r.start()).toBe(false);
  });

  test("transcribe throws when the server reports failure", async () => {
    const r = new MediaRecorderVoiceRecorder(
      makeDeps({ voiceResult: { ok: false, error: "whisper down" } }),
    );
    await r.start();
    await expect(r.stop()).rejects.toThrow("whisper down");
    expect(r.state).toBe(RecorderState.IDLE); // base class restores idle
  });
});
