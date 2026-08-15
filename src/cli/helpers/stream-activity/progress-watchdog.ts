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

/** The state the policy decides from: two timestamps and whether a tool is running. */
export interface ActivityMarks {
  readonly lastContentMs: number;
  readonly lastToolProgressMs: number;
  /**
   * True between a `tool_call_message` and its `tool_return_message`. A tool
   * executing remotely produces no chunks, so this suspends the short
   * no-content deadline — otherwise a legitimately slow tool reads as a dead
   * stream and the run is killed mid-call.
   */
  readonly toolInFlight: boolean;
}

/**
 * The whole decision, as a pure function — no clock, no timer, no stream.
 *
 * A run is abandoned when the model has gone silent (`no_content`), when it
 * has been talking for a very long time without executing anything
 * (`no_tool_progress`), or when a dispatched tool never came back
 * (`stalled_tool`). Continuous reasoning keeps a run alive up to the long
 * deadline; it no longer trips the short one. Neither does a tool that is
 * still executing — but the long deadline stays armed as its backstop, so a
 * genuinely wedged tool is still caught.
 */
export function evaluateInactivity(
  now: number,
  marks: ActivityMarks,
  thresholds: InactivityThresholds,
): InactivityReason | null {
  const sinceToolProgress = now - marks.lastToolProgressMs;
  if (marks.toolInFlight) {
    // A tool is running: silence is expected, so only the stall budget applies.
    return sinceToolProgress > thresholds.stalledToolMs ? "stalled_tool" : null;
  }
  if (now - marks.lastContentMs > thresholds.noContentMs) {
    return "no_content";
  }
  if (sinceToolProgress > thresholds.noToolProgressMs) {
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
  /**
   * Tools outstanding right now. A counter rather than a flag because a turn
   * can dispatch several tool calls before any of them returns; the run is
   * only "idle" again once the last one is back. Clamped at zero so an
   * unmatched return (a replayed or out-of-order chunk) cannot make the
   * watchdog think fewer tools are running than actually are.
   */
  private toolsInFlight = 0;
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
    if (kind === "content") {
      return;
    }
    // Both ends of a tool call are real execution progress.
    this.lastToolProgressMs = now;
    this.toolsInFlight =
      kind === "tool_started"
        ? this.toolsInFlight + 1
        : Math.max(0, this.toolsInFlight - 1);
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
          toolInFlight: this.toolsInFlight > 0,
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
