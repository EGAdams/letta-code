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
export declare function commandFrom(raw: unknown): BrowserCommand | null;
export declare function workFrom(raw: unknown): WorkResult | null;
