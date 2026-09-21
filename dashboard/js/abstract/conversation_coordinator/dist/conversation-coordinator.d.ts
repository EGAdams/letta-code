import type {
  AgentEvent as ExistingAgentEvent,
  ConversationTurn as ExistingConversationTurn,
} from "../../conversation-agent.interface.js";
import type {
  GenerationId,
  SessionStateValue,
} from "../../voice_session/dist/voice-session.js";
export type { GenerationId };
/** Public event kinds produced by a conversation adapter. */
export type AgentEventKind =
  | "assistant_text"
  | "reasoning"
  | "tool_call"
  | "tool_result"
  | "status"
  | "terminal";
/** Provider neutral input for one agent turn. */
export type ConversationTurn = ExistingConversationTurn;
/** Provider neutral output from one agent turn. */
export interface AgentEvent
  extends Omit<ExistingAgentEvent, "kind" | "detail"> {
  kind: AgentEventKind;
  text: string;
  generationId: GenerationId;
  name?: string;
  detail?: Readonly<Record<string, unknown>> | null;
}
/** Existing conversation adapter boundary, expressed structurally for TS. */
export interface ConversationAgentPort {
  submit(
    turn: ConversationTurn,
    generationId: GenerationId,
  ): AsyncIterable<AgentEvent>;
  cancel(generationId: GenerationId): void;
}
/** The subset of VoiceSession used by the coordinator. */
export interface VoiceSessionPort {
  readonly state: SessionStateValue;
  readonly currentGeneration: GenerationId | null;
  startListening(): string;
  beginTurn(): GenerationId;
  beginSpeaking(generationId: unknown): boolean;
  completeTurn(generationId: unknown): boolean;
  interrupt(): GenerationId | null;
  close(): void;
  accepts(generationId: unknown): generationId is GenerationId;
}
/** Result of the existing SpokenOutputPolicy gate. */
export interface SpeechVerdict {
  readonly speak: boolean;
  readonly reason: string;
  readonly text: string;
}
/** Only current public assistant text passes this policy. */
export interface SpokenOutputPolicyPort {
  admit(event: AgentEvent): SpeechVerdict;
}
/** One sentence ready for ordered synthesis and playback. */
export interface SpeechSegment {
  readonly generationId: GenerationId;
  readonly sequence: number;
  readonly text: string;
  readonly final: boolean;
}
/**
 * Strategy for deterministic sentence boundaries.
 *
 * It receives normalized deltas, not provider snapshots. `flush` releases the
 * final unterminated phrase when the agent emits a terminal event.
 */
export interface SentenceSegmenterPort {
  push(delta: string): readonly string[];
  flush(): string | null;
  reset(): void;
}
/**
 * Ordered, cancellable output boundary.
 *
 * A concrete queue may prepare sentence N+1 while sentence N is playing, but
 * it must play segments in sequence and reject cancelled generations.
 */
export interface SpeechQueuePort {
  enqueue(segment: SpeechSegment, agentName: string): void;
  finish(generationId: GenerationId): Promise<void>;
  cancel(generationId: GenerationId): void;
}
/** UI and telemetry observer; the coordinator contains no DOM operations. */
export interface ConversationCoordinatorObserver {
  onEvent?(event: AgentEvent): void;
  onAssistantDelta?(generationId: GenerationId, text: string): void;
  onSpeechQueued?(segment: SpeechSegment): void;
  onTurnComplete?(outcome: ConversationTurnOutcome): void;
  onError?(generationId: GenerationId | null, error: Error): void;
}
export type ConversationTurnStatus = "completed" | "interrupted" | "failed";
export interface ConversationTurnOutcome {
  readonly generationId: GenerationId;
  readonly status: ConversationTurnStatus;
  readonly text: string;
  readonly spokenSegments: number;
}
export interface ConversationCoordinatorDependencies {
  readonly agent: ConversationAgentPort;
  readonly session: VoiceSessionPort;
  readonly spokenOutputPolicy: SpokenOutputPolicyPort;
  readonly sentenceSegmenter: SentenceSegmenterPort;
  readonly speechQueue: SpeechQueuePort;
  readonly observer?: ConversationCoordinatorObserver;
}
export interface ConversationTurnOptions {
  readonly agentName: string;
  readonly speak: boolean;
}
/** Mediator contract for a single conversational surface. */
export interface ConversationCoordinatorPort {
  start(
    turn: ConversationTurn,
    options: ConversationTurnOptions,
  ): Promise<ConversationTurnOutcome>;
  interrupt(): GenerationId | null;
  close(): void;
}
