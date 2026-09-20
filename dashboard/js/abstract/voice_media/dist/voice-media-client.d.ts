/** One complete recording becomes one validated transcript. */
export interface VoiceTranscript {
  raw_transcript: string;
  cleaned_text: string;
}
/** Batch media port used by capture, independent of the transport/provider. */
export interface VoiceMediaClient {
  transcribe(recording: Blob): Promise<VoiceTranscript>;
}
