// Every interface the debugger is built from. Implementations depend on these,
// never on each other; src/main.ts is the only file that names a concrete class.

export type PhaseStatus = "waiting" | "running" | "stalled" | "fail" | "pass";
export type RunStatus = "running" | "success" | "fail" | "interrupted";

/** One recorded event, as GET /api/adw-debugger/feed delivers it. */
export interface DebugEvent {
  cursor: number;
  event_id: string;
  recorded_at: string;
  kind: string;
  message: string;
  machine: string;
  adw_name: string;
  run_id: string;
  phase_id: string;
  phase_name: string;
  instance_id: string;
  attempt: number | null;
  status: "running" | "pass" | "fail" | null;
  source_instance: string;
  target_instance: string;
  tool: string;
  call_id: string;
  deadline_at: string | null;
  payload?: Record<string, unknown>;
}

export interface DebugRun {
  run_id: string;
  adw_name: string;
  status: RunStatus;
  started_at: string;
  ended_at: string | null;
  process_alive: boolean | null;
}

export interface FeedPage {
  ok: boolean;
  error: string;
  machine: string;
  server_now: string;
  stall_timeout_seconds: number;
  adw_names: string[];
  bootstrap: boolean;
  cursor: number;
  runs: DebugRun[];
  events: DebugEvent[];
}

export type ConnectionState =
  | { status: "connecting" }
  | { status: "connected" }
  | { status: "disconnected"; reason: string; attempts: number }
  | { status: "degraded"; reason: string };

export interface FeedListener {
  onPage(page: FeedPage): void;
  onConnection(state: ConnectionState): void;
}

/** Observer subject: catch-up first, then live pages, resumable by cursor. */
export interface IAdwEventSource {
  subscribe(listener: FeedListener): () => void;
  start(): void;
  stop(): void;
  /** Ask now instead of at the next scheduled time (the view just came into sight). */
  wake(): void;
}

export interface IHttpJson {
  getJSON(url: string): Promise<unknown>;
}

export interface ITimer {
  set(callback: () => void, ms: number): unknown;
  clear(handle: unknown): void;
}

/** Milliseconds since the epoch, on the server's clock. */
export interface IClock {
  now(): number;
}

export interface StallVerdict {
  reason: string;
}

export interface StallInput {
  started: boolean;
  terminal: boolean;
  lastProgressAt: number;
  waitDeadlineAt: number | null;
  waitReason: string;
}

/** Strategy: has this phase gone quiet for too long? Null means no. */
export interface IStallPolicy {
  evaluate(
    phase: StallInput,
    nowMs: number,
    timeoutMs: number,
  ): StallVerdict | null;
}

export interface RunSummary {
  runId: string;
  status: RunStatus;
  startedAt: string;
}

export interface RunSelection {
  runId: string | null;
  pinReleased: boolean;
}

export type RunMode = "idle" | "live" | "completed" | "pinned";

/** Strategy: which run the view follows, and when it lets go of one. */
export interface IRunSelectionPolicy {
  select(current: RunSelection, runs: RunSummary[]): RunSelection;
  followLive(current: RunSelection, runs: RunSummary[]): RunSelection;
  mode(selection: RunSelection, runs: RunSummary[]): RunMode;
}

/** Per-run "cleared through this cursor" marks. Display state only. */
export interface IClearStore {
  get(runId: string): number;
  set(runId: string, cursor: number): void;
}

/** The dashboard's own terminal stream, which this feature never rewrites. */
export interface ILegacyTerminal {
  setVisible(visible: boolean): void;
}

export interface DiagramColumn {
  instanceId: string;
  name: string;
  attempt: number | null;
  status: PhaseStatus;
  statusLabel: string;
  detail: string;
  purpose: string;
  selected: boolean;
}

export interface DiagramRow {
  id: string;
  from: number;
  to: number;
  text: string;
  dashed: boolean;
  kind: string;
}

export interface DiagramModel {
  runId: string;
  columns: DiagramColumn[];
  rows: DiagramRow[];
}

export interface RenderResult {
  model: DiagramModel;
  error: string;
}

/** Turns a diagram model into something safe to draw; keeps the last good one. */
export interface ISequenceDiagramRenderer {
  render(model: DiagramModel): RenderResult;
}
