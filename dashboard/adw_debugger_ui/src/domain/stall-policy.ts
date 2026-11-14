// Strategy: when an executing phase counts as stalled.
//
// An explicit wait is judged by its own deadline; anything else by how long ago
// the phase last made progress. Only that phase's own events move either mark,
// so another phase's activity or a feed keepalive cannot hide a stall.
import type { IStallPolicy, StallInput, StallVerdict } from "../contracts";

function seconds(ms: number): string {
  return `${Math.max(0, Math.round(ms / 1000))}s`;
}

export class ProgressTimeoutStallPolicy implements IStallPolicy {
  evaluate(
    phase: StallInput,
    nowMs: number,
    timeoutMs: number,
  ): StallVerdict | null {
    if (!phase.started || phase.terminal) return null;
    if (phase.waitDeadlineAt !== null) {
      const late = nowMs - phase.waitDeadlineAt;
      return late > 0
        ? {
            reason: `wait deadline passed ${seconds(late)} ago: ${phase.waitReason}`,
          }
        : null;
    }
    const quiet = nowMs - phase.lastProgressAt;
    return quiet > timeoutMs
      ? {
          reason: `no progress for ${seconds(quiet)} (timeout ${seconds(timeoutMs)})`,
        }
      : null;
  }
}
