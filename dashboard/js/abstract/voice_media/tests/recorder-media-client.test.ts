import { describe, expect, test } from "bun:test";
import { MediaRecorderVoiceRecorder } from "../../../implementation/media-recorder-voice-recorder.js";
import { RecorderState } from "../../voice-recorder.interface.js";

class FakeMediaRecorder {
  state = "inactive";
  mimeType = "audio/mp4;codecs=mp4a.40.2";
  ondataavailable: ((event: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;

  start() {
    this.state = "recording";
    this.ondataavailable?.({ data: new Blob(["audio frame"]) });
  }

  stop() {
    this.state = "inactive";
    this.onstop?.();
  }
}

function recorder(mediaClient: {
  transcribe: (blob: Blob) => Promise<unknown>;
}) {
  let stoppedTracks = 0;
  let fetchCalls = 0;
  const instance = new MediaRecorderVoiceRecorder({
    navigator: {
      mediaDevices: {
        getUserMedia: async () => ({
          getTracks: () => [
            {
              stop: () => {
                stoppedTracks += 1;
              },
            },
          ],
        }),
      },
    },
    MediaRecorder: FakeMediaRecorder,
    mediaClient,
    fetch: async () => {
      fetchCalls += 1;
      throw new Error("recorder bypassed injected media client");
    },
  });
  return {
    instance,
    get stoppedTracks() {
      return stoppedTracks;
    },
    get fetchCalls() {
      return fetchCalls;
    },
  };
}

describe("MediaRecorderVoiceRecorder delegates to VoiceMediaClient", () => {
  test("sends one completed recording to the injected client after stop", async () => {
    const recordings: Blob[] = [];
    const result = { raw_transcript: "raw", cleaned_text: "cleaned" };
    const ctx = recorder({
      transcribe: async (blob) => {
        recordings.push(blob);
        return result;
      },
    });

    expect(await ctx.instance.start()).toBe(true);
    expect(recordings).toHaveLength(0);
    expect(ctx.instance.state).toBe(RecorderState.RECORDING);
    expect(await ctx.instance.stop()).toBe(result);
    expect(recordings).toHaveLength(1);
    expect(recordings[0]?.type).toBe("audio/mp4;codecs=mp4a.40.2");
    expect(recordings[0]?.size).toBeGreaterThan(0);
    expect(ctx.stoppedTracks).toBe(1);
    expect(ctx.fetchCalls).toBe(0);
    expect(ctx.instance.state).toBe(RecorderState.IDLE);
  });

  test("returns to idle and releases the microphone when the client rejects", async () => {
    const ctx = recorder({
      transcribe: async () => {
        throw new Error("media service unavailable");
      },
    });
    await ctx.instance.start();
    await expect(ctx.instance.stop()).rejects.toThrow(
      "media service unavailable",
    );
    expect(ctx.instance.state).toBe(RecorderState.IDLE);
    expect(ctx.stoppedTracks).toBe(1);
    expect(ctx.fetchCalls).toBe(0);
  });

  test("uses the injected client for each new recording", async () => {
    const recordings: Blob[] = [];
    const ctx = recorder({
      transcribe: async (blob) => {
        recordings.push(blob);
        return { raw_transcript: "raw", cleaned_text: "cleaned" };
      },
    });
    await ctx.instance.start();
    await ctx.instance.stop();
    await ctx.instance.start();
    await ctx.instance.stop();
    expect(recordings).toHaveLength(2);
    expect(recordings[0]).not.toBe(recordings[1]);
    expect(ctx.stoppedTracks).toBe(2);
    expect(ctx.fetchCalls).toBe(0);
  });
});
