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
/** Serializes playback while allowing the agent to keep producing sentences. */
export declare class SequentialSpeechQueue implements SpeechQueuePort {
  private readonly states;
  private readonly speech;
  private readonly session;
  constructor({
    speech,
    session,
  }: {
    speech: SpeechSynthesizerPort;
    session?: PlaybackSessionPort | null;
  });
  enqueue(segment: SpeechSegment, agentName: string): void;
  finish(generationId: GenerationId): Promise<void>;
  cancel(generationId: GenerationId): void;
}
