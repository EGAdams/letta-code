import { abstractMethod } from "../../not-implemented.js";

/** Time and identity ports for a voice conversation. No browser globals here. */
export class Clock {
  now(): number {
    return abstractMethod("Clock.now");
  }
}

export class IdSource {
  next(_prefix?: string): string {
    return abstractMethod("IdSource.next");
  }
}

/** Deterministic clock for tests and simulations. */
export class ManualClock extends Clock {
  private time: number;

  constructor(start = 0) {
    super();
    this.time = start;
  }

  override now(): number {
    return this.time;
  }

  advance(ms: number): number {
    this.time += ms;
    return this.time;
  }

  set(ms: number): void {
    this.time = ms;
  }
}

/** Predictable identifiers make generation fences testable without randomness. */
export class SequentialIdSource extends IdSource {
  private counter: number;

  constructor(start = 1) {
    super();
    this.counter = start;
  }

  override next(prefix = "id"): string {
    const value = `${prefix}-${this.counter}`;
    this.counter += 1;
    return value;
  }
}
