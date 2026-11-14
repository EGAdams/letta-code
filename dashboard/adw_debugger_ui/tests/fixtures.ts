// Controlled event fixtures and fakes shared by the tests.
import type {
  DebugEvent,
  DebugRun,
  FeedListener,
  FeedPage,
  IAdwEventSource,
  IClearStore,
  IClock,
  IHttpJson,
  ILegacyTerminal,
  ITimer,
  RunStatus,
} from "../src/contracts";

export const T0 = Date.parse("2026-11-13T10:00:00.000Z");
let serial = 0;

export function at(seconds: number): string {
  return new Date(T0 + seconds * 1000).toISOString();
}

export function ev(
  run: string,
  kind: string,
  extra: Partial<DebugEvent> & { t?: number } = {},
): DebugEvent {
  serial += 1;
  const { t = 0, ...rest } = extra;
  return {
    cursor: serial,
    event_id: `evt_${serial}`,
    recorded_at: at(t),
    kind,
    message: "",
    machine: "box",
    adw_name: "adw_debug_pilot",
    run_id: run,
    phase_id: "",
    phase_name: "",
    instance_id: "",
    attempt: null,
    status: null,
    source_instance: "",
    target_instance: "",
    tool: "",
    call_id: "",
    deadline_at: null,
    ...rest,
  };
}

export function run(
  id: string,
  status: RunStatus = "running",
  started = 0,
): DebugRun {
  return {
    run_id: id,
    adw_name: "adw_debug_pilot",
    status,
    started_at: at(started),
    ended_at: null,
    process_alive: status === "running",
  };
}

export function page(
  runs: DebugRun[],
  events: DebugEvent[],
  extra: Partial<FeedPage> = {},
): FeedPage {
  return {
    ok: true,
    error: "",
    machine: "box",
    server_now: at(0),
    stall_timeout_seconds: 120,
    adw_names: ["adw_debug_pilot"],
    bootstrap: false,
    cursor: events.reduce((max, event) => Math.max(max, event.cursor), 0),
    runs,
    events,
    ...extra,
  };
}

/** The events one instrumented phase records, in order. */
export function constructed(
  runId: string,
  key: string,
  name: string,
  t = 0,
): DebugEvent[] {
  const instance_id = `${runId}:${key}`;
  return [
    ev(runId, "constructed", { instance_id, phase_name: name, attempt: 1, t }),
    ev(runId, "purpose", {
      instance_id,
      phase_name: name,
      message: `purpose of ${key}`,
      t,
    }),
  ];
}

export function started(
  runId: string,
  key: string,
  name: string,
  seq: number,
  t = 0,
): DebugEvent[] {
  const phase_id = `${runId}_0${seq}_${name}`;
  return [
    ev(runId, "phase_start", {
      phase_id,
      phase_name: name,
      instance_id: phase_id,
      status: "running",
      t,
    }),
    ev(runId, "console", {
      phase_id,
      phase_name: name,
      instance_id: phase_id,
      message: `> ${name}`,
      t,
    }),
    ev(runId, "bound", {
      phase_id,
      phase_name: name,
      instance_id: `${runId}:${key}`,
      attempt: 1,
      t,
    }),
  ];
}

export function ended(
  runId: string,
  key: string,
  name: string,
  seq: number,
  status: "pass" | "fail",
  t = 0,
): DebugEvent[] {
  const phase_id = `${runId}_0${seq}_${name}`;
  const instance_id = `${runId}:${key}`;
  return [
    ev(runId, "cleanup", {
      phase_id,
      phase_name: name,
      instance_id,
      message: "cleanup ok",
      t,
    }),
    ev(runId, "phase_end", {
      phase_id,
      phase_name: name,
      instance_id: phase_id,
      status,
      t,
    }),
  ];
}

export class FakeClock implements IClock {
  constructor(public ms = T0) {}
  now(): number {
    return this.ms;
  }
  advance(seconds: number): void {
    this.ms += seconds * 1000;
  }
}

export class FakeTimer implements ITimer {
  pending: Array<{ id: number; callback: () => void; ms: number }> = [];
  private next = 1;
  set(callback: () => void, ms: number): unknown {
    this.pending.push({ id: this.next, callback, ms });
    return this.next++;
  }
  clear(handle: unknown): void {
    this.pending = this.pending.filter((entry) => entry.id !== handle);
  }
  /** Run every timer that was pending when this was called. */
  fire(): void {
    const due = this.pending;
    this.pending = [];
    for (const entry of due) entry.callback();
  }
}

export class MemoryClearStore implements IClearStore {
  marks: Record<string, number> = {};
  get(runId: string): number {
    return this.marks[runId] ?? 0;
  }
  set(runId: string, cursor: number): void {
    this.marks[runId] = cursor;
  }
}

export class FakeLegacyTerminal implements ILegacyTerminal {
  visible = true;
  setVisible(visible: boolean): void {
    this.visible = visible;
  }
}

export class ManualSource implements IAdwEventSource {
  listeners = new Set<FeedListener>();
  started = false;
  subscribe(listener: FeedListener): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }
  start(): void {
    this.started = true;
  }
  stop(): void {
    this.started = false;
  }
  woken = 0;
  wake(): void {
    this.woken += 1;
  }
  push(feed: FeedPage): void {
    for (const listener of this.listeners) listener.onPage(feed);
  }
  connection(state: Parameters<FeedListener["onConnection"]>[0]): void {
    for (const listener of this.listeners) listener.onConnection(state);
  }
}

export class ScriptedHttp implements IHttpJson {
  urls: string[] = [];
  constructor(private readonly replies: Array<FeedPage | Error>) {}
  async getJSON(url: string): Promise<unknown> {
    this.urls.push(url);
    const reply = this.replies.shift();
    if (!reply) throw new Error("no reply scripted");
    if (reply instanceof Error) throw reply;
    return reply;
  }
}
