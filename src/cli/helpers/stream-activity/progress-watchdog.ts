import {
  type Clock,
  DEFAULT_INACTIVITY_THRESHOLDS,
  type InactivityReason,
  type InactivityThresholds,
  type InactivityWatchdog,
  type StopTicker,
  type StreamActivityKind,
  type Ticker,
} from "./ports";

/** The two timestamps the policy decides from. */
export interface ActivityMarks {
  readonly lastContentMs: number;
  readonly lastToolProgressMs: number;
}

/**
 * The whole decision, as a pure function — no clock, no timer, no stream.
 *
 * A run is abandoned when the model has gone silent (`no_content`) or when it
 * has been talking for a very long time without executing anything
 * (`no_tool_progress`). Continuous reasoning keeps a run alive up to the long
 * deadline; it no longer trips the short one.
 */
export function evaluateInactivity(
  now: number,
  marks: ActivityMarks,
  thresholds: InactivityThresholds,
): InactivityReason | null {
  if (now - marks.lastContentMs > thresholds.noContentMs) {
    return "no_content";
  }
  if (now - marks.lastToolProgressMs > thresholds.noToolProgressMs) {
    return "no_tool_progress";
  }
  return null;
}

export interface ProgressWatchdogDeps {
  readonly clock: Clock;
  readonly ticker: Ticker;
  readonly thresholds?: InactivityThresholds;
}

/**
 * Tracks stream liveness and fires once when a deadline passes.
 *
 * Its only responsibility is the deadline. It does not know about HTTP
 * streams, abort controllers, or the UI — the caller decides what a timeout
 * means (SRP).
 */
export class ProgressWatchdog implements InactivityWatchdog {
  private readonly clock: Clock;
  private readonly ticker: Ticker;
  private readonly thresholds: InactivityThresholds;

  private lastContentMs: number;
  private lastToolProgressMs: number;
  private stopTicker: StopTicker | null = null;
  private fired: InactivityReason | null = null;

  constructor(deps: ProgressWatchdogDeps) {
    this.clock = deps.clock;
    this.ticker = deps.ticker;
    this.thresholds = deps.thresholds ?? DEFAULT_INACTIVITY_THRESHOLDS;
    const startedAt = this.clock.now();
    this.lastContentMs = startedAt;
    this.lastToolProgressMs = startedAt;
  }

  record(kind: StreamActivityKind): void {
    const now = this.clock.now();
    this.lastContentMs = now;
    if (kind === "tool_progress") {
      this.lastToolProgressMs = now;
    }
  }

  start(onTimeout: (reason: InactivityReason) => void): void {
    if (this.stopTicker) {
      return;
    }
    this.stopTicker = this.ticker.start(this.thresholds.pollIntervalMs, () => {
      if (this.fired) {
        return;
      }
      const reason = evaluateInactivity(
        this.clock.now(),
        {
          lastContentMs: this.lastContentMs,
          lastToolProgressMs: this.lastToolProgressMs,
        },
        this.thresholds,
      );
      if (!reason) {
        return;
      }
      this.fired = reason;
      this.stop();
      onTimeout(reason);
    });
  }

  stop(): void {
    this.stopTicker?.();
    this.stopTicker = null;
  }

  firedReason(): InactivityReason | null {
    return this.fired;
  }
}
