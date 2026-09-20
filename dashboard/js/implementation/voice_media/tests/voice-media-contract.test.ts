import { describe, expect, test } from "bun:test";
import {
  parseVoiceUploadResponse,
  recordingFilename,
} from "../src/voice-media-contract.ts";

describe("voice media wire contract", () => {
  test.each([
    ["audio/webm;codecs=opus", "voice.webm"],
    ["audio/ogg;codecs=opus", "voice.ogg"],
    ["audio/mp4;codecs=mp4a.40.2", "voice.mp4"],
    ["audio/wav", "voice.wav"],
  ])("names %s with its actual extension", (mime, expected) => {
    expect(recordingFilename(mime)).toBe(expected);
  });

  test("rejects an unrecognized recording format before upload", () => {
    expect(() => recordingFilename("audio/unknown")).toThrow(
      /Unsupported recording format/,
    );
  });

  test("accepts only a complete successful transcript", () => {
    expect(
      parseVoiceUploadResponse({
        ok: true,
        raw_transcript: "heard",
        cleaned_text: "cleaned",
      }),
    ).toEqual({ ok: true, raw_transcript: "heard", cleaned_text: "cleaned" });
    expect(() =>
      parseVoiceUploadResponse({ ok: true, cleaned_text: "cleaned" }),
    ).toThrow(/invalid voice response/);
  });

  test("surfaces the server error without treating it as a transcript", () => {
    expect(() =>
      parseVoiceUploadResponse({ ok: false, error: "whisper down" }),
    ).toThrow("whisper down");
  });
});
