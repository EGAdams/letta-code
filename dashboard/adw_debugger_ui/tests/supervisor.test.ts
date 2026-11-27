import { describe, expect, it } from "vitest";
import type {
  ConnectionState,
  ISupervisorEventSource,
  SupervisorEvent,
  SupervisorListener,
  SupervisorPage,
} from "../src/contracts";
import { DebuggerController } from "../src/controller";
import { NewestRunPolicy } from "../src/domain/run-selection";
import { ProgressTimeoutStallPolicy } from "../src/domain/stall-policy";
import { linesFor } from "../src/domain/supervisor";
import type { DebuggerView } from "../src/domain/view";
import { LastGoodDiagramRenderer } from "../src/infra/safe-renderer";
import { PollingSupervisorSource } from "../src/infra/supervisor-source";
import {
  constructed,
  FakeClock,
  FakeLegacyTerminal,
  FakeTimer,
  ManualSource,
  MemoryClearStore,
  page,
  run,
} from "./fixtures";

const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

function sup(over: Partial<SupervisorEvent>): SupervisorEvent {
  return {
    at: "2026-11-27T10:00:00Z",
    machine: "SQMC",
    agent: "supervisor-sqmc",
    kind: "log",
    state: "",
    message: "",
    task_id: "",
    bridge_task_id: "",
    request_id: "",
    adw_id: "",
    source: "run.log",
    ...over,
  };
}

function supPage(
  events: SupervisorEvent[],
  gaps: string[] = [],
): SupervisorPage {
  return {
    ok: true,
    error: "",
    machine: "SQMC",
    server_now: "2026-11-27T10:00:05Z",
    supervisor_events: events,
    gaps,
  };
}

class HttpByUrl {
  urls: string[] = [];
  constructor(private readonly reply: (url: string) => unknown) {}
  async getJSON(url: string): Promise<unknown> {
    this.urls.push(url);
    const value = this.reply(url);
    if (value instanceof Error) throw value;
    return value;
  }
}

const OPTIONS = {
  url: "/api/live-activity",
  activeMs: 3000,
  idleMs: 15000,
  retryStepMs: 2000,
  retryMaxMs: 15000,
  isActive: () => true,
};

describe("supervisor filtering", () => {
  const events = [
    sup({
      kind: "heartbeat",
      state: "alive",
      message: "last cron watch 40s ago",
    }),
    sup({ kind: "wake", state: "open", task_id: "inc1", message: "inc1 woke" }),
    sup({ kind: "handoff.todo", adw_id: "ab12cd34", task_id: "h1" }),
    sup({
      agent: "supervisor-bati",
      machine: "BATI",
      kind: "mail.held",
      task_id: "m1",
    }),
  ];

  it("keeps everything by default and filters by agent", () => {
    expect(linesFor(events, { agent: "", runId: null })).toHaveLength(4);
    const bati = linesFor(events, { agent: "supervisor-bati", runId: null });
    expect(bati.map((l) => l.kind)).toEqual(["mail.held"]);
  });

  it("correlates only on ids the source recorded, never by guessing", () => {
    expect(
      linesFor(events, { agent: "", runId: "ab12cd34" }).map((l) => l.kind),
    ).toEqual(["handoff.todo"]);
    expect(linesFor(events, { agent: "", runId: "nope" })).toEqual([]);
    expect(linesFor(events, { agent: "", runId: "inc1" })).toHaveLength(1); // post-office/task id
  });
});

describe("supervisor polling source", () => {
  it("asks the named machine and drops an answer for the machine it left", async () => {
    const http = new HttpByUrl((url) =>
      url.includes("machine=R46")
        ? supPage([sup({ machine: "R46" })])
        : supPage([]),
    );
    const timer = new FakeTimer();
    const source = new PollingSupervisorSource(http, timer, OPTIONS);
    const pages: SupervisorPage[] = [];
    source.subscribe({ onPage: (p) => pages.push(p), onConnection: () => {} });
    source.start();
    await settle();
    source.setMachine("R46");
    await settle();
    expect(http.urls).toEqual([
      "/api/live-activity",
      "/api/live-activity?machine=R46",
    ]);
    expect(pages.at(-1)?.supervisor_events[0].machine).toBe("R46");
  });

  it("reports a failed read as a connection problem and backs off", async () => {
    const http = new HttpByUrl(() => new Error("Failed to fetch"));
    const timer = new FakeTimer();
    const source = new PollingSupervisorSource(http, timer, OPTIONS);
    const states: ConnectionState[] = [];
    source.subscribe({ onPage: () => {}, onConnection: (s) => states.push(s) });
    source.start();
    await settle();
    expect(states.at(-1)).toMatchObject({
      status: "disconnected",
      attempts: 1,
    });
    expect(timer.pending[0].ms).toBe(2000);
  });
});

class ManualSupervisor implements ISupervisorEventSource {
  listeners = new Set<SupervisorListener>();
  machines: string[] = [];
  stopped = false;
  subscribe(l: SupervisorListener): () => void {
    this.listeners.add(l);
    return () => this.listeners.delete(l);
  }
  start(): void {}
  stop(): void {
    this.stopped = true;
  }
  wake(): void {}
  setMachine(m: string): void {
    this.machines.push(m);
  }
  push(p: SupervisorPage): void {
    for (const l of this.listeners) l.onPage(p);
  }
}

function build() {
  const source = new ManualSource();
  const supervisor = new ManualSupervisor();
  const cleared = new MemoryClearStore();
  const controller = new DebuggerController({
    source,
    supervisor,
    machines: ["", "SQMC", "BATI"],
    clock: new FakeClock(),
    cleared,
    legacy: new FakeLegacyTerminal(),
    timer: new FakeTimer(),
    selection: new NewestRunPolicy(),
    stall: new ProgressTimeoutStallPolicy(),
    renderer: new LastGoodDiagramRenderer(),
  });
  let view!: DebuggerView;
  controller.start();
  controller.subscribe((v) => {
    view = v;
  });
  return { controller, source, supervisor, cleared, view: () => view };
}

describe("supervisor events in the debugger view", () => {
  it("shows records beside a run, filters them, and clearing the run keeps them", () => {
    const t = build();
    t.source.push(
      page([run("ab12cd34")], constructed("ab12cd34", "a", "a"), {
        bootstrap: true,
      }),
    );
    t.supervisor.push(
      supPage(
        [
          sup({
            kind: "status",
            state: "awake",
            message: "supervisor is awake",
          }),
          sup({ kind: "handoff.todo", adw_id: "ab12cd34", task_id: "h1" }),
          sup({ kind: "recovery", state: "not fixed", task_id: "inc9" }),
        ],
        ["R46: unreachable"],
      ),
    );
    expect(t.view().supervisor.available).toBe(true);
    expect(t.view().supervisor.awake).toBe("awake");
    expect(t.view().supervisor.lines).toHaveLength(3);
    expect(t.view().supervisor.gaps).toEqual(["R46: unreachable"]);

    t.controller.toggleSupervisorCorrelation();
    expect(t.view().supervisor.lines.map((l) => l.kind)).toEqual([
      "handoff.todo",
    ]);

    t.controller.clearSelectedRun();
    expect(t.view().supervisor.total).toBe(3); // audit records are not the terminal
    expect(t.view().supervisor.lines).toHaveLength(1);

    t.controller.toggleSupervisorCorrelation();
    t.controller.selectSupervisorAgent("supervisor-sqmc");
    expect(t.view().supervisor.lines).toHaveLength(3);
  });

  it("switching machine asks that machine and empties the old records", () => {
    const t = build();
    t.supervisor.push(supPage([sup({})]));
    t.controller.selectSupervisorMachine("BATI");
    expect(t.supervisor.machines).toEqual(["BATI"]);
    expect(t.view().supervisor.machine).toBe("BATI");
    expect(t.view().supervisor.total).toBe(0);
  });

  it("is simply unavailable where no supervisor feed is given", () => {
    const controller = new DebuggerController({
      source: new ManualSource(),
      clock: new FakeClock(),
      cleared: new MemoryClearStore(),
      legacy: new FakeLegacyTerminal(),
      timer: new FakeTimer(),
      selection: new NewestRunPolicy(),
      stall: new ProgressTimeoutStallPolicy(),
      renderer: new LastGoodDiagramRenderer(),
    });
    let view!: DebuggerView;
    controller.subscribe((v) => {
      view = v;
    });
    expect(view.supervisor.available).toBe(false);
  });
});
