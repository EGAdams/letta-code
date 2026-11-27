// ISupervisorEventSource over the dashboard's /api/live-activity. Observer subject.
//
// Supervisor records are a snapshot of what is on disk (log tail, handoffs,
// incidents, held mail, status), not an append-only cursor, so each page
// replaces the last. One request at a time; a failed request is a connection
// problem and says nothing about any supervisor.
import type {
  ConnectionState,
  IHttpJson,
  ISupervisorEventSource,
  ITimer,
  SupervisorListener,
  SupervisorPage,
} from "../contracts";

export interface SupervisorPollingOptions {
  url: string;
  activeMs: number;
  idleMs: number;
  retryStepMs: number;
  retryMaxMs: number;
  isActive: () => boolean;
}

export class PollingSupervisorSource implements ISupervisorEventSource {
  private readonly listeners = new Set<SupervisorListener>();
  private machine = "";
  private handle: unknown = null;
  private running = false;
  private inflight = false;
  private failures = 0;
  private generation = 0;

  constructor(
    private readonly http: IHttpJson,
    private readonly timer: ITimer,
    private readonly options: SupervisorPollingOptions,
  ) {}

  subscribe(listener: SupervisorListener): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  start(): void {
    if (this.running) return;
    this.running = true;
    this.emit({ status: "connecting" });
    void this.poll();
  }

  stop(): void {
    this.running = false;
    this.timer.clear(this.handle);
    this.handle = null;
  }

  wake(): void {
    if (!this.running || this.inflight) return;
    this.timer.clear(this.handle);
    void this.poll();
  }

  setMachine(machine: string): void {
    if (machine === this.machine) return;
    this.machine = machine;
    this.generation += 1; // an answer for the old machine must not be shown as the new one
    this.failures = 0;
    this.emit({ status: "connecting" });
    if (!this.running) return;
    this.timer.clear(this.handle);
    this.inflight = false;
    void this.poll();
  }

  private emit(state: ConnectionState): void {
    for (const listener of this.listeners) listener.onConnection(state);
  }

  private schedule(): void {
    if (!this.running) return;
    const wait =
      this.failures > 0
        ? Math.min(
            this.options.retryStepMs * this.failures,
            this.options.retryMaxMs,
          )
        : this.options.isActive()
          ? this.options.activeMs
          : this.options.idleMs;
    this.handle = this.timer.set(() => void this.poll(), wait);
  }

  private urlFor(): string {
    return this.machine
      ? `${this.options.url}${this.options.url.includes("?") ? "&" : "?"}machine=${encodeURIComponent(this.machine)}`
      : this.options.url;
  }

  private async poll(): Promise<void> {
    if (this.inflight || !this.running) return;
    this.inflight = true;
    const generation = this.generation;
    try {
      const page = (await this.http.getJSON(this.urlFor())) as SupervisorPage;
      if (!this.running || generation !== this.generation) return;
      this.failures = 0;
      if (page.ok) {
        this.emit({ status: "connected" });
        for (const listener of this.listeners) listener.onPage(page);
      } else {
        this.emit({
          status: "degraded",
          reason: page.error || "the supervisor records could not be read",
        });
      }
    } catch (error) {
      if (generation !== this.generation) return;
      this.failures += 1;
      this.emit({
        status: "disconnected",
        attempts: this.failures,
        reason: error instanceof Error ? error.message : String(error),
      });
    } finally {
      if (generation === this.generation) {
        this.inflight = false;
        this.schedule();
      }
    }
  }
}
