// The debugger's state: plain data, produced only by the projector.
import type { RunStatus } from "../contracts";

export interface PhaseState {
  instanceId: string;
  runId: string;
  phaseId: string;
  name: string;
  attempt: number | null;
  className: string;
  purpose: string;
  order: number;
  constructed: boolean;
  started: boolean;
  outcome: "pass" | "fail" | null;
  abandoned: boolean;
  startedAt: number;
  endedAt: number;
  lastProgressAt: number;
  waitDeadlineAt: number | null;
  waitReason: string;
  cleanup: string;
  error: string;
}

/** The ADW itself: the participant that starts each phase and receives its outcome. */
export const RUNNER = "@runner";

export interface ArrowState {
  id: string;
  cursor: number;
  /** recorded_at as epoch ms (0 when unparseable). */
  at: number;
  kind: string;
  from: string;
  to: string;
  text: string;
  dashed: boolean;
}

export interface LogLine {
  cursor: number;
  eventId: string;
  runId: string;
  phaseId: string;
  instanceId: string;
  recordedAt: string;
  kind: string;
  text: string;
}

export interface RunState {
  runId: string;
  adwName: string;
  status: RunStatus;
  startedAt: string;
  endedAt: string | null;
  phases: Record<string, PhaseState>;
  instanceOfPhase: Record<string, string>;
  arrows: ArrowState[];
  visible: string[];
}

export interface DebuggerState {
  runs: Record<string, RunState>;
  logs: LogLine[];
  seen: Record<string, true>;
  maxCursor: number;
}

export const MAX_LOG_LINES = 5000;

export function emptyState(): DebuggerState {
  return { runs: {}, logs: [], seen: {}, maxCursor: 0 };
}

export function isTerminal(phase: PhaseState): boolean {
  return phase.outcome !== null || phase.abandoned;
}

export function sortedPhases(run: RunState): PhaseState[] {
  return Object.values(run.phases).sort((a, b) => a.order - b.order);
}
