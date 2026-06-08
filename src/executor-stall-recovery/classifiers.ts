/**
 * Failure classifiers (Chain of Responsibility).
 * Seven classifiers, each owns ONE failure fingerprint; first match wins.
 * build_default_chain() assembles them; the chain falls back to UNKNOWN -> ABORT.
 */

import type { IFailureClassifier, IFailureClassifierChain } from "./interfaces";
import type { ExecutorFailure, FailureClassification } from "./models";
import { FailureKind, RecoveryAction } from "./models";

function createClassification(
  kind: FailureKind,
  retryable: boolean,
  action: RecoveryAction,
  evidence: string,
  name: string,
): FailureClassification {
  return {
    kind,
    retryable,
    recommended_action: action,
    evidence,
    classifier_name: name,
  };
}

class AllowlistClassifier implements IFailureClassifier {
  name = "allowlist";

  classify(failure: ExecutorFailure): FailureClassification | undefined {
    if (
      failure.status === 400 &&
      (failure.detail?.toLowerCase() || "").includes("allowlist")
    ) {
      return createClassification(
        FailureKind.ALLOWLIST_BLOCKED,
        false,
        RecoveryAction.ABORT,
        `executor rejected command (allowlist): ${failure.detail}`,
        this.name,
      );
    }
    return undefined;
  }
}

class ServerReloadClassifier implements IFailureClassifier {
  name = "server_reload";

  classify(failure: ExecutorFailure): FailureClassification | undefined {
    if (failure.status === 500) {
      return createClassification(
        FailureKind.SERVER_RELOAD_500,
        true,
        RecoveryAction.RETRY,
        `executor 500 (likely watchfiles reload): ${failure.detail}`,
        this.name,
      );
    }
    return undefined;
  }
}

class TimeoutClassifier implements IFailureClassifier {
  name = "timeout";

  classify(failure: ExecutorFailure): FailureClassification | undefined {
    const detail = (failure.detail || "").toLowerCase();
    if (failure.status === 408 || detail.includes("timed out")) {
      return createClassification(
        FailureKind.REQUEST_TIMEOUT,
        true,
        RecoveryAction.NARROW,
        `executor timed out — narrow the command: ${failure.detail}`,
        this.name,
      );
    }
    return undefined;
  }
}

class ExecutorDownClassifier implements IFailureClassifier {
  name = "executor_down";
  private readonly signatures = [
    "econnrefused",
    "connection refused",
    "connectionerror",
    "no route",
  ];

  classify(failure: ExecutorFailure): FailureClassification | undefined {
    const probe = (failure.transport_error || "").toLowerCase();
    if (probe && this.signatures.some((sig) => probe.includes(sig))) {
      return createClassification(
        FailureKind.EXECUTOR_DOWN,
        false,
        RecoveryAction.CIRCUIT_OPEN,
        `executor unreachable: ${failure.transport_error}`,
        this.name,
      );
    }
    return undefined;
  }
}

class EndTurnNoReturnClassifier implements IFailureClassifier {
  name = "end_turn_no_return";

  classify(failure: ExecutorFailure): FailureClassification | undefined {
    const detail = (failure.detail || "").toLowerCase();
    if (detail.includes("end_turn") && detail.includes("tool_return")) {
      return createClassification(
        FailureKind.END_TURN_NO_RETURN,
        true,
        RecoveryAction.FALLBACK,
        "server ended turn with no tool_return — run client-side fallback",
        this.name,
      );
    }
    return undefined;
  }
}

class PeerToolRuleClassifier implements IFailureClassifier {
  name = "peer_tool_rule";

  classify(failure: ExecutorFailure): FailureClassification | undefined {
    const detail = (failure.detail || "").toLowerCase();
    if (
      detail.includes("max_steps") &&
      (detail.includes("required_before_exit") ||
        detail.includes("send_message"))
    ) {
      return createClassification(
        FailureKind.PEER_TOOL_RULE_HANG,
        false,
        RecoveryAction.ABORT,
        "peer agent hung on an unsatisfiable tool rule — abort, do not retry",
        this.name,
      );
    }
    return undefined;
  }
}

class ResponseLostClassifier implements IFailureClassifier {
  /**
   * The tool likely RAN, but its tool_return was lost in transit (SSE/relay drop).
   * Verbatim Telegram fingerprint:
   *   "the response was lost during a tool workflow. Please try again."
   */
  name = "response_lost";
  private readonly signatures = [
    "response was lost",
    "response lost",
    "lost during a tool workflow",
    "lost the response",
    "tool_return lost",
    "lost tool_return",
    "result was dropped",
  ];

  classify(failure: ExecutorFailure): FailureClassification | undefined {
    const detail = (failure.detail || "").toLowerCase();
    if (this.signatures.some((sig) => detail.includes(sig))) {
      return createClassification(
        FailureKind.TOOL_RESPONSE_LOST,
        true,
        RecoveryAction.RESYNC,
        `tool likely executed but its tool_return was lost in transit — re-sync the result instead of re-running: ${failure.detail}`,
        this.name,
      );
    }
    return undefined;
  }
}

class FailureClassifierChain implements IFailureClassifierChain {
  private links: IFailureClassifier[];

  constructor(links: IFailureClassifier[]) {
    this.links = links;
  }

  classify(failure: ExecutorFailure): FailureClassification {
    for (const link of this.links) {
      const result = link.classify(failure);
      if (result) {
        return result;
      }
    }
    // Unmapped failures are NEVER silently retried.
    return createClassification(
      FailureKind.UNKNOWN,
      false,
      RecoveryAction.ABORT,
      `unclassified executor failure — aborting rather than blind-retrying: status=${failure.status} transport=${failure.transport_error} detail=${JSON.stringify(failure.detail)}`,
      "fallback",
    );
  }
}

export function buildDefaultChain(): FailureClassifierChain {
  return new FailureClassifierChain([
    new AllowlistClassifier(),
    new ServerReloadClassifier(),
    new TimeoutClassifier(),
    new ExecutorDownClassifier(),
    new EndTurnNoReturnClassifier(),
    new PeerToolRuleClassifier(),
    new ResponseLostClassifier(),
  ]);
}

export { FailureClassifierChain };
