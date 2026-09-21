// Browser-local opt-in for one agent's Pipecat voice uploads.

import { MediaRecorderVoiceRecorder } from "../implementation/media-recorder-voice-recorder.js";
import { HttpVoiceMediaClient } from "../implementation/voice_media/dist/http-voice-media-client.js";

export const PIPECAT_PILOT_AGENT_KEY = "voicePipecatPilotAgentId";

export function recorderFactoryForAgent(
  agentId,
  storage,
  { serverSelected = false } = {},
) {
  const isPilot =
    Boolean(agentId) &&
    (serverSelected || storage?.getItem?.(PIPECAT_PILOT_AGENT_KEY) === agentId);
  return (options) =>
    new MediaRecorderVoiceRecorder({
      ...options,
      ...(isPilot
        ? {
            mediaClient: new HttpVoiceMediaClient({
              fetch: options.fetch,
              pilotAgentId: agentId,
            }),
          }
        : {}),
    });
}
