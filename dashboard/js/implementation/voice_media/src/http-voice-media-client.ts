import type {
  VoiceMediaClient,
  VoiceTranscript,
} from "../../../abstract/voice_media/dist/voice-media-client.js";
import {
  parseVoiceUploadResponse,
  recordingFilename,
} from "./voice-media-contract.js";

interface VoiceHttpResponse {
  ok: boolean;
  status: number;
  json(): Promise<unknown>;
}

type VoiceFetch = (
  url: string,
  init: {
    method: "POST";
    headers: Record<string, string>;
    body: Blob;
  },
) => Promise<VoiceHttpResponse>;

export interface HttpVoiceMediaClientOptions {
  fetch?: VoiceFetch;
  endpoint?: string;
  filename?: string;
  pilotAgentId?: string;
}

/** Adapts the dashboard's batch /api/voice wire format to VoiceMediaClient. */
export class HttpVoiceMediaClient implements VoiceMediaClient {
  private readonly fetch: VoiceFetch;
  private readonly endpoint: string;
  private readonly filename: string;
  private readonly pilotAgentId: string | undefined;

  constructor({
    fetch = globalThis.fetch.bind(globalThis),
    endpoint = "/api/voice",
    filename = "voice.webm",
    pilotAgentId,
  }: HttpVoiceMediaClientOptions = {}) {
    this.fetch = fetch;
    this.endpoint = endpoint;
    this.filename = filename;
    this.pilotAgentId = pilotAgentId;
  }

  async transcribe(recording: Blob): Promise<VoiceTranscript> {
    if (recording.size === 0) throw new Error("empty audio recording");
    const filename = recordingFilename(recording.type, this.filename);
    const headers: Record<string, string> = { "X-Filename": filename };
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
