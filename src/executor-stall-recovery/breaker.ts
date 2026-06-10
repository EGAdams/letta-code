/**
 * Circuit breaker — stops the 14x spin on a dead executor.
 * Counts CONSECUTIVE open-worthy failures (EXECUTOR_DOWN by default).
 */

import type { ICircuitBreaker } from "./interfaces";
import { FailureKind } from "./models";

// Failure kinds that indicate the executor service itself is unhealthy.
const OPEN_WORTHY = new Set([
  FailureKind.EXECUTOR_DOWN,
  FailureKind.SERVER_RELOAD_500,
]);

export class CircuitBreaker implements ICircuitBreaker {
  private threshold: number;
  private resetAfterMs: number;
  private consecutive: number = 0;
  private openedAt: number | null = null;

  constructor(threshold: number = 2, resetAfterMs: number = 30000) {
    this.threshold = threshold;
    this.resetAfterMs = resetAfterMs;
  }

  private now(): number {
    return Date.now();
  }

  allow(): boolean {
    if (this.openedAt === null) {
      return true;
    }
    // Half-open after the cooldown: allow a single probe.
    if (this.now() - this.openedAt >= this.resetAfterMs) {
      this.openedAt = null;
      this.consecutive = 0;
      return true;
    }
    return false;
  }

  record_success(): void {
    this.consecutive = 0;
    this.openedAt = null;
  }

  record_failure(kind: FailureKind): void {
    if (!OPEN_WORTHY.has(kind)) {
      // Non-infra failures don't latch the breaker.
      this.consecutive = 0;
      return;
    }
    this.consecutive += 1;
    if (this.consecutive >= this.threshold) {
      this.openedAt = this.now();
    }
  }
}
