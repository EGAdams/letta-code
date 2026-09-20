import {
  parseVoiceUploadResponse,
  recordingFilename,
} from "./voice-media-contract.js";
/** Adapts the dashboard's batch /api/voice wire format to VoiceMediaClient. */
export class HttpVoiceMediaClient {
  fetch;
  endpoint;
  filename;
  constructor({
    fetch = globalThis.fetch.bind(globalThis),
    endpoint = "/api/voice",
    filename = "voice.webm",
  } = {}) {
    this.fetch = fetch;
    this.endpoint = endpoint;
    this.filename = filename;
  }
  async transcribe(recording) {
    if (recording.size === 0) throw new Error("empty audio recording");
    const filename = recordingFilename(recording.type, this.filename);
    const response = await this.fetch(this.endpoint, {
      method: "POST",
      headers: { "X-Filename": filename },
      body: recording,
    });
    if (!response.ok) {
      throw new Error(`voice upload failed (HTTP ${response.status})`);
    }
    const payload = parseVoiceUploadResponse(await response.json());
    return {
      raw_transcript: payload.raw_transcript,
      cleaned_text: payload.cleaned_text,
    };
  }
}
