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
  RUNNER,
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

const RUNNER_STATUS: Record<RunStatus, PhaseStatus> = {
  running: "running",
  success: "pass",
  fail: "fail",
  interrupted: "stalled",
};

/** The ADW itself, drawn as the left-most participant. */
function runnerColumn(run: RunState, now: number): DiagramColumn {
  const status = RUNNER_STATUS[run.status] ?? "waiting";
  const startedMs = Date.parse(run.startedAt) || 0;
  const endedMs = run.endedAt ? Date.parse(run.endedAt) || now : now;
  return {
    instanceId: RUNNER,
    kind: "runner",
    name: run.adwName,
    attempt: null,
    status,
    statusLabel: LABEL[status],
    detail: elapsed(startedMs, endedMs),
    purpose: `ADW run ${run.runId}: starts each phase and receives its outcome`,
    selected: false,
  };
}

function offset(fromMs: number, atMs: number): string {
  if (!fromMs || !atMs) return "";
  const ms = Math.max(0, atMs - fromMs);
  return ms >= 10_000 ? `+${(ms / 1000).toFixed(1)} s` : `+${ms} ms`;
}

export function diagramFor(
  run: RunState | undefined,
  now: number,
  timeoutMs: number,
  stall: IStallPolicy,
  selectedInstance: string | null,
): DiagramModel {
  if (!run) return { runId: "", columns: [], rows: [] };
  const phases = run.visible
    .map((id) => run.phases[id])
    .filter(Boolean)
    .map((phase) => ({
      ...columnFor(
        phase,
        run,
        now,
        timeoutMs,
        stall,
        phase.instanceId === selectedInstance,
      ),
      kind: "phase" as const,
    }));
  if (phases.length === 0) return { runId: run.runId, columns: [], rows: [] };
  const columns: DiagramColumn[] = [runnerColumn(run, now), ...phases];
  const index = new Map(
    columns.map((column, position) => [column.instanceId, position]),
  );
  const runStartMs = Date.parse(run.startedAt) || (run.arrows[0]?.at ?? 0);
  // Only arrows whose two ends are both on screen are drawn; the rest stay in the terminal.
  const arrows = run.arrows
    .filter((arrow) => index.has(arrow.from) && index.has(arrow.to))
    .sort((a, b) => a.cursor - b.cursor);
  const rows = arrows.map((arrow) => ({
    id: arrow.id,
    from: index.get(arrow.from)!,
    to: index.get(arrow.to)!,
    text: arrow.text,
    dashed: arrow.dashed,
    kind: arrow.kind,
    elapsed: offset(runStartMs, arrow.at),
  }));
  // Activation bars: from the row that started a phase to the row that returned its outcome.
  for (const column of columns) {
    if (column.kind === "runner") {
      column.activeFrom = rows.length ? 0 : null;
      column.activeTo = run.status === "running" ? null : rows.length - 1;
      continue;
    }
    const at = index.get(column.instanceId)!;
    const first = rows.findIndex((row) => row.to === at || row.from === at);
    const end = rows.findIndex(
      (row) => row.kind === "phase_end" && row.from === at,
    );
    const phase = run.phases[column.instanceId];
    column.activeFrom = phase?.started && first >= 0 ? first : null;
    // No recorded outcome (running, stalled, interrupted): the bar stays open to the bottom.
    column.activeTo = end >= 0 ? end : null;
  }
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
