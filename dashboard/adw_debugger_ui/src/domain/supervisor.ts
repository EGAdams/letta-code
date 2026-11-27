// Supervisor records -> what the pane shows. Pure; nothing here writes or deletes.
//
// Correlation uses only the ids the sources already recorded (the ADW run id,
// the post-office task id, the Bridge task id, the request id). A record with
// none of them is shown under "everything", never guessed onto a run.
import type { SupervisorEvent } from "../contracts";

export interface SupervisorFilter {
  agent: string; // "" = every agent
  runId: string | null; // set = only records carrying this id
}

export interface SupervisorLine {
  key: string;
  at: string;
  machine: string;
  agent: string;
  kind: string;
  state: string;
  text: string;
  ids: string;
}

export interface SupervisorView {
  available: boolean;
  machine: string;
  machines: string[];
  agents: string[];
  agent: string;
  correlate: boolean;
  correlateLabel: string;
  lines: SupervisorLine[];
  total: number;
  gaps: string[];
  error: string;
  awake: string;
}

export function idsOf(event: SupervisorEvent): string[] {
  return [
    event.adw_id,
    event.task_id,
    event.bridge_task_id,
    event.request_id,
  ].filter(Boolean);
}

export function agentsOf(events: SupervisorEvent[]): string[] {
  return [...new Set(events.map((e) => e.agent).filter(Boolean))].sort();
}

export function matches(
  event: SupervisorEvent,
  filter: SupervisorFilter,
): boolean {
  if (filter.agent && event.agent !== filter.agent) return false;
  if (filter.runId && !idsOf(event).includes(filter.runId)) return false;
  return true;
}

export function toLine(event: SupervisorEvent, index: number): SupervisorLine {
  return {
    key: `${index}:${event.at}:${event.kind}:${event.source}`,
    at: event.at,
    machine: event.machine,
    agent: event.agent,
    kind: event.kind,
    state: event.state,
    text: event.message,
    ids: idsOf(event).join(" · "),
  };
}

export function linesFor(
  events: SupervisorEvent[],
  filter: SupervisorFilter,
): SupervisorLine[] {
  return events
    .filter((event) => matches(event, filter))
    .map((event, index) => toLine(event, index));
}

/** The newest `status` record's state: "awake", "asleep" or "unknown"; "" when none was recorded. */
export function awakeState(events: SupervisorEvent[]): string {
  for (let i = events.length - 1; i >= 0; i -= 1)
    if (events[i].kind === "status") return events[i].state;
  return "";
}
