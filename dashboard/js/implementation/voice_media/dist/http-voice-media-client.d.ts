import type {
  VoiceMediaClient,
  VoiceTranscript,
} from "../../../abstract/voice_media/dist/voice-media-client.js";
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
export declare class HttpVoiceMediaClient implements VoiceMediaClient {
  private readonly fetch;
  private readonly endpoint;
  private readonly filename;
  private readonly pilotAgentId;
  constructor({
    fetch,
    endpoint,
    filename,
    pilotAgentId,
  }?: HttpVoiceMediaClientOptions);
  transcribe(recording: Blob): Promise<VoiceTranscript>;
}
