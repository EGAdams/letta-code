/**
 * Ports / interfaces — program to THESE, inject implementations.
 * TypeScript port of scissari_executor Python interfaces.
 */

import type {
  ExecutorCommand,
  ExecutorFailure,
  ExecutorResponse,
  FailureClassification,
  FailureKind,
  GuardVerdict,
  RecoveryOutcome,
  StallReport,
} from "./models";

/**
 * Adapter over the HTTP executor service (uvicorn @ 127.0.0.1:8787).
 */
export interface IExecutorClient {
  run(cmd: ExecutorCommand): Promise<ExecutorResponse>;
}

/**
 * One link in the Chain of Responsibility. Returns undefined to defer to the next link.
 */
export interface IFailureClassifier {
  name: string;
  classify(failure: ExecutorFailure): FailureClassification | undefined;
}

/**
 * Chain of Responsibility classifier.
 */
export interface IFailureClassifierChain {
  classify(failure: ExecutorFailure): FailureClassification;
}

/**
 * Strategy — decides what to do about one classified failure.
 */
export interface IRecoveryStrategy {
  handles: FailureKind;
  recover(
    cmd: ExecutorCommand,
    classification: FailureClassification,
  ): Promise<RecoveryOutcome>;
}

/**
 * Factory for creating recovery strategies per failure kind.
 */
export interface IRecoveryStrategyFactory {
  for_kind(kind: FailureKind): IRecoveryStrategy;
}

/**
 * Circuit breaker — kills the 14x spin on repeated EXECUTOR_DOWN.
 */
export interface ICircuitBreaker {
  allow(): boolean;
  record_success(): void;
  record_failure(kind: FailureKind): void;
}

/**
 * State machine that replaces the blind `count < 14` counter.
 */
export interface ILoopGuard {
  register(cmd: ExecutorCommand, outcome: RecoveryOutcome): GuardVerdict;
  reset(): void;
}

/**
 * Memento store — snapshot before any TRIPPED reset.
 */
export interface IConversationSnapshotStore {
  capture(
    agent_id: string,
    transcript: Record<string, unknown>[],
  ): Promise<string>;
  restore(snapshot_id: string): Promise<Record<string, unknown>[]>;
}

/**
 * Observer — Telegram, scissari-alerts.jsonl, dashboard LED all implement this.
 */
export interface IAlertSink {
  emit(report: StallReport): Promise<void>;
}

/**
 * Facade — the ONLY thing Scissari's turn loop calls.
 */
export interface IExecutorRunService {
  execute(cmd: ExecutorCommand, agent_id: string): Promise<ExecutorResponse>;
}
