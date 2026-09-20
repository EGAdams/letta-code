import type {
  VoiceMediaClient,
  VoiceTranscript,
} from "../src/voice-media-client.ts";

// Compile-time contract: capture depends only on this port's single batch
// operation and on a transcript without HTTP response metadata.
const transcript: VoiceTranscript = {
  raw_transcript: "heard words",
  cleaned_text: "Spoken words.",
};

const mediaClient: VoiceMediaClient = {
  async transcribe(_recording: Blob): Promise<VoiceTranscript> {
    return transcript;
  },
};

void mediaClient;
