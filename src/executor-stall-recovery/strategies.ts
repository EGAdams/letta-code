/**
 * Recovery strategies (Strategy + Template Method + Factory).
 * BaseRecoveryStrategy.recover() is the fixed skeleton; subclasses fill _decide().
 */

import type { IRecoveryStrategy, IRecoveryStrategyFactory } from "./interfaces";
import type {
  ExecutorCommand,
  FailureClassification,
  RecoveryOutcome,
} from "./models";
import { FailureKind, RecoveryAction } from "./models";

abstract class BaseRecoveryStrategy implements IRecoveryStrategy {
  abstract handles: FailureKind;

  async recover(
    cmd: ExecutorCommand,
    classification: FailureClassification,
  ): Promise<RecoveryOutcome> {
    if (!classification.retryable) {
      // Honor the classifier's recommended terminal action (ABORT or CIRCUIT_OPEN).
      const action = [
        RecoveryAction.ABORT,
        RecoveryAction.CIRCUIT_OPEN,
      ].includes(classification.recommended_action)
        ? classification.recommended_action
        : RecoveryAction.ABORT;

      return {
        action,
        reason: classification.evidence,
      };
    }
    return this._decide(cmd, classification);
  }

  protected abstract _decide(
    cmd: ExecutorCommand,
    c: FailureClassification,
  ): Promise<RecoveryOutcome>;
}

class AllowlistAbortStrategy extends BaseRecoveryStrategy {
  handles = FailureKind.ALLOWLIST_BLOCKED;

  protected async _decide(
    cmd: ExecutorCommand,
    c: FailureClassification,
  ): Promise<RecoveryOutcome> {
    return { action: RecoveryAction.ABORT, reason: c.evidence };
  }
}

class BackoffRetryStrategy extends BaseRecoveryStrategy {
  handles = FailureKind.SERVER_RELOAD_500;

  protected async _decide(
    cmd: ExecutorCommand,
    c: FailureClassification,
  ): Promise<RecoveryOutcome> {
    return {
      action: RecoveryAction.RETRY,
      backoff_ms: 1500,
      reason: "executor reloading — backing off before one retry",
    };
  }
}

class NarrowCommandStrategy extends BaseRecoveryStrategy {
  handles = FailureKind.REQUEST_TIMEOUT;

  protected async _decide(
    cmd: ExecutorCommand,
    c: FailureClassification,
  ): Promise<RecoveryOutcome> {
    // Halve the timeout so a verbatim re-run is impossible (defeats the spin).
    const narrowed: ExecutorCommand = {
      ...cmd,
      timeout_s: Math.max(5.0, (cmd.timeout_s || 60) / 2),
    };
    return {
      action: RecoveryAction.NARROW,
      next_command: narrowed,
      reason: "timeout — retrying once with a tightened command/timeout",
    };
  }
}

class ClientSideFallbackStrategy extends BaseRecoveryStrategy {
  handles = FailureKind.END_TURN_NO_RETURN;

  protected async _decide(
    cmd: ExecutorCommand,
    c: FailureClassification,
  ): Promise<RecoveryOutcome> {
    return {
      action: RecoveryAction.FALLBACK,
      next_command: cmd,
      reason: "server omitted tool_return — execute client-side",
    };
  }
}

class ResyncStrategy extends BaseRecoveryStrategy {
  handles = FailureKind.TOOL_RESPONSE_LOST;

  protected async _decide(
    cmd: ExecutorCommand,
    c: FailureClassification,
  ): Promise<RecoveryOutcome> {
    // The tool likely already ran; re-fetch its result rather than re-execute.
    return {
      action: RecoveryAction.RESYNC,
      next_command: cmd,
      backoff_ms: 500,
      reason: "tool_return lost in transit — re-syncing the result once",
    };
  }
}

class CircuitOpenStrategy extends BaseRecoveryStrategy {
  handles = FailureKind.EXECUTOR_DOWN;

  protected async _decide(
    cmd: ExecutorCommand,
    c: FailureClassification,
  ): Promise<RecoveryOutcome> {
    return { action: RecoveryAction.CIRCUIT_OPEN, reason: c.evidence };
  }
}

class PeerToolRuleAbortStrategy extends BaseRecoveryStrategy {
  handles = FailureKind.PEER_TOOL_RULE_HANG;

  protected async _decide(
    cmd: ExecutorCommand,
    c: FailureClassification,
  ): Promise<RecoveryOutcome> {
    return { action: RecoveryAction.ABORT, reason: c.evidence };
  }
}

class AbortStrategy extends BaseRecoveryStrategy {
  handles = FailureKind.UNKNOWN;

  protected async _decide(
    cmd: ExecutorCommand,
    c: FailureClassification,
  ): Promise<RecoveryOutcome> {
    return { action: RecoveryAction.ABORT, reason: c.evidence };
  }
}

export class StrategyFactory implements IRecoveryStrategyFactory {
  private registry: Map<FailureKind, IRecoveryStrategy>;

  constructor() {
    const strategies: BaseRecoveryStrategy[] = [
      new AllowlistAbortStrategy(),
      new BackoffRetryStrategy(),
      new NarrowCommandStrategy(),
      new ClientSideFallbackStrategy(),
      new ResyncStrategy(),
      new CircuitOpenStrategy(),
      new PeerToolRuleAbortStrategy(),
      new AbortStrategy(),
    ];
    this.registry = new Map(strategies.map((s) => [s.handles, s]));
  }

  for_kind(kind: FailureKind): IRecoveryStrategy {
    return this.registry.get(kind) || this.registry.get(FailureKind.UNKNOWN)!;
  }
}
