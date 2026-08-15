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
  /** A tool call was dispatched; it is now executing. */
  | "tool_started"
  /** A tool finished executing and returned. */
  | "tool_finished";

/** Why the watchdog gave up on a run. */
export type InactivityReason =
  /** Nothing at all arrived — the stream is dead or the backend is wedged. */
  | "no_content"
  /** The model kept talking but never executed a tool — a planning loop. */
  | "no_tool_progress"
  /** A tool was dispatched and never returned — the tool itself is wedged. */
  | "stalled_tool";

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
 * Three independent deadlines, one per way a run can die.
 *
 * `noContentMs` catches a dead stream quickly, but is deliberately suspended
 * while a tool is executing: a long tool (e.g. `run_claude_code_sdk`, which
 * runs a whole nested Claude session on a remote executor) emits nothing at
 * all for minutes, and that silence is the tool working, not the stream dying.
 *
 * `noToolProgressMs` catches a model looping forever in reasoning without ever
 * calling a tool. `stalledToolMs` catches a tool that was dispatched and never
 * came back. These are separate numbers because they bound different things:
 * the first is a model-behaviour budget, the second must clear the slowest
 * legitimate tool round trip the surrounding stack permits. The executor's
 * mcp-proxy allows 900s per call (`start_executor_server.sh --requestTimeout`)
 * with real calls observed at 480s, so a shared 600s would have cut off calls
 * the rest of the stack considers perfectly healthy.
 */
export interface InactivityThresholds {
  readonly noContentMs: number;
  readonly noToolProgressMs: number;
  readonly stalledToolMs: number;
  readonly pollIntervalMs: number;
}

export const DEFAULT_INACTIVITY_THRESHOLDS: InactivityThresholds = {
  noContentMs: 90_000,
  noToolProgressMs: 600_000,
  // Matches mcp-proxy's 900s per-request ceiling; past this the tool is gone,
  // not slow — nothing downstream is still waiting on it.
  stalledToolMs: 900_000,
  pollIntervalMs: 10_000,
};
