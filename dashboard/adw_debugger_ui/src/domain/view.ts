// Selector: state + selection + time -> exactly what the components draw. Pure.
import type {
  ConnectionState,
  DiagramColumn,
  DiagramModel,
  IStallPolicy,
  PhaseStatus,
  RunMode,
  RunStatus,
} from "../contracts";
import type { LogFilter } from "./log-selection";
import {
  type DebuggerState,
  isTerminal,
  type LogLine,
  type PhaseState,
  type RunState,
} from "./state";

export interface DebuggerView {
  runId: string | null;
  adwName: string;
  runStatus: RunStatus | null;
  mode: RunMode;
  modeLabel: string;
  diagram: DiagramModel;
  lines: LogLine[];
  filterLabel: string;
  phaseSelected: boolean;
  clearLabel: string;
  clearDisabledReason: string;
  connection: ConnectionState;
  renderError: string;
  stallTimeoutSeconds: number;
  lastDelayMs: number | null;
}

const MODE_LABEL: Record<RunMode, string> = {
  idle: "Idle -- no pilot run recorded yet",
  live: "Live",
  completed: "Completed",
  pinned: "Pinned after failure",
};

const LABEL: Record<PhaseStatus, string> = {
  waiting: "Waiting",
  running: "Running",
  stalled: "Stalled",
  fail: "Fail",
  pass: "Pass",
};

function elapsed(fromMs: number, toMs: number): string {
  if (!fromMs) return "";
  const total = Math.max(0, Math.round((toMs - fromMs) / 1000));
  return total >= 60
    ? `${Math.floor(total / 60)}m ${total % 60}s`
    : `${total}s`;
}

export function columnFor(
  phase: PhaseState,
  run: RunState,
  now: number,
  timeoutMs: number,
  stall: IStallPolicy,
  selected: boolean,
): DiagramColumn {
  let status: PhaseStatus = "waiting";
  let detail = "";
  if (phase.outcome === "pass" || phase.outcome === "fail") {
    status = phase.outcome;
    detail = [elapsed(phase.startedAt, phase.endedAt), phase.error]
      .filter(Boolean)
      .join(" -- ");
  } else if (phase.abandoned) {
    detail = "never executed";
  } else if (!phase.started) {
    detail = "constructed, not started";
  } else if (run.status !== "running") {
    status = "stalled";
    detail =
      run.status === "interrupted"
        ? "process ended without recording an outcome; no cleanup recorded"
        : `run ended (${run.status}) without an outcome for this phase`;
  } else {
    const verdict = stall.evaluate(
      {
        started: phase.started,
        terminal: isTerminal(phase),
        lastProgressAt: phase.lastProgressAt,
        waitDeadlineAt: phase.waitDeadlineAt,
        waitReason: phase.waitReason,
      },
      now,
      timeoutMs,
    );
    status = verdict
      ? "stalled"
      : phase.waitDeadlineAt !== null
        ? "waiting"
        : "running";
    detail = [
      elapsed(phase.startedAt, now),
      verdict?.reason ?? phase.waitReason,
    ]
      .filter(Boolean)
      .join(" -- ");
  }
  return {
    instanceId: phase.instanceId,
    name: phase.name,
    attempt: phase.attempt,
    status,
    statusLabel: LABEL[status],
    detail,
    purpose: phase.purpose,
    selected,
  };
}

export function diagramFor(
  run: RunState | undefined,
  now: number,
  timeoutMs: number,
  stall: IStallPolicy,
  selectedInstance: string | null,
): DiagramModel {
  if (!run) return { runId: "", columns: [], rows: [] };
  const columns = run.visible
    .map((id) => run.phases[id])
    .filter(Boolean)
    .map((phase) =>
      columnFor(
        phase,
        run,
        now,
        timeoutMs,
        stall,
        phase.instanceId === selectedInstance,
      ),
    );
  const index = new Map(
    columns.map((column, position) => [column.instanceId, position]),
  );
  // Only arrows whose two ends are both on screen are drawn; the rest stay in the terminal.
  const rows = run.arrows
    .filter((arrow) => index.has(arrow.from) && index.has(arrow.to))
    .map((arrow) => ({
      id: arrow.id,
      from: index.get(arrow.from)!,
      to: index.get(arrow.to)!,
      text: arrow.text,
      dashed: arrow.dashed,
      kind: arrow.kind,
    }));
  return { runId: run.runId, columns, rows };
}

export function describe(
  run: RunState | undefined,
  mode: RunMode,
  filter: LogFilter,
  state: DebuggerState,
) {
  const phase =
    filter.mode === "phase"
      ? state.runs[filter.runId]?.phases[filter.instanceId]
      : undefined;
  return {
    modeLabel: MODE_LABEL[mode],
    filterLabel:
      filter.mode === "all"
        ? "All events"
        : `Run ${filter.runId} -- phase ${phase?.name ?? filter.instanceId}` +
          ` (${filter.instanceId}${phase?.attempt ? `, attempt ${phase.attempt}` : ""})`,
    clearLabel: run
      ? `Clear displayed logs for ${run.runId}`
      : "Clear displayed logs",
    clearDisabledReason: run
      ? ""
      : "No ADW run is selected, so there is nothing run-scoped to clear.",
  };
}
