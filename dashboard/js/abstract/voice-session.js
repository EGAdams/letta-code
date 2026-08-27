import { ManualClock, SequentialIdSource } from "./session-clock.js";

/**
 * VoiceSession — the object that owns one voice conversation.
 *
 * Documented as Planned on Project Plans -> Voice Communication -> VoiceSession;
 * this is that object. It is deliberately framework-free: no Letta, no Pipecat,
 * no browser APIs, no timers. Time and identity arrive as injected ports, which
 * is what makes lifecycle rules testable without sleeps or a microphone.
 *
 * Its real job is **generation fencing**. Every agent turn gets a GenerationId.
 * When the user interrupts, the live turn becomes stale, and any output still
 * in flight for it has one authoritative place to ask "is this still wanted?":
 *
 *     const gen = session.beginTurn();
 *     const reply = await agent.submit(turn, gen);
 *     if (!session.accepts(gen)) return;      // superseded — drop it
 *
 * Without that check a slow reply from an abandoned turn arrives late and is
 * spoken over the new one. That failure is the reason this class exists.
 *
 * @typedef {string} SessionId
 * @typedef {string} GenerationId
 */

/** The legal states of one conversation. */
export const SessionState = Object.freeze({
  IDLE: "idle",
  LISTENING: "listening",
  THINKING: "thinking",
  SPEAKING: "speaking",
  INTERRUPTED: "interrupted",
  CLOSED: "closed",
});

/**
 * Which transitions are legal, as `from -> [to...]`.
 *
 * `close()` is legal from every live state and is handled separately: a session
 * must always be closable, including out of an error path, so it is not worth
 * listing on every row. Nothing leaves CLOSED.
 */
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

/** Thrown when a caller asks for a transition the lifecycle does not allow. */
export class IllegalTransitionError extends Error {
  constructor(from, to) {
    super(`VoiceSession: ${from} -> ${to} is not a legal transition`);
    this.name = "IllegalTransitionError";
    this.from = from;
    this.to = to;
  }
}

export class VoiceSession {
  /**
   * @param {object} [deps]
   * @param {import("./session-clock.js").Clock} [deps.clock]
   * @param {import("./session-clock.js").IdSource} [deps.idSource]
   * @param {(change: {session: SessionId, from: string, to: string,
   *   generation: GenerationId|null, at: number}) => void} [deps.onStateChange]
   */
  constructor({
    clock = new ManualClock(),
    idSource = new SequentialIdSource(),
    onStateChange = () => {},
  } = {}) {
    this._clock = clock;
    this._ids = idSource;
    this._onStateChange = onStateChange;
    this._id = idSource.next("session");
    this._state = SessionState.IDLE;
    this._generation = null;
    this._startedAt = clock.now();
    // Every generation this session has ever issued, so a late arrival can be
    // told apart from an id that was never ours at all.
    this._issued = new Set();
  }

  /** @returns {SessionId} */
  get id() {
    return this._id;
  }

  /** @returns {string} one of SessionState */
  get state() {
    return this._state;
  }

  /** @returns {GenerationId|null} the live agent turn, if any */
  get currentGeneration() {
    return this._generation;
  }

  /** @returns {number} clock time at construction */
  get startedAt() {
    return this._startedAt;
  }

  /** True once close() has run. A closed session accepts nothing. */
  get closed() {
    return this._state === SessionState.CLOSED;
  }

  /**
   * The fence. True only for the generation that is still live.
   *
   * Fails closed on everything else: a superseded id, an id from another
   * session, `null`, or any id at all once the session is closed.
   *
   * @param {GenerationId} generationId
   * @returns {boolean}
   */
  accepts(generationId) {
    if (this.closed) return false;
    if (typeof generationId !== "string" || !generationId) return false;
    return generationId === this._generation;
  }

  /** True if this session issued the id at some point, live or not. */
  issued(generationId) {
    return this._issued.has(generationId);
  }

  /** idle | interrupted | speaking | thinking -> listening. */
  startListening() {
    this._transition(SessionState.LISTENING);
    return this._state;
  }

  /**
   * Start an agent turn: listening -> thinking, minting a new GenerationId and
   * superseding whatever turn was live.
   *
   * @returns {GenerationId}
   */
  beginTurn() {
    this._transition(SessionState.THINKING);
    this._generation = this._ids.next("gen");
    this._issued.add(this._generation);
    return this._generation;
  }

  /**
   * thinking -> speaking, for the named generation only.
   *
   * A superseded generation reaching this method is not an error the caller
   * needs to handle — it is exactly the race the fence exists for — so it
   * returns false rather than throwing.
   *
   * @param {GenerationId} generationId
   * @returns {boolean} whether the session is now speaking for that generation
   */
  beginSpeaking(generationId) {
    if (!this.accepts(generationId)) return false;
    this._transition(SessionState.SPEAKING);
    return true;
  }

  /**
   * The turn finished normally: speaking | thinking -> listening, and the
   * generation stops being live.
   *
   * @param {GenerationId} generationId
   * @returns {boolean} false if that generation had already been superseded
   */
  completeTurn(generationId) {
    if (!this.accepts(generationId)) return false;
    this._transition(SessionState.LISTENING);
    this._generation = null;
    return true;
  }

  /**
   * The user spoke over the agent. The live turn becomes stale immediately —
   * `accepts()` starts refusing it before any downstream work is torn down,
   * because output already in flight cannot be recalled, only discarded.
   *
   * @returns {GenerationId|null} the generation that was just superseded
   */
  interrupt() {
    const superseded = this._generation;
    this._transition(SessionState.INTERRUPTED);
    this._generation = null;
    return superseded;
  }

  /** End the session from any state. Idempotent. */
  close() {
    if (this.closed) return;
    this._apply(SessionState.CLOSED);
    this._generation = null;
  }

  /** @private */
  _transition(to) {
    if (!LEGAL[this._state].includes(to)) {
      throw new IllegalTransitionError(this._state, to);
    }
    this._apply(to);
  }

  /** @private */
  _apply(to) {
    const from = this._state;
    this._state = to;
    // Observers are notified after the change lands, so a handler that reads
    // back `session.state` sees the state it was told about.
    this._onStateChange({
      session: this._id,
      from,
      to,
      generation: this._generation,
      at: this._clock.now(),
    });
  }
}
