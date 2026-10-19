export interface BrowserCommand {
  id: string;
  action: "evidence" | "editor" | "category";
  expense_id: number;
  category_id: number | null;
  category_label: string;
  url: string;
  expected: Record<string, unknown>;
}
export interface WorkState {
  workspace: string;
  assignment: string;
  environment: "training";
  status: string;
  message: string;
  /** What the receptionist is waiting to be told; empty unless she asked something. */
  question: string;
  /** The stored category as the server last read it back, for checkable evidence. */
  category: string;
  expense_id: number | null;
  command: BrowserCommand | null;
  history: string[];
  run_ids: string[];
}
export interface WorkResult {
  ok: boolean;
  state: WorkState;
  error: string;
}
export interface BrowserOutcome {
  ok: boolean;
  error: string;
}

function object(raw: unknown): raw is Record<string, unknown> {
  return raw !== null && typeof raw === "object" && !Array.isArray(raw);
}
export function commandFrom(raw: unknown): BrowserCommand | null {
  if (
    !object(raw) ||
    typeof raw.id !== "string" ||
    !/^[A-Za-z0-9_-]{8,100}$/.test(raw.id) ||
    !["evidence", "editor", "category"].includes(String(raw.action)) ||
    !Number.isSafeInteger(raw.expense_id) ||
    Number(raw.expense_id) <= 0
  )
    return null;
  if (
    raw.action === "category" &&
    (!Number.isSafeInteger(raw.category_id) ||
      typeof raw.category_label !== "string")
  )
    return null;
  if (
    raw.action === "evidence" &&
    (typeof raw.url !== "string" ||
      !raw.url.startsWith("/api/receptionist-training/document?"))
  )
    return null;
  return {
    id: raw.id,
    action: raw.action as BrowserCommand["action"],
    expense_id: Number(raw.expense_id),
    category_id: Number.isSafeInteger(raw.category_id)
      ? Number(raw.category_id)
      : null,
    category_label:
      typeof raw.category_label === "string" ? raw.category_label : "",
    url: typeof raw.url === "string" ? raw.url : "",
    expected: object(raw.expected) ? raw.expected : {},
  };
}
export function workFrom(raw: unknown): WorkResult | null {
  if (!object(raw) || typeof raw.ok !== "boolean" || !object(raw.state))
    return null;
  const state = raw.state;
  if (
    state.environment !== "training" ||
    typeof state.workspace !== "string" ||
    typeof state.status !== "string" ||
    typeof state.message !== "string"
  )
    return null;
  const command = state.command ? commandFrom(state.command) : null;
  if (state.command && !command) return null;
  return {
    ok: raw.ok,
    error: typeof raw.error === "string" ? raw.error : "",
    state: {
      workspace: state.workspace,
      assignment: String(state.assignment),
      environment: "training",
      status: state.status,
      message: state.message,
      // Optional on the wire: an older server, or any state that asked nothing, omits them.
      question: typeof state.question === "string" ? state.question : "",
      category: typeof state.category === "string" ? state.category : "",
      expense_id: Number.isSafeInteger(state.expense_id)
        ? Number(state.expense_id)
        : null,
      command,
      history: Array.isArray(state.history)
        ? state.history.filter((x): x is string => typeof x === "string")
        : [],
      run_ids: Array.isArray(state.run_ids)
        ? state.run_ids.filter((x): x is string => typeof x === "string")
        : [],
    },
  };
}
