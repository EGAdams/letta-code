// Which phase columns are on screen. Pure; called by the projector after each event.
//
//   active  = phases executing now + real instances still waiting to execute
//   recent  = phases that finished since the last one started
//   visible = active + recent, while anything is active
//
// When nothing is active any more the column set is left exactly as it was, so
// the last diagram stays up with its final colours.
import { isTerminal, type RunState, sortedPhases } from "./state";

export function activeIds(run: RunState): string[] {
  return sortedPhases(run)
    .filter((phase) => !isTerminal(phase))
    .map((phase) => phase.instanceId);
}

export function phaseStarted(run: RunState): void {
  run.recent = [];
  refreshVisible(run);
}

export function phaseEnded(run: RunState, instanceId: string): void {
  if (!run.recent.includes(instanceId)) run.recent.push(instanceId);
  refreshVisible(run);
}

export function refreshVisible(run: RunState): void {
  const active = activeIds(run);
  if (active.length === 0) return;
  const wanted = new Set([...active, ...run.recent]);
  run.visible = sortedPhases(run)
    .map((phase) => phase.instanceId)
    .filter((id) => wanted.has(id));
}

/** A provisional column was replaced by its real instance: carry its place over. */
export function renameColumn(run: RunState, from: string, to: string): void {
  const swap = (ids: string[]) => ids.map((id) => (id === from ? to : id));
  run.recent = swap(run.recent);
  run.visible = swap(run.visible);
}
