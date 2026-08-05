import type { Clock, StopTicker, Ticker } from "./ports";

/** Real wall clock. The only place `Date.now()` is read for the watchdog. */
export const systemClock: Clock = {
  now: () => Date.now(),
};

/** Real timer. The only place `setInterval` is used for the watchdog. */
export const intervalTicker: Ticker = {
  start(intervalMs: number, onTick: () => void): StopTicker {
    const handle = setInterval(onTick, intervalMs);
    return () => {
      clearInterval(handle);
    };
  },
};
