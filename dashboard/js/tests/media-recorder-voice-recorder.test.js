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

function makeDeps({
  canOpen = true,
  voiceResult = { ok: true },
  denyError = new Error("denied"),
} = {}) {
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
          if (!canOpen) throw denyError;
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
    fetch: async () => ({
      ok: true,
      status: 200,
      json: async () => voiceResult,
    }),
    _tracks: tracks,
  };
}

describe("MediaRecorderVoiceRecorder (concrete VoiceRecorder)", () => {
  test("full capture: idle -> recording -> processing -> idle", async () => {
    const states = [];
    const deps = makeDeps({
      voiceResult: { ok: true, raw_transcript: "hello", cleaned_text: "hello" },
    });
    const r = new MediaRecorderVoiceRecorder({
      ...deps,
      onStateChange: (s) => states.push(s),
    });

    expect(await r.start()).toBe(true);
    expect(r.state).toBe(RecorderState.RECORDING);

    const result = await r.stop();
    expect(result).toEqual({
      raw_transcript: "hello",
      cleaned_text: "hello",
    });
    expect(r.state).toBe(RecorderState.IDLE);
    expect(deps._tracks.stopped).toBe(true); // stream released
    expect(states).toEqual([
      RecorderState.RECORDING,
      RecorderState.PROCESSING,
      RecorderState.IDLE,
    ]);
  });

  test("openStream returns false when getUserMedia is unavailable, with a secure-context lastError", async () => {
    const r = new MediaRecorderVoiceRecorder({ navigator: {} });
    expect(await r.start()).toBe(false);
    expect(r.state).toBe(RecorderState.IDLE);
    expect(r.lastError).toMatch(/secure context/i);
  });

  test("openStream returns false with a permission-denied lastError on NotAllowedError", async () => {
    const err = new Error("denied");
    err.name = "NotAllowedError";
    const r = new MediaRecorderVoiceRecorder(
      makeDeps({ canOpen: false, denyError: err }),
    );
    expect(await r.start()).toBe(false);
    expect(r.lastError).toMatch(/permission was denied/i);
  });

  test("openStream distinguishes a generic getUserMedia failure from permission-denied", async () => {
    const err = new Error("device busy");
    err.name = "NotReadableError";
    const r = new MediaRecorderVoiceRecorder(
      makeDeps({ canOpen: false, denyError: err }),
    );
    expect(await r.start()).toBe(false);
    expect(r.lastError).not.toMatch(/permission was denied/i);
    expect(r.lastError).toContain("device busy");
  });

  test("transcribe throws when the server reports failure", async () => {
    const r = new MediaRecorderVoiceRecorder(
      makeDeps({ voiceResult: { ok: false, error: "whisper down" } }),
    );
    await r.start();
    await expect(r.stop()).rejects.toThrow("whisper down");
    expect(r.state).toBe(RecorderState.IDLE); // base class restores idle
  });

  test("uploads the actual MP4 recording format in X-Filename", async () => {
    const deps = makeDeps({
      voiceResult: { ok: true, raw_transcript: "raw", cleaned_text: "clean" },
    });
    const sent = [];
    class Mp4Recorder extends FakeMediaRecorder {
      constructor(stream) {
        super(stream);
        this.mimeType = "audio/mp4;codecs=mp4a.40.2";
      }
    }
    const r = new MediaRecorderVoiceRecorder({
      ...deps,
      MediaRecorder: Mp4Recorder,
      fetch: async (url, options) => {
        sent.push({ url, options });
        return {
          ok: true,
          status: 200,
          json: async () => ({
            ok: true,
            raw_transcript: "raw",
            cleaned_text: "clean",
          }),
        };
      },
    });
    await r.start();
    await r.stop();
    expect(sent[0].url).toBe("/api/voice");
    expect(sent[0].options.method).toBe("POST");
    expect(sent[0].options.headers["X-Filename"]).toBe("voice.mp4");
    expect(sent[0].options.body.type).toBe("audio/mp4;codecs=mp4a.40.2");
  });

  test("releases the microphone if MediaRecorder start fails", async () => {
    const deps = makeDeps();
    class FailingRecorder extends FakeMediaRecorder {
      start() {
        throw new Error("capture failed");
      }
    }
    const r = new MediaRecorderVoiceRecorder({
      ...deps,
      MediaRecorder: FailingRecorder,
    });
    await expect(r.start()).rejects.toThrow("capture failed");
    expect(r.state).toBe(RecorderState.IDLE);
    expect(deps._tracks.stopped).toBe(true);
  });

  test("releases the microphone if MediaRecorder construction fails", async () => {
    const deps = makeDeps();
    class FailingRecorder {
      constructor() {
        throw new Error("unsupported encoder");
      }
    }
    const r = new MediaRecorderVoiceRecorder({
      ...deps,
      MediaRecorder: FailingRecorder,
    });
    await expect(r.start()).rejects.toThrow("unsupported encoder");
    expect(r.state).toBe(RecorderState.IDLE);
    expect(deps._tracks.stopped).toBe(true);
  });

  test("releases the microphone and returns idle if MediaRecorder stop fails", async () => {
    const deps = makeDeps();
    class FailingRecorder extends FakeMediaRecorder {
      stop() {
        throw new Error("device disconnected");
      }
    }
    const r = new MediaRecorderVoiceRecorder({
      ...deps,
      MediaRecorder: FailingRecorder,
    });
    await r.start();
    await expect(r.stop()).rejects.toThrow("device disconnected");
    expect(r.state).toBe(RecorderState.IDLE);
    expect(deps._tracks.stopped).toBe(true);
  });

  test("rejects a malformed successful voice response", async () => {
    const r = new MediaRecorderVoiceRecorder(
      makeDeps({ voiceResult: { ok: true, cleaned_text: null } }),
    );
    await r.start();
    await expect(r.stop()).rejects.toThrow(/invalid voice response/i);
    expect(r.state).toBe(RecorderState.IDLE);
  });
});
