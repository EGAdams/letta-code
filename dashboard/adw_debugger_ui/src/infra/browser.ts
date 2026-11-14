// The browser-facing adapters: fetch, timers, storage, and the legacy terminal node.
import type {
  IClearStore,
  IClock,
  IHttpJson,
  ILegacyTerminal,
  ITimer,
} from "../contracts";

export class FetchJson implements IHttpJson {
  async getJSON(url: string): Promise<unknown> {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status} from ${url}`);
    return response.json();
  }
}

export class WindowTimer implements ITimer {
  set(callback: () => void, ms: number): unknown {
    return window.setTimeout(callback, ms);
  }
  clear(handle: unknown): void {
    window.clearTimeout(handle as number);
  }
}

/** The server's clock, estimated from each feed page's `server_now`. */
export class ServerAlignedClock implements IClock {
  private offset = 0;
  align(serverNow: string): void {
    const server = Date.parse(serverNow);
    if (!Number.isNaN(server)) this.offset = server - Date.now();
  }
  now(): number {
    return Date.now() + this.offset;
  }
}

export class LocalStorageClearStore implements IClearStore {
  private marks: Record<string, number> = {};
  constructor(private readonly key = "adwDebugger.clearedThrough.v1") {
    try {
      this.marks = JSON.parse(localStorage.getItem(this.key) ?? "{}") ?? {};
    } catch {
      this.marks = {};
    }
  }
  get(runId: string): number {
    return this.marks[runId] ?? 0;
  }
  set(runId: string, cursor: number): void {
    this.marks[runId] = cursor;
    try {
      localStorage.setItem(this.key, JSON.stringify(this.marks));
    } catch {
      /* display state only */
    }
  }
}

/** Hides or shows the dashboard's own #terminal-stream. Never touches its contents. */
export class DomLegacyTerminal implements ILegacyTerminal {
  constructor(private readonly node: HTMLElement | null) {}
  setVisible(visible: boolean): void {
    if (this.node) this.node.style.display = visible ? "" : "none";
  }
}
