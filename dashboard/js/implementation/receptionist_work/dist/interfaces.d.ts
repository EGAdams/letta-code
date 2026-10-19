import type {
  BrowserCommand,
  BrowserOutcome,
  WorkResult,
  WorkState,
} from "./contracts.js";
export type { WorkState } from "./contracts.js";
export interface BrowserWorkspace {
  show(state: WorkState): void;
  execute(command: BrowserCommand): Promise<BrowserOutcome>;
}
export interface Workflows {
  state(): Promise<WorkResult>;
  claim(command: BrowserCommand): Promise<boolean>;
  verify(command: BrowserCommand, outcome: BrowserOutcome): Promise<WorkResult>;
  cancel(command: BrowserCommand): Promise<WorkResult>;
}
export interface JsonHttp {
  getJSON(url: string): Promise<unknown>;
  postJSON(
    url: string,
    body: unknown,
    options?: {
      timeout?: number;
    },
  ): Promise<unknown>;
}
export interface RequestIdentity {
  forGeneration(generation: string): string;
}
export type WorkPhase =
  | "no_work"
  | "assigned"
  | "in_progress"
  | "needs_input"
  | "paused"
  | "cancelled"
  | "failed"
  | "verified"
  | "unknown";
/** The separate statements the work panel shows, so no two conditions can look alike. */
export interface WorkFacts {
  phase: WorkPhase;
  headline: string;
  assignment: string;
  expense: string;
  operation: string;
  /** Non-empty only while an answer is owed to the receptionist. */
  waitingFor: string;
  /** Non-empty only for a failure or a cancellation. */
  problem: string;
  /** Non-empty only when a stored value was read back; never a restatement of the request. */
  evidence: string;
  /** The operation and run this panel is describing, so evidence is attributable. */
  identity: string;
  verified: boolean;
}
export interface WorkPresenter {
  present(state: WorkState): WorkFacts;
}
