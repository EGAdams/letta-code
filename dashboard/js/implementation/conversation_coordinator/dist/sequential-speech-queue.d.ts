import type {
  GenerationId,
  SpeechQueuePort,
  SpeechSegment,
} from "../../../abstract/conversation_coordinator/dist/conversation-coordinator.js";
interface PlaybackToken {
  readonly pending?: Promise<unknown>;
  readonly finished?: Promise<unknown>;
  cancel?(): void;
}
interface SpeechSynthesizerPort {
  readonly lastError?: string | null;
  speak(text: string, agentName?: string | null): PlaybackToken | null;
  prefetch?(text: string, agentName?: string | null): void;
  cancel?(): void;
}
interface PlaybackSessionPort {
  trackPlayback?(
    generationId: unknown,
    playback: {
      cancel(): void;
    },
  ): boolean;
  completeTurn?(generationId: unknown): boolean;
}
export type SpeechSegmentTelemetryEvent =
  | "tts_requested"
  | "audio_ready"
  | "audio_playing";
/** Optional latency-instrumentation hook; never gates playback. */
export type SpeechSegmentTelemetryPort = (
  event: SpeechSegmentTelemetryEvent,
  segment: SpeechSegment,
) => void;
/** Serializes playback while allowing the agent to keep producing sentences. */
export declare class SequentialSpeechQueue implements SpeechQueuePort {
  private readonly states;
  private readonly speech;
  private readonly session;
  private readonly telemetry;
  constructor({
    speech,
    session,
    telemetry,
  }: {
    speech: SpeechSynthesizerPort;
    session?: PlaybackSessionPort | null;
    telemetry?: SpeechSegmentTelemetryPort | null;
  });
  enqueue(segment: SpeechSegment, agentName: string): void;
  finish(generationId: GenerationId): Promise<void>;
  private emitTelemetry;
  cancel(generationId: GenerationId): void;
}
export {};
