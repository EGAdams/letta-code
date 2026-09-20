import { ManualClock, SequentialIdSource } from "./session-clock.js";
export const SessionState = Object.freeze({
  IDLE: "idle",
  LISTENING: "listening",
  THINKING: "thinking",
  SPEAKING: "speaking",
  INTERRUPTED: "interrupted",
  CLOSED: "closed",
});
const LEGAL = Object.freeze({
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
  from;
  to;
  constructor(from, to) {
    super(`VoiceSession: ${from} -> ${to} is not a legal transition`);
    this.from = from;
    this.to = to;
    this.name = "IllegalTransitionError";
  }
}
/** Owns a conversation's lifecycle and rejects output from superseded turns. */
export class VoiceSession {
  clock;
  ids;
  onStateChange;
  sessionId;
  currentState = SessionState.IDLE;
  generation = null;
  startTime;
  generations = new Set();
  constructor({
    clock = new ManualClock(),
    idSource = new SequentialIdSource(),
    onStateChange = () => {},
  } = {}) {
    this.clock = clock;
    this.ids = idSource;
    this.onStateChange = onStateChange;
    this.sessionId = idSource.next("session");
    this.startTime = clock.now();
  }
  get id() {
    return this.sessionId;
  }
  get state() {
    return this.currentState;
  }
  get currentGeneration() {
    return this.generation;
  }
  get startedAt() {
    return this.startTime;
  }
  get closed() {
    return this.currentState === SessionState.CLOSED;
  }
  /** The authoritative fence; malformed and stale ids fail closed. */
  accepts(generationId) {
    return (
      !this.closed &&
      typeof generationId === "string" &&
      !!generationId &&
      generationId === this.generation
    );
  }
  issued(generationId) {
    return (
      typeof generationId === "string" && this.generations.has(generationId)
    );
  }
  startListening() {
    this.transition(SessionState.LISTENING);
    return this.currentState;
  }
  beginTurn() {
    this.transition(SessionState.THINKING);
    this.generation = this.ids.next("gen");
    this.generations.add(this.generation);
    return this.generation;
  }
  beginSpeaking(generationId) {
    if (!this.accepts(generationId)) return false;
    this.transition(SessionState.SPEAKING);
    return true;
  }
  completeTurn(generationId) {
    if (!this.accepts(generationId)) return false;
    this.transition(SessionState.LISTENING);
    this.generation = null;
    return true;
  }
  interrupt() {
    const superseded = this.generation;
    this.transition(SessionState.INTERRUPTED);
    this.generation = null;
    return superseded;
  }
  close() {
    if (this.closed) return;
    this.apply(SessionState.CLOSED);
    this.generation = null;
  }
  transition(to) {
    if (!LEGAL[this.currentState].includes(to)) {
      throw new IllegalTransitionError(this.currentState, to);
    }
    this.apply(to);
  }
  apply(to) {
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
