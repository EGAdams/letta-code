/**
 * ExecutorRunService (Facade).
 * The ONLY entry point the bot's turn loop calls. Orchestrates all recovery logic.
 */

import { CircuitBreaker } from "./breaker";
import { buildDefaultChain } from "./classifiers";
import { LoopGuard } from "./guard";
import type {
  IAlertSink,
  ICircuitBreaker,
  IConversationSnapshotStore,
  IExecutorClient,
  IExecutorRunService,
  IFailureClassifierChain,
  ILoopGuard,
  IRecoveryStrategyFactory,
} from "./interfaces";
import type {
  ExecutorCommand,
  ExecutorResponse,
  FailureClassification,
  GuardVerdict,
  RecoveryOutcome,
} from "./models";
import {
  ExecutorFailureError,
  FailureKind,
  RecoveryAction,
  type StallReport,
  TurnState,
} from "./models";
import { StrategyFactory } from "./strategies";

// Hard ceiling so a logic bug can never reproduce the original infinite spin.
const ABSOLUTE_MAX_ATTEMPTS = 6;

export class StalledError extends Error {
  report: StallReport;

  constructor(report: StallReport) {
    super(report.message);
    this.name = "StalledError";
    this.report = report;
  }
}

export class ExecutorRunService implements IExecutorRunService {
  private client: IExecutorClient;
  private alertSink: IAlertSink;
  private classifier: IFailureClassifierChain;
  private factory: IRecoveryStrategyFactory;
  private guard: ILoopGuard;
  private breaker: ICircuitBreaker;
  private snapshots: IConversationSnapshotStore | null;
  private sleepFn: (ms: number) => Promise<void>;

  constructor(
    client: IExecutorClient,
    alertSink: IAlertSink,
    classifier?: IFailureClassifierChain,
    factory?: IRecoveryStrategyFactory,
    guard?: ILoopGuard,
    breaker?: ICircuitBreaker,
    snapshotStore?: IConversationSnapshotStore,
    sleepFn?: (ms: number) => Promise<void>,
  ) {
    this.client = client;
    this.alertSink = alertSink;
    this.classifier = classifier || buildDefaultChain();
    this.factory = factory || new StrategyFactory();
    this.guard = guard || new LoopGuard(undefined, snapshotStore);
    this.breaker = breaker || new CircuitBreaker();
    this.snapshots = snapshotStore || null;
    this.sleepFn =
      sleepFn || ((ms) => new Promise((resolve) => setTimeout(resolve, ms)));
  }

  private async stall(
    agentId: string,
    classification: FailureClassification | null,
    verdict: GuardVerdict | null,
    note: string,
  ): Promise<StalledError> {
    const report: StallReport = {
      agent_id: agentId,
      classification: classification || undefined,
      calls_used: verdict?.calls_used || 0,
      final_state: verdict?.state || TurnState.TRIPPED,
      snapshot_id: verdict?.snapshot_id,
      // The fix: a concrete, classified reason — never "no error captured".
      message:
        `executor_run could not complete: ${note}` +
        (classification ? ` — ${classification.evidence}` : ""),
    };
    await this.alertSink.emit(report);
    return new StalledError(report);
  }

  async execute(
    cmd: ExecutorCommand,
    agentId: string,
  ): Promise<ExecutorResponse> {
    let current = cmd;

    for (let attempt = 0; attempt < ABSOLUTE_MAX_ATTEMPTS; attempt++) {
      // Circuit breaker: don't even touch a service we believe is dead.
      if (!this.breaker.allow()) {
        const classification: FailureClassification = {
          kind: FailureKind.EXECUTOR_DOWN,
          retryable: false,
          recommended_action: RecoveryAction.CIRCUIT_OPEN,
          evidence: "circuit open — executor presumed down",
          classifier_name: "circuit_breaker",
        };
        const verdict = this.guard.register(current, {
          action: RecoveryAction.CIRCUIT_OPEN,
          kind: classification.kind,
          reason: "circuit open",
        });
        throw await this.stall(
          agentId,
          classification,
          verdict,
          "circuit open",
        );
      }

      try {
        const response = await this.client.run(current);
        this.breaker.record_success();
        return response;
      } catch (error) {
        if (!(error instanceof ExecutorFailureError)) {
          throw error;
        }

        const classification = this.classifier.classify(error.failure);
        this.breaker.record_failure(classification.kind);

        const strategy = this.factory.for_kind(classification.kind);
        const outcome = await strategy.recover(current, classification);
        outcome.kind = classification.kind; // tag for guard budget + reporting

        const verdict = this.guard.register(current, outcome);

        // Terminal action or guard tripped -> stop and alert with a reason.
        if (
          [RecoveryAction.ABORT, RecoveryAction.CIRCUIT_OPEN].includes(
            outcome.action,
          ) ||
          !verdict.should_continue
        ) {
          throw await this.stall(
            agentId,
            classification,
            verdict,
            outcome.action,
          );
        }

        // Retry-ish: honor backoff, advance the command, loop again.
        if (outcome.backoff_ms) {
          await this.sleepFn(outcome.backoff_ms);
        }
        current = outcome.next_command || current;
      }
    }

    // Defensive: absolute attempt ceiling reached (should be unreachable).
    throw await this.stall(agentId, null, null, "attempt ceiling reached");
  }
}
