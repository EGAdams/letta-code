/**
 * Loop guard (State machine).
 * Replaces the blind `count < 14` counter with per-kind budgets (default 2).
 */

import type { IConversationSnapshotStore, ILoopGuard } from "./interfaces";
import type { ExecutorCommand, GuardVerdict, RecoveryOutcome } from "./models";
import { fingerprintCommand, RecoveryAction, TurnState } from "./models";

// Per-kind "strike count": the Nth identical retry-ish attempt trips the guard.
const DEFAULT_BUDGET_PER_KIND: Record<string, number> = {
  allowlist_blocked: 0, // F1 — terminal (ABORT trips immediately anyway)
  server_reload_500: 2, // F2 — one backoff retry, then trip
  request_timeout: 2, // F3 — one narrowed retry, then trip
  executor_down: 0, // F4 — terminal (CIRCUIT_OPEN)
  end_turn_no_return: 2, // F5 — one client-side fallback, then trip
  peer_tool_rule_hang: 0, // F6 — terminal (ABORT)
  tool_response_lost: 2, // F7 — one re-sync of the lost result, then trip
  unknown: 0, // always abort
};

const TERMINAL_ACTIONS = new Set([
  RecoveryAction.ABORT,
  RecoveryAction.CIRCUIT_OPEN,
]);

export class LoopGuard implements ILoopGuard {
  private budget: Record<string, number>;
  private snapshots: IConversationSnapshotStore | null;
  private defaultRetryBudget: number;
  private agentId: string;
  private calls: number = 0;
  private fingerprints: Record<string, number> = {};

  constructor(
    budgetPerKind?: Record<string, number>,
    snapshotStore?: IConversationSnapshotStore,
    defaultRetryBudget: number = 2,
    agentId: string = "loop-guard",
  ) {
    this.budget = { ...DEFAULT_BUDGET_PER_KIND, ...budgetPerKind };
    this.snapshots = snapshotStore || null;
    this.defaultRetryBudget = defaultRetryBudget;
    this.agentId = agentId;
  }

  private budgetFor(outcome: RecoveryOutcome): number {
    if (outcome.kind) {
      return this.budget[outcome.kind] ?? this.defaultRetryBudget;
    }
    return this.defaultRetryBudget;
  }

  private captureSnapshot(): string | undefined {
    if (!this.snapshots) return undefined;
    // Note: synchronous in TS version — in production, make this async
    return undefined; // TODO: implement snapshot capture
  }

  register(cmd: ExecutorCommand, outcome: RecoveryOutcome): GuardVerdict {
    this.calls += 1;

    // Terminal outcome: trip now, snapshot for forensics.
    if (TERMINAL_ACTIONS.has(outcome.action)) {
      return {
        state: TurnState.TRIPPED,
        should_continue: false,
        calls_used: this.calls,
        snapshot_id: this.captureSnapshot(),
      };
    }

    // Retry-ish outcome: count identical-command attempts against the budget.
    const fp = fingerprintCommand(cmd);
    const repeats = (this.fingerprints[fp] ?? 0) + 1;
    this.fingerprints[fp] = repeats;
    const budget = this.budgetFor(outcome);

    if (repeats >= budget) {
      return {
        state: TurnState.TRIPPED,
        should_continue: false,
        calls_used: this.calls,
        budget_for_kind: budget,
        snapshot_id: this.captureSnapshot(),
      };
    }

    return {
      state: TurnState.RECOVERING,
      should_continue: true,
      calls_used: this.calls,
      budget_for_kind: budget,
    };
  }

  reset(): void {
    this.calls = 0;
    this.fingerprints = {};
  }
}
