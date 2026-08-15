import {
  DEFAULT_INACTIVITY_THRESHOLDS,
  type InactivityReason,
  type InactivityThresholds,
} from "./ports";

function describeDuration(ms: number): string {
  if (ms >= 60_000 && ms % 60_000 === 0) {
    const minutes = ms / 60_000;
    return `${minutes} minute${minutes === 1 ? "" : "s"}`;
  }
  const seconds = Math.round(ms / 1000);
  return `${seconds} second${seconds === 1 ? "" : "s"}`;
}

function describeCause(
  reason: InactivityReason,
  thresholds: InactivityThresholds,
): string {
  return reason === "no_content"
    ? `Stopped after ${describeDuration(thresholds.noContentMs)} without a response from the model.`
    : `Stopped after ${describeDuration(thresholds.noToolProgressMs)} of reasoning without running a tool.`;
}

/**
 * The user-facing text for a watchdog stop.
 *
 * Pure and separately testable so the TUI does not embed timing policy in a
 * string literal — the numbers come from the thresholds that actually fired.
 */
export function inactivityStopMessage(
  reason: InactivityReason,
  backendCancelSucceeded: boolean,
  thresholds: InactivityThresholds = DEFAULT_INACTIVITY_THRESHOLDS,
): string {
  const cause = describeCause(reason, thresholds);
  return backendCancelSucceeded
    ? `${cause} The backend run was cancelled, so this conversation is ready for another message.`
    : `${cause} Backend cancellation could not be confirmed — start a new conversation with \`letta --new\` if this conversation remains busy.`;
}
