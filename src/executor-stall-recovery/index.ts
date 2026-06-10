/**
 * Executor stall recovery system - TypeScript port of scissari_executor
 * Replaces blind 14-call retry with classified failure detection & strategy-driven recovery
 */

export { CircuitBreaker } from "./breaker";
// Implementations
export { buildDefaultChain, FailureClassifierChain } from "./classifiers";
export { LoopGuard } from "./guard";
// Interfaces
export type {
  IAlertSink,
  ICircuitBreaker,
  IConversationSnapshotStore,
  IExecutorClient,
  IExecutorRunService,
  IFailureClassifier,
  IFailureClassifierChain,
  ILoopGuard,
  IRecoveryStrategy,
  IRecoveryStrategyFactory,
} from "./interfaces";
export type {
  ExecutorCommand,
  ExecutorFailure,
  ExecutorResponse,
  FailureClassification,
  GuardVerdict,
  RecoveryOutcome,
  StallReport,
} from "./models";
// Models & types
export {
  ExecutorFailureError,
  FailureKind,
  fingerprintCommand,
  RecoveryAction,
  TurnState,
} from "./models";
export { ExecutorRunService, StalledError } from "./service";
export { StrategyFactory } from "./strategies";
