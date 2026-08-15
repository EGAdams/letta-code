import type { InactivityThresholds, InactivityWatchdog } from "./ports";
import { ProgressWatchdog } from "./progress-watchdog";
import { intervalTicker, systemClock } from "./system-adapters";

export { classifyStreamActivity } from "./activity-classifier";
export { inactivityStopMessage } from "./inactivity-message";
export {
  type ActivityRecorder,
  type Clock,
  DEFAULT_INACTIVITY_THRESHOLDS,
  type InactivityReason,
  type InactivityThresholds,
  type InactivityWatchdog,
  type StopTicker,
  type StreamActivityKind,
  type Ticker,
} from "./ports";
export {
  type ActivityMarks,
  evaluateInactivity,
  ProgressWatchdog,
} from "./progress-watchdog";
export { intervalTicker, systemClock } from "./system-adapters";

/**
 * Composition root for the default watchdog: the only place the real clock and
 * the real timer are bound to the policy.
 */
export function createProgressWatchdog(
  thresholds?: InactivityThresholds,
): InactivityWatchdog {
  return new ProgressWatchdog({
    clock: systemClock,
    ticker: intervalTicker,
    ...(thresholds ? { thresholds } : {}),
  });
}
