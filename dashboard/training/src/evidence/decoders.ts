import type {
  IWorkflowCheckpoint,
  IWorkflowPhase,
  IWorkflowRun,
} from "../../../../../the-factory/src/components/workflow-inspector/interfaces";

type JsonRecord = Record<string, unknown>;
const invalid = (): never => {
  throw new Error(
    "The server returned invalid workflow evidence. Refresh to retry.",
  );
};
const record = (value: unknown): JsonRecord =>
  value && typeof value === "object" && !Array.isArray(value)
    ? (value as JsonRecord)
    : invalid();
const string = (value: unknown): string =>
  typeof value === "string" ? value : invalid();
export const runId = (value: unknown): string =>
  /^[a-f0-9]{8}$/.test(string(value)) ? (value as string) : invalid();

export function decodeCheckpoint(value: unknown): IWorkflowCheckpoint {
  const response = record(value);
  if (response.ok !== true) invalid();
  const state = record(response.state);
  if (
    state.expense_id !== null &&
    (!Number.isSafeInteger(state.expense_id) ||
      (state.expense_id as number) <= 0)
  )
    invalid();
  if (!Array.isArray(state.run_ids)) invalid();
  return {
    assignment: string(state.assignment),
    environment: string(state.environment),
    status: string(state.status),
    expense: state.expense_id as number | null,
    category: string(state.category),
    message: string(state.message),
    pending:
      state.command === null ? null : string(record(state.command).action),
    runs: [...new Set((state.run_ids as unknown[]).map(runId))],
  };
}

export function decodeRun(value: unknown, expected: string): IWorkflowRun {
  const response = record(value);
  if (
    response.ok !== true ||
    runId(response.run_id) !== expected ||
    !Array.isArray(response.events)
  )
    invalid();
  const events = response.events as unknown[];
  const phases = new Map<string, IWorkflowPhase>();
  let recordedAt = "";
  for (const raw of events) {
    const event = record(raw);
    if (event.adw_id !== expected) invalid();
    const type = string(event.type);
    const timestamp = string(event.ts);
    if (!Number.isFinite(Date.parse(timestamp))) invalid();
    recordedAt = timestamp;
    if (type !== "phase_start" && type !== "phase_end") continue;
    const id = string(event.phase_id);
    if (!id) invalid();
    const name = string(event.name);
    const payload = record(event.payload);
    const previous = phases.get(id);
    if (type === "phase_start") {
      phases.set(id, {
        id,
        name,
        description:
          typeof payload.description === "string" ? payload.description : "",
        status: "No completion recorded",
        started: timestamp,
        ended: "",
      });
    } else {
      const status =
        payload.status === "success"
          ? "Completed"
          : ["error", "failed", "failure"].includes(String(payload.status))
            ? "Failed"
            : "Unknown result";
      phases.set(id, {
        id,
        name,
        description: previous?.description || "",
        status,
        started: previous?.started || "",
        ended: timestamp,
      });
    }
  }
  return {
    id: expected,
    phases: [...phases.values()],
    recordedAt,
    limited: events.length >= 500,
  };
}
