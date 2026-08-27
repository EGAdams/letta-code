/**
 * The two primitives a lifecycle object is not allowed to reach for directly:
 * "what time is it" and "give me a new id".
 *
 * VoiceSession stamps every generation with a time and an id. If it called
 * `Date.now()` and `crypto.randomUUID()` itself, its tests would need sleeps
 * and could never assert on an id — so both are ports, and the deterministic
 * implementations below are the ones tests use.
 *
 * The real, global-backed implementations live in
 * `js/implementation/system-session-primitives.js`, per the directory rule that
 * `abstract/` never touches globals.
 */
import { abstractMethod } from "./not-implemented.js";

/** A source of the current time, in milliseconds since the epoch. */
export class Clock {
  /** @returns {number} */
  now() {
    return abstractMethod("Clock.now");
  }
}

/** A source of unique, opaque identifiers. */
export class IdSource {
  /** @param {string} [prefix] @returns {string} */
  next(_prefix) {
    return abstractMethod("IdSource.next");
  }
}

/**
 * A clock the test drives by hand.
 *
 * Nothing in the session waits on wall-clock time, so a test never needs to
 * sleep — it advances the clock and asserts on the stamps that came out.
 */
export class ManualClock extends Clock {
  constructor(start = 0) {
    super();
    this._now = start;
  }
  now() {
    return this._now;
  }
  /** @param {number} ms @returns {number} the new time */
  advance(ms) {
    this._now += ms;
    return this._now;
  }
  /** @param {number} ms */
  set(ms) {
    this._now = ms;
  }
}

/**
 * Ids that count up: `gen-1`, `gen-2`, ...
 *
 * Predictable ids are the whole reason generation fencing is testable — an
 * assertion can name the generation it expects to be rejected.
 */
export class SequentialIdSource extends IdSource {
  constructor(start = 1) {
    super();
    this._n = start;
  }
  next(prefix = "id") {
    const value = `${prefix}-${this._n}`;
    this._n += 1;
    return value;
  }
}
