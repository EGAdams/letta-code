// IAdwEventSource over the dashboard's HTTP feed. Observer subject.
//
// One request at a time on one timer chain. The first request asks for the
// catch-up page; every later one sends the last cursor it was given, so a
// dropped connection resumes exactly where it stopped. A failed request is a
// connection problem and is reported as one -- it says nothing about any ADW.
import type {
  ConnectionState,
  FeedListener,
  FeedPage,
  IAdwEventSource,
  IHttpJson,
  ITimer,
} from "../contracts";

export interface PollingOptions {
  url: string;
  activeMs: number;
  idleMs: number;
  retryStepMs: number;
  retryMaxMs: number;
  isActive: () => boolean;
}

export class PollingEventSource implements IAdwEventSource {
  private readonly listeners = new Set<FeedListener>();
  private cursor: number | null = null;
  private handle: unknown = null;
  private running = false;
  private inflight = false;
  private failures = 0;

  constructor(
    private readonly http: IHttpJson,
    private readonly timer: ITimer,
    private readonly options: PollingOptions,
  ) {}

  subscribe(listener: FeedListener): () => void {
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

  private async poll(): Promise<void> {
    if (this.inflight || !this.running) return;
    this.inflight = true;
    try {
      const url =
        this.cursor === null
          ? this.options.url
          : `${this.options.url}?after=${this.cursor}`;
      const page = (await this.http.getJSON(url)) as FeedPage;
      if (!this.running) return;
      this.failures = 0;
      if (page.ok) {
        this.cursor = Math.max(this.cursor ?? 0, page.cursor);
        this.emit({ status: "connected" });
        for (const listener of this.listeners) listener.onPage(page);
      } else {
        this.emit({
          status: "degraded",
          reason: page.error || "the feed could not read the trace database",
        });
      }
    } catch (error) {
      this.failures += 1;
      this.emit({
        status: "disconnected",
        attempts: this.failures,
        reason: error instanceof Error ? error.message : String(error),
      });
    } finally {
      this.inflight = false;
      this.schedule();
    }
  }
}
