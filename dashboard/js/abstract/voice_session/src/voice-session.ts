import {
  type Clock,
  type IdSource,
  ManualClock,
  SequentialIdSource,
} from "./session-clock.js";

export type SessionId = string;
export type GenerationId = string;

export const SessionState = Object.freeze({
  IDLE: "idle",
  LISTENING: "listening",
  THINKING: "thinking",
  SPEAKING: "speaking",
  INTERRUPTED: "interrupted",
  CLOSED: "closed",
} as const);

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

const LEGAL: Record<SessionStateValue, readonly SessionStateValue[]> =
  Object.freeze({
    [SessionState.IDLE]: [SessionState.LISTENING],
    [SessionState.LISTENING]: [SessionState.THINKING, SessionState.INTERRUPTED],
    [SessionState.THINKING]: [
      SessionState.SPEAKING,
      SessionState.LISTENING,
      SessionState.INTERRUPTED,
    ],
    [SessionState.SPEAKING]: [SessionState.LISTENING, SessionState.INTERRUPTED],
    [SessionState.INTERRUPTED]: [SessionState.LISTENING],
    [SessionState.CLOSED]: [],
  });

export class IllegalTransitionError extends Error {
  constructor(
    public readonly from: SessionStateValue,
    public readonly to: SessionStateValue,
  ) {
    super(`VoiceSession: ${from} -> ${to} is not a legal transition`);
    this.name = "IllegalTransitionError";
  }
}

/** Owns a conversation's lifecycle and rejects output from superseded turns. */
export class VoiceSession {
  private readonly clock: Clock;
  private readonly ids: IdSource;
  private readonly onStateChange: (change: SessionStateChange) => void;
  private readonly sessionId: SessionId;
  private currentState: SessionStateValue = SessionState.IDLE;
  private generation: GenerationId | null = null;
  private readonly startTime: number;
  private readonly generations = new Set<GenerationId>();

  constructor({
    clock = new ManualClock(),
    idSource = new SequentialIdSource(),
    onStateChange = () => {},
  }: VoiceSessionDependencies = {}) {
    this.clock = clock;
    this.ids = idSource;
    this.onStateChange = onStateChange;
    this.sessionId = idSource.next("session");
    this.startTime = clock.now();
  }

  get id(): SessionId {
    return this.sessionId;
  }

  get state(): SessionStateValue {
    return this.currentState;
  }

  get currentGeneration(): GenerationId | null {
    return this.generation;
  }

  get startedAt(): number {
    return this.startTime;
  }

  get closed(): boolean {
    return this.currentState === SessionState.CLOSED;
  }

  /** The authoritative fence; malformed and stale ids fail closed. */
  accepts(generationId: unknown): generationId is GenerationId {
    return (
      !this.closed &&
      typeof generationId === "string" &&
      !!generationId &&
      generationId === this.generation
    );
  }

  issued(generationId: unknown): boolean {
    return (
      typeof generationId === "string" && this.generations.has(generationId)
    );
  }

  startListening(): SessionStateValue {
    this.transition(SessionState.LISTENING);
    return this.currentState;
  }

  beginTurn(): GenerationId {
    this.transition(SessionState.THINKING);
    this.generation = this.ids.next("gen");
    this.generations.add(this.generation);
    return this.generation;
  }

  beginSpeaking(generationId: unknown): boolean {
    if (!this.accepts(generationId)) return false;
    this.transition(SessionState.SPEAKING);
    return true;
  }

  completeTurn(generationId: unknown): boolean {
    if (!this.accepts(generationId)) return false;
    this.transition(SessionState.LISTENING);
    this.generation = null;
    return true;
  }

  interrupt(): GenerationId | null {
    const superseded = this.generation;
    this.transition(SessionState.INTERRUPTED);
    this.generation = null;
    return superseded;
  }

  close(): void {
    if (this.closed) return;
    this.apply(SessionState.CLOSED);
    this.generation = null;
  }

  private transition(to: SessionStateValue): void {
    if (!LEGAL[this.currentState].includes(to)) {
      throw new IllegalTransitionError(this.currentState, to);
    }
    this.apply(to);
  }

  private apply(to: SessionStateValue): void {
    const from = this.currentState;
    this.currentState = to;
    this.onStateChange({
      session: this.sessionId,
      from,
      to,
      generation: this.generation,
      at: this.clock.now(),
    });
  }
}
