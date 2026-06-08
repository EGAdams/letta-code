/**
 * Domain models & enums (Command + value objects).
 * TypeScript port of scissari_executor Python package models.
 */

export enum FailureKind {
  ALLOWLIST_BLOCKED = "allowlist_blocked", // F1  HTTP 400
  SERVER_RELOAD_500 = "server_reload_500", // F2  HTTP 500 watchfiles loop
  REQUEST_TIMEOUT = "request_timeout", // F3  HTTP 408
  EXECUTOR_DOWN = "executor_down", // F4  ECONNREFUSED / no process
  END_TURN_NO_RETURN = "end_turn_no_return", // F5  tool_call then end_turn, no tool_return
  PEER_TOOL_RULE_HANG = "peer_tool_rule_hang", // F6  peer agent max_steps from bad tool_rule
  TOOL_RESPONSE_LOST = "tool_response_lost", // F7  tool_return produced but lost in transit
  UNKNOWN = "unknown", // never silently retried — always aborts
}

export enum RecoveryAction {
  RETRY = "retry", // safe, after backoff
  NARROW = "narrow", // retry only with a tightened command
  FALLBACK = "fallback", // run client-side (F5)
  RESYNC = "resync", // re-fetch the already-produced result, do NOT re-execute (F7)
  ABORT = "abort", // stop now; retrying cannot help
  CIRCUIT_OPEN = "circuit_open", // service dead; stop and alert ops
}

export enum TurnState {
  RUNNING = "running",
  RECOVERING = "recovering",
  RESOLVED = "resolved",
  TRIPPED = "tripped", // replaces the old "reset at 14"
}

export interface ExecutorCommand {
  cmd: string;
  cwd?: string;
  timeout_s?: number;
  allowlist_key?: string;
}

export function fingerprintCommand(cmd: ExecutorCommand): string {
  // Stable hash for de-dup / repetition detection.
  // Identical (cmd, cwd) pairs collapse to the same fingerprint so the
  // LoopGuard can detect a command being retried verbatim — the exact
  // pattern behind the 14-call spin.
  const { createHash } = require("crypto");
  const basis = `${cmd.cmd}\0${cmd.cwd || ""}`;
  return createHash("sha256").update(basis, "utf8").digest("hex").slice(0, 16);
}

export interface ExecutorResponse {
  ok: boolean;
  status: number;
  stdout?: string;
  stderr?: string;
  duration_s?: number;
}

export interface ExecutorFailure {
  status?: number; // HTTP status if any
  transport_error?: string; // e.g. "ECONNREFUSED"
  detail?: string; // server 'detail' body
  raw?: Record<string, unknown>;
}

export interface FailureClassification {
  kind: FailureKind;
  retryable: boolean;
  recommended_action: RecoveryAction;
  evidence: string; // human-readable WHY (fixes "no error captured")
  classifier_name: string;
}

export interface RecoveryOutcome {
  action: RecoveryAction;
  backoff_ms?: number;
  next_command?: ExecutorCommand; // set when NARROW/FALLBACK
  reason?: string;
  kind?: FailureKind; // source classification (for budget + reporting)
}

export interface GuardVerdict {
  state: TurnState;
  should_continue: boolean;
  calls_used: number;
  budget_for_kind?: number;
  snapshot_id?: string; // set when state == TRIPPED
}

export interface StallReport {
  agent_id: string;
  classification?: FailureClassification;
  calls_used?: number;
  final_state?: TurnState;
  snapshot_id?: string;
  message: string;
}

export class ExecutorFailureError extends Error {
  failure: ExecutorFailure;

  constructor(failure: ExecutorFailure) {
    super(failure.detail || failure.transport_error || "executor failure");
    this.failure = failure;
    this.name = "ExecutorFailureError";
  }
}
