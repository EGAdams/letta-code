// Orchestration. Owns no rules of its own: it hands each event page to the
// reducer, asks the policies what to follow and what is stalled, and publishes
// one view. Presentation components only ever read that view and call the
// five actions below.
import type {
  ConnectionState,
  FeedPage,
  IAdwEventSource,
  IClearStore,
  IClock,
  ILegacyTerminal,
  IRunSelectionPolicy,
  ISequenceDiagramRenderer,
  IStallPolicy,
  ITimer,
  RunSelection,
  RunSummary,
} from "./contracts";
import { clearRun, type LogFilter, linesFor } from "./domain/log-selection";
import { project } from "./domain/projector";
import { type DebuggerState, emptyState } from "./domain/state";
import { type DebuggerView, describe, diagramFor } from "./domain/view";

export interface ControllerDependencies {
  source: IAdwEventSource;
  selection: IRunSelectionPolicy;
  stall: IStallPolicy;
  renderer: ISequenceDiagramRenderer;
  cleared: IClearStore;
  legacy: ILegacyTerminal;
  clock: IClock & { align?(serverNow: string): void };
  timer: ITimer;
  tickMs?: number;
}

export class DebuggerController {
  private state: DebuggerState = emptyState();
  private selected: RunSelection = { runId: null, pinReleased: false };
  private filter: LogFilter = { mode: "all" };
  private connection: ConnectionState = { status: "connecting" };
  private timeoutSeconds = 120;
  private lastDelayMs: number | null = null;
  private renderError = "";
  private tick: unknown = null;
  private unsubscribe: (() => void) | null = null;
  private readonly listeners = new Set<(view: DebuggerView) => void>();

  constructor(private readonly deps: ControllerDependencies) {}

  start(): void {
    this.unsubscribe = this.deps.source.subscribe({
      onPage: (page) => this.onPage(page),
      onConnection: (state) => {
        this.connection = state;
        this.publish();
      },
    });
    this.deps.source.start();
    const again = () => {
      this.publish();
      this.tick = this.deps.timer.set(again, this.deps.tickMs ?? 1000);
    };
    this.tick = this.deps.timer.set(again, this.deps.tickMs ?? 1000);
  }

  /** The view came into sight: catch up now rather than on the slow cadence. */
  wake(): void {
    this.deps.source.wake();
  }

  dispose(): void {
    this.deps.source.stop();
    this.unsubscribe?.();
    this.deps.timer.clear(this.tick);
    this.deps.legacy.setVisible(true);
    this.listeners.clear();
  }

  subscribe(listener: (view: DebuggerView) => void): () => void {
    this.listeners.add(listener);
    listener(this.view());
    return () => {
      this.listeners.delete(listener);
    };
  }

  selectPhase(instanceId: string): void {
    if (!this.selected.runId) return;
    this.filter = { mode: "phase", runId: this.selected.runId, instanceId };
    this.publish();
  }

  allEvents(): void {
    this.filter = { mode: "all" }; // the pin, if any, is left alone
    this.publish();
  }

  followLive(): void {
    this.follow(this.deps.selection.followLive(this.selected, this.runs()));
    this.publish();
  }

  clearSelectedRun(): void {
    if (!this.selected.runId) return;
    clearRun(this.state, this.selected.runId, this.deps.cleared);
    this.publish();
  }

  reportRenderError(message: string): void {
    this.renderError = message;
    this.publish();
  }

  private runs(): RunSummary[] {
    return Object.values(this.state.runs).map((run) => ({
      runId: run.runId,
      status: run.status,
      startedAt: run.startedAt,
    }));
  }

  private follow(next: RunSelection): void {
    if (next.runId !== this.selected.runId) this.filter = { mode: "all" }; // run-specific selection resets
    this.selected = next;
  }

  private onPage(page: FeedPage): void {
    this.deps.clock.align?.(page.server_now);
    this.timeoutSeconds = page.stall_timeout_seconds;
    const before = this.state;
    this.state = project(this.state, page);
    if (!page.bootstrap && this.state !== before && page.events.length > 0) {
      const newest = Date.parse(
        page.events[page.events.length - 1].recorded_at,
      );
      if (!Number.isNaN(newest))
        this.lastDelayMs = Math.max(0, this.deps.clock.now() - newest);
    }
    this.follow(this.deps.selection.select(this.selected, this.runs()));
    this.publish();
  }

  private view(): DebuggerView {
    const run = this.selected.runId
      ? this.state.runs[this.selected.runId]
      : undefined;
    const mode = this.deps.selection.mode(this.selected, this.runs());
    const selectedInstance =
      this.filter.mode === "phase" && this.filter.runId === run?.runId
        ? this.filter.instanceId
        : null;
    const rendered = this.deps.renderer.render(
      diagramFor(
        run,
        this.deps.clock.now(),
        this.timeoutSeconds * 1000,
        this.deps.stall,
        selectedInstance,
      ),
    );
    return {
      runId: run?.runId ?? null,
      adwName: run?.adwName ?? "",
      runStatus: run?.status ?? null,
      mode,
      diagram: rendered.model,
      lines: linesFor(this.state, this.filter, this.deps.cleared),
      phaseSelected: this.filter.mode === "phase",
      connection: this.connection,
      renderError: rendered.error || this.renderError,
      stallTimeoutSeconds: this.timeoutSeconds,
      lastDelayMs: this.lastDelayMs,
      ...describe(run, mode, this.filter, this.state),
    };
  }

  private publish(): void {
    this.deps.legacy.setVisible(this.filter.mode === "all");
    const view = this.view();
    for (const listener of this.listeners) listener(view);
  }
}
