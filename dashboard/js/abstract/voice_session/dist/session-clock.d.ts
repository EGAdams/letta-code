/** Time and identity ports for a voice conversation. No browser globals here. */
export declare class Clock {
  now(): number;
}
export declare class IdSource {
  next(_prefix?: string): string;
}
/** Deterministic clock for tests and simulations. */
export declare class ManualClock extends Clock {
  private time;
  constructor(start?: number);
  now(): number;
  advance(ms: number): number;
  set(ms: number): void;
}
/** Predictable identifiers make generation fences testable without randomness. */
export declare class SequentialIdSource extends IdSource {
  private counter;
  constructor(start?: number);
  next(prefix?: string): string;
}
