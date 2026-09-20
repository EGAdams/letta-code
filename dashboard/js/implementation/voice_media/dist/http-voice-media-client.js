import {
  parseVoiceUploadResponse,
  recordingFilename,
} from "./voice-media-contract.js";
/** Adapts the dashboard's batch /api/voice wire format to VoiceMediaClient. */
export class HttpVoiceMediaClient {
  fetch;
  endpoint;
  filename;
  pilotAgentId;
  constructor({
    fetch = globalThis.fetch.bind(globalThis),
    endpoint = "/api/voice",
    filename = "voice.webm",
    pilotAgentId,
  } = {}) {
    this.fetch = fetch;
    this.endpoint = endpoint;
    this.filename = filename;
    this.pilotAgentId = pilotAgentId;
  }
  async transcribe(recording) {
    if (recording.size === 0) throw new Error("empty audio recording");
    const filename = recordingFilename(recording.type, this.filename);
    const headers = { "X-Filename": filename };
    if (this.pilotAgentId) {
      headers["X-Voice-Media-Backend"] = "pipecat";
      headers["X-Voice-Agent-Id"] = this.pilotAgentId;
    }
    const response = await this.fetch(this.endpoint, {
      method: "POST",
      headers,
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
