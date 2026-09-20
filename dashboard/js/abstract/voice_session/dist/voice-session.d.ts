import { type Clock, type IdSource } from "./session-clock.js";
export type SessionId = string;
export type GenerationId = string;
export declare const SessionState: Readonly<{
  readonly IDLE: "idle";
  readonly LISTENING: "listening";
  readonly THINKING: "thinking";
  readonly SPEAKING: "speaking";
  readonly INTERRUPTED: "interrupted";
  readonly CLOSED: "closed";
}>;
export type SessionStateValue =
  (typeof SessionState)[keyof typeof SessionState];
export interface SessionStateChange {
  session: SessionId;
  from: SessionStateValue;
  to: SessionStateValue;
  generation: GenerationId | null;
  at: number;
}
export interface VoiceSessionDependencies {
  clock?: Clock;
  idSource?: IdSource;
  onStateChange?: (change: SessionStateChange) => void;
}
/** A handle for the one utterance owned by a speaking turn. */
export interface SpeechPlayback {
  cancel(): void;
}
export declare class IllegalTransitionError extends Error {
  readonly from: SessionStateValue;
  readonly to: SessionStateValue;
  constructor(from: SessionStateValue, to: SessionStateValue);
}
/** Owns a conversation's lifecycle and rejects output from superseded turns. */
export declare class VoiceSession {
  private readonly clock;
  private readonly ids;
  private readonly onStateChange;
  private readonly sessionId;
  private currentState;
  private generation;
  private readonly startTime;
  private readonly generations;
  private playback;
  constructor({ clock, idSource, onStateChange }?: VoiceSessionDependencies);
  get id(): SessionId;
  get state(): SessionStateValue;
  get currentGeneration(): GenerationId | null;
  get startedAt(): number;
  get closed(): boolean;
  /** The authoritative fence; malformed and stale ids fail closed. */
  accepts(generationId: unknown): generationId is GenerationId;
  issued(generationId: unknown): boolean;
  startListening(): SessionStateValue;
  beginTurn(): GenerationId;
  beginSpeaking(generationId: unknown): boolean;
  trackPlayback(generationId: unknown, playback: SpeechPlayback): boolean;
  completeTurn(generationId: unknown): boolean;
  interrupt(): GenerationId | null;
  close(): void;
  private transition;
  private apply;
}
