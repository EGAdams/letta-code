// Which recorded lines the terminal shows: a phase filter plus per-run clear marks.
import type { IClearStore } from "../contracts";
import type { DebuggerState, LogLine } from "./state";

export type LogFilter =
  | { mode: "all" }
  | { mode: "phase"; runId: string; instanceId: string };

export function linesFor(
  state: DebuggerState,
  filter: LogFilter,
  cleared: IClearStore,
): LogLine[] {
  return state.logs.filter((line) => {
    if (line.cursor <= cleared.get(line.runId)) return false;
    if (filter.mode === "all") return true;
    if (line.runId !== filter.runId) return false;
    const run = state.runs[line.runId];
    const owner =
      (line.phaseId && run?.instanceOfPhase[line.phaseId]) ||
      line.instanceId ||
      line.phaseId;
    return owner === filter.instanceId;
  });
}

/** Clear is a display mark: everything recorded for this run up to now is hidden. */
export function clearRun(
  state: DebuggerState,
  runId: string,
  cleared: IClearStore,
): void {
  cleared.set(runId, Math.max(cleared.get(runId), state.maxCursor));
}
