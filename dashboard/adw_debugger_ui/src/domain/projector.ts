// Reducer: (state, feed page) -> next state. Pure -- no clock, no DOM, no network.
// The input state is never modified; a page with nothing new returns it unchanged.
import type { DebugEvent, DebugRun, FeedPage } from "../contracts";
import { refreshVisible, renameColumn } from "./columns";
import {
  type DebuggerState,
  MAX_LOG_LINES,
  type PhaseState,
  RUNNER,
  type RunState,
} from "./state";

const PROGRESS_KINDS = new Set([
  "phase_start",
  "bound",
  "progress",
  "tool_call",
  "tool_result",
  "message",
  "log",
]);

function newRun(run: DebugRun): RunState {
  return {
    runId: run.run_id,
    adwName: run.adw_name,
    status: run.status,
    startedAt: run.started_at,
    endedAt: run.ended_at,
    phases: {},
    instanceOfPhase: {},
    arrows: [],
    visible: [],
  };
}

function newPhase(event: DebugEvent, instanceId: string): PhaseState {
  return {
    instanceId,
    runId: event.run_id,
    phaseId: "",
    name: event.phase_name || instanceId,
    attempt: event.attempt,
    className: "",
    purpose: "",
    order: event.cursor,
    constructed: false,
    started: false,
    outcome: null,
    abandoned: false,
    startedAt: 0,
    endedAt: 0,
    lastProgressAt: 0,
    waitDeadlineAt: null,
    waitReason: "",
    cleanup: "",
    error: "",
  };
}

function instanceFor(run: RunState, event: DebugEvent): string {
  if (event.phase_id && run.instanceOfPhase[event.phase_id])
    return run.instanceOfPhase[event.phase_id];
  return event.instance_id || event.phase_id;
}

/** `bound` says which constructed instance a phase id belongs to; fold the stand-in into it. */
function bind(run: RunState, event: DebugEvent): PhaseState {
  const instanceId = event.instance_id;
  const standIn = run.phases[event.phase_id];
  const phase = run.phases[instanceId] ?? newPhase(event, instanceId);
  if (standIn && standIn !== phase) {
    phase.started = phase.started || standIn.started;
    phase.startedAt = phase.startedAt || standIn.startedAt;
    phase.lastProgressAt = Math.max(
      phase.lastProgressAt,
      standIn.lastProgressAt,
    );
    phase.outcome = phase.outcome ?? standIn.outcome;
    delete run.phases[event.phase_id];
    renameColumn(run, event.phase_id, instanceId);
  }
  run.phases[instanceId] = phase;
  run.instanceOfPhase[event.phase_id] = instanceId;
  phase.phaseId = event.phase_id;
  return phase;
}

function pushArrow(
  run: RunState,
  event: DebugEvent,
  from: string,
  to: string,
  text: string,
  dashed: boolean,
): void {
  run.arrows.push({
    id: event.event_id,
    cursor: event.cursor,
    at: Date.parse(event.recorded_at) || 0,
    kind: event.kind,
    from,
    to,
    text,
    dashed,
  });
}

/** Tool calls, their results, progress notes and messages: one row each, as recorded. */
function recordArrow(
  run: RunState,
  event: DebugEvent,
  instanceId: string,
): void {
  if (event.kind === "progress") {
    if (event.message)
      pushArrow(run, event, instanceId, instanceId, event.message, false);
    return;
  }
  if (
    event.kind !== "tool_call" &&
    event.kind !== "tool_result" &&
    event.kind !== "message"
  )
    return;
  const crossPhase =
    event.kind === "message" && event.source_instance && event.target_instance;
  pushArrow(
    run,
    event,
    crossPhase ? event.source_instance : instanceId,
    crossPhase ? event.target_instance : instanceId,
    event.message,
    event.kind === "tool_result",
  );
}

function seconds(fromMs: number, toMs: number): string {
  if (!fromMs || !toMs) return "";
  const ms = Math.max(0, toMs - fromMs);
  return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)}s`;
}

function applyEvent(run: RunState, event: DebugEvent): void {
  const at = Date.parse(event.recorded_at) || 0;
  const instanceId = instanceFor(run, event);
  if (!instanceId) return; // a run-level line: terminal only
  let phase: PhaseState;
  if (event.kind === "bound") {
    phase = bind(run, event);
  } else {
    run.phases[instanceId] ??= newPhase(event, instanceId);
    phase = run.phases[instanceId];
  }
  if (event.attempt !== null && event.attempt !== undefined)
    phase.attempt = event.attempt;
  recordArrow(run, event, phase.instanceId);

  if (event.kind === "constructed") {
    phase.constructed = true;
    phase.className = event.message;
  } else if (event.kind === "purpose") {
    phase.purpose = event.message;
  } else if (event.kind === "cleanup") {
    phase.cleanup = event.message; // evidence only: never changes an outcome
    if (!phase.started && phase.outcome === null) phase.abandoned = true;
  } else if (event.kind === "error") {
    phase.error = event.message;
  }
  if (phase.outcome !== null || phase.abandoned) {
    // a late event never reopens a finished phase
    refreshVisible(run);
    return;
  }
  if (
    event.kind === "phase_end" &&
    event.status &&
    event.status !== "running"
  ) {
    phase.outcome = event.status;
    phase.endedAt = at;
    phase.started = true;
    // The runner gets the outcome back: the dashed return arrow.
    pushArrow(
      run,
      event,
      phase.instanceId,
      RUNNER,
      [event.status, seconds(phase.startedAt, at), phase.error]
        .filter(Boolean)
        .join(" · "),
      true,
    );
    refreshVisible(run);
    return;
  }
  if (event.kind === "waiting") {
    phase.waitDeadlineAt = event.deadline_at
      ? Date.parse(event.deadline_at)
      : null;
    phase.waitReason = event.message;
    phase.lastProgressAt = at;
  } else if (PROGRESS_KINDS.has(event.kind)) {
    phase.waitDeadlineAt = null;
    phase.waitReason = "";
    phase.lastProgressAt = at;
  }
  if (
    (event.kind === "phase_start" || event.kind === "bound") &&
    !phase.started
  ) {
    phase.started = true;
    phase.startedAt = at;
    if (event.kind === "phase_start") phase.phaseId = event.phase_id;
    // The runner starts the phase: the solid call arrow.
    pushArrow(run, event, RUNNER, phase.instanceId, phase.name, false);
    refreshVisible(run);
    return;
  }
  refreshVisible(run);
}

function logText(event: DebugEvent): string {
  const where = [event.run_id, event.phase_name, event.kind]
    .filter(Boolean)
    .join(" ");
  return `${event.recorded_at} [${where}] ${event.message}`;
}

export function project(state: DebuggerState, page: FeedPage): DebuggerState {
  const fresh = page.events.filter((event) => !state.seen[event.event_id]);
  const runsChanged = page.runs.some((run) => {
    const known = state.runs[run.run_id];
    return (
      !known || known.status !== run.status || known.endedAt !== run.ended_at
    );
  });
  if (fresh.length === 0 && !runsChanged) return state;

  const next: DebuggerState = structuredClone(state);
  for (const run of page.runs) {
    next.runs[run.run_id] ??= newRun(run);
    const known = next.runs[run.run_id];
    known.status = run.status;
    known.endedAt = run.ended_at;
  }
  for (const event of fresh.sort((a, b) => a.cursor - b.cursor)) {
    next.seen[event.event_id] = true;
    next.maxCursor = Math.max(next.maxCursor, event.cursor);
    next.runs[event.run_id] ??= newRun({
      run_id: event.run_id,
      adw_name: event.adw_name,
      status: "running",
      started_at: event.recorded_at,
      ended_at: null,
      process_alive: null,
    });
    const run = next.runs[event.run_id];
    applyEvent(run, event);
    next.logs.push({
      cursor: event.cursor,
      eventId: event.event_id,
      runId: event.run_id,
      phaseId: event.phase_id,
      instanceId: event.instance_id,
      recordedAt: event.recorded_at,
      kind: event.kind,
      text: logText(event),
    });
  }
  next.logs.sort((a, b) => a.cursor - b.cursor);
  if (next.logs.length > MAX_LOG_LINES)
    next.logs.splice(0, next.logs.length - MAX_LOG_LINES);
  return next;
}
