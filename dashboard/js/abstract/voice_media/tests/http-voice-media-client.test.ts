import { describe, expect, test } from "bun:test";
import {
  HttpVoiceMediaClient,
  type HttpVoiceMediaClientOptions,
} from "../../../implementation/voice_media/src/http-voice-media-client.ts";

const transcript = {
  ok: true,
  raw_transcript: "  heard words  ",
  cleaned_text: "Spoken words.",
};

function audio(type = "audio/webm", contents = "recorded audio") {
  return new Blob([contents], { type });
}

function reply(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  };
}

interface UploadInit {
  method: string;
  body: Blob;
  headers: Record<string, string>;
}

function client(options: HttpVoiceMediaClientOptions) {
  return new HttpVoiceMediaClient(options);
}

describe("HttpVoiceMediaClient batch upload", () => {
  test("posts exactly one recording and returns only the transcript fields", async () => {
    const recording = audio();
    const calls: Array<{ url: unknown; init: UploadInit }> = [];
    const media = client({
      fetch: async (url: unknown, init: UploadInit) => {
        calls.push({ url, init });
        return reply(transcript);
      },
    });

    expect(await media.transcribe(recording)).toEqual({
      raw_transcript: "  heard words  ",
      cleaned_text: "Spoken words.",
    });
    expect(calls).toHaveLength(1);
    expect(calls[0]?.url).toBe("/api/voice");
    expect(calls[0]?.init.method).toBe("POST");
    expect(calls[0]?.init.body).toBe(recording);
    expect(calls[0]?.init.headers["X-Filename"]).toBe("voice.webm");
  });

  test.each([
    ["audio/webm;codecs=opus", "voice.webm"],
    ["audio/ogg;codecs=opus", "voice.ogg"],
    ["audio/mp4;codecs=mp4a.40.2", "voice.mp4"],
    ["audio/wav", "voice.wav"],
  ])("labels a %s recording as %s", async (mime, filename) => {
    let sentFilename: string | undefined;
    const media = client({
      fetch: async (_url: unknown, init: UploadInit) => {
        sentFilename = init.headers["X-Filename"];
        return reply(transcript);
      },
    });
    await media.transcribe(audio(mime));
    expect(sentFilename).toBe(filename);
  });

  test("uses an injected endpoint and preserves the configured filename stem", async () => {
    const calls: Array<{ url: unknown; filename: unknown }> = [];
    const media = client({
      endpoint: "/api/voice-preview",
      filename: "meeting.webm",
      fetch: async (url: unknown, init: UploadInit) => {
        calls.push({ url, filename: init.headers["X-Filename"] });
        return reply(transcript);
      },
    });
    await media.transcribe(audio("audio/mp4"));
    expect(calls).toEqual([
      { url: "/api/voice-preview", filename: "meeting.mp4" },
    ]);
  });

  test("rejects an empty recording before calling fetch", async () => {
    let calls = 0;
    const media = client({
      fetch: async () => {
        calls += 1;
        return reply(transcript);
      },
    });
    await expect(media.transcribe(audio("audio/webm", ""))).rejects.toThrow(
      /empty|audio|recording/i,
    );
    expect(calls).toBe(0);
  });

  test("rejects an unsupported MIME type before calling fetch", async () => {
    let calls = 0;
    const media = client({
      fetch: async () => {
        calls += 1;
        return reply(transcript);
      },
    });
    await expect(media.transcribe(audio("text/plain"))).rejects.toThrow(
      /unsupported recording format/i,
    );
    expect(calls).toBe(0);
  });

  test("surfaces a server-declared processing error", async () => {
    const media = client({
      fetch: async () => reply({ ok: false, error: "transcriber unavailable" }),
    });
    await expect(media.transcribe(audio())).rejects.toThrow(
      "transcriber unavailable",
    );
  });

  test("rejects HTTP failure even if the body claims success", async () => {
    const media = client({ fetch: async () => reply(transcript, 503) });
    await expect(media.transcribe(audio())).rejects.toThrow();
  });

  test("rejects a non-JSON response", async () => {
    const media = client({
      fetch: async () => ({
        ok: true,
        status: 200,
        json: async () => {
          throw new SyntaxError("Unexpected token <");
        },
      }),
    });
    await expect(media.transcribe(audio())).rejects.toThrow();
  });

  test.each([
    { ok: true, cleaned_text: "cleaned" },
    { ok: true, raw_transcript: "raw", cleaned_text: "  " },
    { ok: true, raw_transcript: "raw", cleaned_text: null },
    { ok: "true", raw_transcript: "raw", cleaned_text: "cleaned" },
  ])("rejects an incomplete or malformed success: %p", async (body) => {
    const media = client({ fetch: async () => reply(body) });
    await expect(media.transcribe(audio())).rejects.toThrow(
      /invalid voice response/i,
    );
  });

  test("propagates a network failure without fabricating a transcript", async () => {
    const media = client({
      fetch: async () => {
        throw new TypeError("network offline");
      },
    });
    await expect(media.transcribe(audio())).rejects.toThrow("network offline");
  });
});
