// Which phase columns are on screen. Pure; called by the projector after each event.
//
// Every phase instance the run has recorded, in construction order, for the
// whole life of the run -- a sequence diagram reads top to bottom, so a phase
// that has finished keeps its column and its colour. Waiting instances show
// grey until they start; a finished run keeps every column it had.
import { type RunState, sortedPhases } from "./state";

export function refreshVisible(run: RunState): void {
  run.visible = sortedPhases(run).map((phase) => phase.instanceId);
}

/** A provisional column was replaced by its real instance: carry its place and its arrows over. */
export function renameColumn(run: RunState, from: string, to: string): void {
  run.visible = run.visible.map((id) => (id === from ? to : id));
  for (const arrow of run.arrows) {
    if (arrow.from === from) arrow.from = to;
    if (arrow.to === from) arrow.to = to;
  }
}
