/**
 * Ports for the stream inactivity watchdog.
 *
 * Everything the watchdog needs from the outside world — the clock and the
 * poll timer — is an injected interface, so the policy can be tested without
 * faking globals and without waiting real minutes.
 */

/** What a stream chunk proves about liveness. */
export type StreamActivityKind =
  /** The model is producing output (reasoning, assistant text, approvals). */
  | "content"
  /** A tool actually started or finished executing. */
  | "tool_progress";

/** Why the watchdog gave up on a run. */
export type InactivityReason =
  /** Nothing at all arrived — the stream is dead or the backend is wedged. */
  | "no_content"
  /** The model kept talking but never executed a tool — a planning loop. */
  | "no_tool_progress";

/** Time source. Injected so tests do not depend on wall-clock progress. */
export interface Clock {
  now(): number;
}

/** Cancels a running ticker. */
export type StopTicker = () => void;

/** Periodic callback source. Injected so tests can step time explicitly. */
export interface Ticker {
  start(intervalMs: number, onTick: () => void): StopTicker;
}

/**
 * The narrow half of the watchdog the chunk loop needs (ISP): the drain loop
 * only reports activity, it never starts, stops, or interrogates the policy.
 */
export interface ActivityRecorder {
  record(kind: StreamActivityKind): void;
}

/** The full lifecycle, used only by whoever owns the stream. */
export interface InactivityWatchdog extends ActivityRecorder {
  /** Begin watching. `onTimeout` fires at most once. */
  start(onTimeout: (reason: InactivityReason) => void): void;
  stop(): void;
  /** The reason this watchdog fired, or null if it never did. */
  firedReason(): InactivityReason | null;
}

/**
 * Two independent deadlines. `noContentMs` catches a dead stream quickly;
 * `noToolProgressMs` is the long backstop that still catches a model looping
 * forever in reasoning without ever calling a tool.
 */
export interface InactivityThresholds {
  readonly noContentMs: number;
  readonly noToolProgressMs: number;
  readonly pollIntervalMs: number;
}

export const DEFAULT_INACTIVITY_THRESHOLDS: InactivityThresholds = {
  noContentMs: 90_000,
  noToolProgressMs: 600_000,
  pollIntervalMs: 10_000,
};
