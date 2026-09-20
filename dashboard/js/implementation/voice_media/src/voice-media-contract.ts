/** The binary upload's extension must describe the MediaRecorder output. */
const AUDIO_EXTENSIONS: Readonly<Record<string, string>> = Object.freeze({
  "audio/webm": "webm",
  "audio/ogg": "ogg",
  "audio/mp4": "mp4",
  "audio/x-m4a": "m4a",
  "audio/wav": "wav",
  "audio/x-wav": "wav",
  "audio/mpeg": "mp3",
  "audio/flac": "flac",
  "audio/aac": "aac",
});

export interface VoiceUploadSuccess {
  ok: true;
  raw_transcript: string;
  cleaned_text: string;
}

export function recordingFilename(
  mimeType: string,
  preferred = "voice.webm",
): string {
  const type = mimeType.split(";", 1)[0]?.trim().toLowerCase();
  const extension = type ? AUDIO_EXTENSIONS[type] : undefined;
  if (!extension) throw new Error(`Unsupported recording format: ${mimeType}`);
  const stem = preferred.replace(/\.[^.]+$/, "");
  return `${stem}.${extension}`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

export function parseVoiceUploadResponse(value: unknown): VoiceUploadSuccess {
  if (!isRecord(value) || typeof value.ok !== "boolean")
    throw new Error("invalid voice response");
  if (!value.ok) {
    throw new Error(
      typeof value.error === "string" && value.error
        ? value.error
        : "voice processing failed",
    );
  }
  if (
    typeof value.raw_transcript !== "string" ||
    !value.raw_transcript.trim() ||
    typeof value.cleaned_text !== "string" ||
    !value.cleaned_text.trim()
  )
    throw new Error("invalid voice response");
  return {
    ok: true,
    raw_transcript: value.raw_transcript,
    cleaned_text: value.cleaned_text,
  };
}
