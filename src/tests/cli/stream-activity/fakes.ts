import type {
  Clock,
  StopTicker,
  Ticker,
} from "../../../cli/helpers/stream-activity";

/** Clock the test moves by hand. */
export class FakeClock implements Clock {
  constructor(private current = 1_800_000_000_000) {}

  now(): number {
    return this.current;
  }

  advance(ms: number): void {
    this.current += ms;
  }
}

/** Ticker that never fires on its own — the test decides when a poll happens. */
export class ManualTicker implements Ticker {
  private callbacks = new Set<() => void>();
  intervals: number[] = [];

  start(intervalMs: number, onTick: () => void): StopTicker {
    this.intervals.push(intervalMs);
    this.callbacks.add(onTick);
    return () => {
      this.callbacks.delete(onTick);
    };
  }

  /** Run one poll of every live ticker. */
  tick(): void {
    for (const cb of [...this.callbacks]) {
      cb();
    }
  }

  get running(): number {
    return this.callbacks.size;
  }
}
