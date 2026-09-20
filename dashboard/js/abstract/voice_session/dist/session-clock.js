import { abstractMethod } from "../../not-implemented.js";
/** Time and identity ports for a voice conversation. No browser globals here. */
export class Clock {
  now() {
    return abstractMethod("Clock.now");
  }
}
export class IdSource {
  next(_prefix) {
    return abstractMethod("IdSource.next");
  }
}
/** Deterministic clock for tests and simulations. */
export class ManualClock extends Clock {
  time;
  constructor(start = 0) {
    super();
    this.time = start;
  }
  now() {
    return this.time;
  }
  advance(ms) {
    this.time += ms;
    return this.time;
  }
  set(ms) {
    this.time = ms;
  }
}
/** Predictable identifiers make generation fences testable without randomness. */
export class SequentialIdSource extends IdSource {
  counter;
  constructor(start = 1) {
    super();
    this.counter = start;
  }
  next(prefix = "id") {
    const value = `${prefix}-${this.counter}`;
    this.counter += 1;
    return value;
  }
}
