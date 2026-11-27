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
  ISupervisorEventSource,
  ITimer,
  RunSelection,
  RunSummary,
  SupervisorEvent,
  SupervisorPage,
} from "./contracts";
import { hasKnownExecutionHost, isDadsComputer } from "./domain/host-filter";
import { clearRun, type LogFilter, linesFor } from "./domain/log-selection";
import { project } from "./domain/projector";
import { type DebuggerState, emptyState } from "./domain/state";
import {
  agentsOf,
  awakeState,
  type SupervisorView,
  linesFor as supervisorLines,
} from "./domain/supervisor";
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
  /** Supervisor records; absent where the page has no live-activity feed. Read-only. */
  supervisor?: ISupervisorEventSource;
  /** Machines the supervisor pane can be pointed at; "" is the machine serving the dashboard. */
  machines?: string[];
}

export class DebuggerController {
  private state: DebuggerState = emptyState();
  private selected: RunSelection = { runId: null, pinReleased: false };
  private filter: LogFilter = { mode: "all" };
  private connection: ConnectionState = { status: "connecting" };
  private timeoutSeconds = 120;
  private lastDelayMs: number | null = null;
  private renderError = "";
  private dadsComputerOnly = false;
  private supervisorEvents: SupervisorEvent[] = [];
  private supervisorGaps: string[] = [];
  private supervisorError = "";
  private supervisorMachine = "";
  private supervisorAgent = "";
  private supervisorCorrelate = false;
  private unsubscribeSupervisor: (() => void) | null = null;
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
    this.unsubscribeSupervisor =
      this.deps.supervisor?.subscribe({
        onPage: (page) => this.onSupervisorPage(page),
        onConnection: (state) => {
          this.supervisorError =
            state.status === "disconnected" || state.status === "degraded"
              ? state.reason
              : "";
          this.publish();
        },
      }) ?? null;
    this.deps.supervisor?.start();
    const again = () => {
      this.publish();
      this.tick = this.deps.timer.set(again, this.deps.tickMs ?? 1000);
    };
    this.tick = this.deps.timer.set(again, this.deps.tickMs ?? 1000);
  }

  /** The view came into sight: catch up now rather than on the slow cadence. */
  wake(): void {
    this.deps.source.wake();
    this.deps.supervisor?.wake();
  }

  dispose(): void {
    this.deps.source.stop();
    this.unsubscribe?.();
    this.deps.supervisor?.stop();
    this.unsubscribeSupervisor?.();
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

  toggleDadsComputerOnly(): void {
    this.dadsComputerOnly = !this.dadsComputerOnly;
    const selected = this.selected.runId
      ? this.state.runs[this.selected.runId]
      : undefined;
    if (this.dadsComputerOnly && selected && !isDadsComputer(selected)) {
      this.selected = { runId: null, pinReleased: false };
      this.filter = { mode: "all" };
    }
    this.follow(this.deps.selection.select(this.selected, this.runs()));
    this.publish();
  }

  /** Point the supervisor pane at another machine. Never touches the run's own events. */
  selectSupervisorMachine(machine: string): void {
    if (machine === this.supervisorMachine) return;
    this.supervisorMachine = machine;
    this.supervisorEvents = [];
    this.supervisorGaps = [];
    this.supervisorAgent = "";
    this.deps.supervisor?.setMachine(machine);
    this.publish();
  }

  selectSupervisorAgent(agent: string): void {
    this.supervisorAgent = agent;
    this.publish();
  }

  /** Show only the records that carry the selected run's id. Off by default. */
  toggleSupervisorCorrelation(): void {
    this.supervisorCorrelate = !this.supervisorCorrelate;
    this.publish();
  }

  /** Clears the run's terminal view only; supervisor and audit records are never removed. */
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
    return Object.values(this.state.runs)
      .filter((run) => !this.dadsComputerOnly || isDadsComputer(run))
      .map((run) => ({
        runId: run.runId,
        status: run.status,
        startedAt: run.startedAt,
      }));
  }

  private onSupervisorPage(page: SupervisorPage): void {
    this.deps.clock.align?.(page.server_now);
    this.supervisorEvents = page.supervisor_events;
    this.supervisorGaps = page.gaps;
    this.publish();
  }

  private supervisorView(runId: string | null): SupervisorView {
    const correlate = this.supervisorCorrelate && runId !== null;
    const lines = supervisorLines(this.supervisorEvents, {
      agent: this.supervisorAgent,
      runId: correlate ? runId : null,
    });
    return {
      available: this.deps.supervisor !== undefined,
      machine: this.supervisorMachine,
      machines: this.deps.machines ?? [""],
      agents: agentsOf(this.supervisorEvents),
      agent: this.supervisorAgent,
      correlate: this.supervisorCorrelate,
      correlateLabel: runId
        ? `Only records for run ${runId}`
        : "Only records for the selected run (no run selected)",
      lines,
      total: this.supervisorEvents.length,
      gaps: this.supervisorGaps,
      error: this.supervisorError,
      awake: awakeState(this.supervisorEvents),
    };
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
    const allRuns = Object.values(this.state.runs);
    const visibleRuns = this.dadsComputerOnly
      ? allRuns.filter(isDadsComputer)
      : allRuns;
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
      dadsComputerOnly: this.dadsComputerOnly,
      dadsComputerFilterAvailable: allRuns.some(hasKnownExecutionHost),
      dadsComputerVisibleRuns: visibleRuns.length,
      supervisor: this.supervisorView(run?.runId ?? null),
      ...describe(run, mode, this.filter, this.state),
    };
  }

  private publish(): void {
    this.deps.legacy.setVisible(this.filter.mode === "all");
    const view = this.view();
    for (const listener of this.listeners) listener(view);
  }
}
