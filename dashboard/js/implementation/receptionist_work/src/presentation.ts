import type { BrowserCommand, WorkState } from "./contracts.js";
import type { WorkFacts, WorkPhase, WorkPresenter } from "./interfaces.js";

/** One row of the panel per question a reader actually asks of it. */
interface Reading {
  phase: WorkPhase;
  headline: string;
  problem?: (state: WorkState) => string;
}

const READINGS: Record<string, Reading> = {
  idle: { phase: "no_work", headline: "No work in progress." },
  ready: { phase: "assigned", headline: "Ready for your next instruction." },
  waiting_browser: {
    phase: "in_progress",
    headline: "Working in this browser now. Keep this tab open.",
  },
  needs_input: {
    phase: "needs_input",
    headline: "Waiting for you to answer a question.",
  },
  paused: { phase: "paused", headline: "Paused. Your place is kept." },
  verified: {
    phase: "verified",
    headline: "Finished and independently verified.",
  },
  // Neither of the two below may read as a completed save: a cancellation can arrive after the
  // save already landed, and a failure may have failed either before or after the write.
  cancelled: {
    phase: "cancelled",
    headline: "Stopped before finishing.",
    problem: () =>
      "Pending work was stopped. A category that already saved is retained; this does not undo it.",
  },
  failed: {
    phase: "failed",
    headline: "Something went wrong. The stored value is not confirmed.",
    problem: (state) => state.message || "No explanation was reported.",
  },
};

function words(assignment: string): string {
  if (!assignment.trim()) return "No assignment yet.";
  const spaced = assignment.replace(/_/g, " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

function describe(command: BrowserCommand | null): string {
  if (!command) return "No operation requested.";
  if (command.action === "evidence")
    return `Open the supporting information for expense #${command.expense_id}.`;
  if (command.action === "editor")
    return `Open the expense editor for expense #${command.expense_id}.`;
  return `Set the category of expense #${command.expense_id} to ${command.category_label || "an unnamed category"}.`;
}

/**
 * Presenter: turns one checkpoint into the separate statements the work panel shows. It exists so
 * that "waiting", "cancelled", "failed" and "verified" can never collapse into one hopeful line of
 * text, and so a claim of success always arrives with the identity of the run that earned it.
 */
export class TrainingWorkPresenter implements WorkPresenter {
  present(state: WorkState): WorkFacts {
    const reading = READINGS[state.status] ?? {
      phase: "unknown" as WorkPhase,
      headline: `Unexpected status “${state.status}”. Treat this as unfinished.`,
    };
    const run = state.run_ids.at(-1) ?? "";
    const identity = [
      state.command ? `operation ${state.command.id}` : "",
      run ? `run ${run}` : "",
    ]
      .filter((part) => part)
      .join(", ");
    return {
      phase: reading.phase,
      headline: reading.headline,
      assignment: words(state.assignment),
      expense:
        state.expense_id === null
          ? "No expense selected."
          : `Expense #${state.expense_id}`,
      operation: describe(state.command),
      waitingFor: reading.phase === "needs_input" ? state.question : "",
      problem: reading.problem ? reading.problem(state) : "",
      // Only a verified checkpoint earns an evidence line, and it quotes the value that was read
      // back rather than the value that was requested.
      evidence: reading.phase === "verified" ? this.evidence(state) : "",
      identity,
      verified: reading.phase === "verified",
    };
  }
  private evidence(state: WorkState): string {
    const record =
      state.expense_id === null
        ? "the training expense"
        : `expense #${state.expense_id}`;
    const stored =
      state.category || state.command?.category_label || "the requested value";
    return `Read back from the database: ${record} is stored as ${stored}.`;
  }
}
