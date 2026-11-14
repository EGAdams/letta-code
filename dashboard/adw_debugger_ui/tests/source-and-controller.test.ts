import { describe, expect, it } from "vitest";
import type { ConnectionState, FeedPage } from "../src/contracts";
import { DebuggerController } from "../src/controller";
import { EarliestActiveRunPolicy } from "../src/domain/run-selection";
import { ProgressTimeoutStallPolicy } from "../src/domain/stall-policy";
import type { DebuggerView } from "../src/domain/view";
import { PollingEventSource } from "../src/infra/polling-event-source";
import { LastGoodDiagramRenderer } from "../src/infra/safe-renderer";
import {
  constructed,
  ended,
  ev,
  FakeClock,
  FakeLegacyTerminal,
  FakeTimer,
  ManualSource,
  MemoryClearStore,
  page,
  run,
  ScriptedHttp,
  started,
} from "./fixtures";

const settle = () => new Promise((resolve) => setTimeout(resolve, 0));
const OPTIONS = {
  url: "/feed",
  activeMs: 500,
  idleMs: 5000,
  retryStepMs: 1000,
  retryMaxMs: 5000,
  isActive: () => true,
};

describe("polling event source", () => {
  it("catches up first, then resumes from the cursor, across a lost connection", async () => {
    const first = page([run("r1")], constructed("r1", "a", "a"), {
      bootstrap: true,
    });
    const second = page([run("r1")], started("r1", "a", "a", 1));
    const http = new ScriptedHttp([
      first,
      new Error("Failed to fetch"),
      second,
    ]);
    const timer = new FakeTimer();
    const pages: FeedPage[] = [];
    const states: ConnectionState[] = [];
    const source = new PollingEventSource(http, timer, OPTIONS);
    source.subscribe({
      onPage: (p) => pages.push(p),
      onConnection: (s) => states.push(s),
    });
    source.start();
    await settle();
    timer.fire();
    await settle();
    expect(timer.pending[0].ms).toBe(1000); // backing off, not hammering
    timer.fire();
    await settle();
    expect(http.urls).toEqual([
      "/feed",
      `/feed?after=${first.cursor}`,
      `/feed?after=${first.cursor}`,
    ]);
    expect(pages).toEqual([first, second]);
    expect(states.map((s) => s.status)).toEqual([
      "connecting",
      "connected",
      "disconnected",
      "connected",
    ]);
    expect(states[2]).toMatchObject({ reason: "Failed to fetch", attempts: 1 });
  });

  it("reports an unreadable trace as degraded, and delivers no page for it", async () => {
    const http = new ScriptedHttp([
      page([], [], {
        ok: false,
        error: "OperationalError: unable to open database file",
      }),
    ]);
    const states: ConnectionState[] = [];
    const pages: FeedPage[] = [];
    const source = new PollingEventSource(http, new FakeTimer(), OPTIONS);
    source.subscribe({
      onPage: (p) => pages.push(p),
      onConnection: (s) => states.push(s),
    });
    source.start();
    await settle();
    expect(states.at(-1)).toEqual({
      status: "degraded",
      reason: "OperationalError: unable to open database file",
    });
    expect(pages).toEqual([]);
  });

  it("asks at once when woken, instead of waiting out the idle interval", async () => {
    const http = new ScriptedHttp([page([], []), page([], [])]);
    const timer = new FakeTimer();
    const source = new PollingEventSource(http, timer, {
      ...OPTIONS,
      isActive: () => false,
    });
    source.start();
    await settle();
    expect(timer.pending[0].ms).toBe(5000);
    source.wake();
    await settle();
    expect(http.urls).toHaveLength(2);
    expect(timer.pending).toHaveLength(1); // still one timer chain, not two
  });

  it("stops asking once stopped", async () => {
    const http = new ScriptedHttp([page([], [])]);
    const timer = new FakeTimer();
    const source = new PollingEventSource(http, timer, OPTIONS);
    source.start();
    await settle();
    source.stop();
    expect(timer.pending).toEqual([]);
  });
});

function harness() {
  const source = new ManualSource();
  const clock = new FakeClock();
  const cleared = new MemoryClearStore();
  const legacy = new FakeLegacyTerminal();
  const timer = new FakeTimer();
  const controller = new DebuggerController({
    source,
    clock,
    cleared,
    legacy,
    timer,
    selection: new EarliestActiveRunPolicy(),
    stall: new ProgressTimeoutStallPolicy(),
    renderer: new LastGoodDiagramRenderer(),
  });
  let view!: DebuggerView;
  controller.start();
  controller.subscribe((next) => {
    view = next;
  });
  return {
    source,
    clock,
    cleared,
    legacy,
    timer,
    controller,
    view: () => view,
  };
}

/** Phase participants only; the ADW runner column is checked on its own. */
const phaseColumns = (view: DebuggerView) =>
  view.diagram.columns.filter((column) => column.kind === "phase");
const statuses = (view: DebuggerView) =>
  phaseColumns(view).map((column) => `${column.name}:${column.status}`);

describe("controller", () => {
  it("is honestly idle with nothing recorded, and Clear says why it is disabled", () => {
    const h = harness();
    h.source.push(page([], [], { bootstrap: true }));
    expect(h.view()).toMatchObject({
      runId: null,
      mode: "idle",
      modeLabel: "Idle -- no pilot run recorded yet",
    });
    expect(h.view().clearDisabledReason).toMatch(/No ADW run is selected/);
  });

  it("goes waiting -> running -> stalled -> running -> pass on the fake clock", () => {
    const h = harness();
    h.source.push(
      page(
        [run("r1")],
        [...constructed("r1", "a", "a"), ...constructed("r1", "b", "b")],
        { bootstrap: true },
      ),
    );
    expect(statuses(h.view())).toEqual(["a:waiting", "b:waiting"]);
    h.source.push(page([run("r1")], started("r1", "a", "a", 1)));
    expect(statuses(h.view())).toEqual(["a:running", "b:waiting"]);
    h.clock.advance(121);
    h.timer.fire();
    expect(statuses(h.view())).toEqual(["a:stalled", "b:waiting"]);
    expect(phaseColumns(h.view())[0].detail).toBe(
      "2m 1s -- no progress for 121s (timeout 120s)",
    );
    h.source.push(
      page(
        [run("r1")],
        [
          ev("r1", "progress", {
            phase_id: "r1_01_a",
            instance_id: "r1:a",
            t: 121,
          }),
        ],
      ),
    );
    expect(statuses(h.view())).toEqual(["a:running", "b:waiting"]);
    h.source.push(page([run("r1")], ended("r1", "a", "a", 1, "pass", 122)));
    expect(statuses(h.view())).toEqual(["a:pass", "b:waiting"]);
  });

  it("does not let another phase or an empty page reset a stall", () => {
    const h = harness();
    h.source.push(
      page(
        [run("r1"), run("r2", "running", 1)],
        [...constructed("r1", "a", "a"), ...started("r1", "a", "a", 1)],
      ),
    );
    h.clock.advance(130);
    h.source.push(
      page(
        [run("r1"), run("r2", "running", 1)],
        [
          ...constructed("r2", "a", "a", 130),
          ...started("r2", "a", "a", 1, 130),
        ],
      ),
    );
    h.source.push(page([run("r1"), run("r2", "running", 1)], []));
    expect(statuses(h.view())).toEqual(["a:stalled"]);
    expect(h.view().runId).toBe("r1");
  });

  it("uses the timeout the backend reports", () => {
    const h = harness();
    h.source.push(
      page(
        [run("r1")],
        [...constructed("r1", "a", "a"), ...started("r1", "a", "a", 1)],
        { stall_timeout_seconds: 5 },
      ),
    );
    h.clock.advance(6);
    h.timer.fire();
    expect(statuses(h.view())).toEqual(["a:stalled"]);
    expect(h.view().stallTimeoutSeconds).toBe(5);
  });

  it("pins a failed run against a later one; All events keeps the pin; Follow live releases it", () => {
    const h = harness();
    h.source.push(
      page(
        [run("r1")],
        [...constructed("r1", "a", "a"), ...started("r1", "a", "a", 1)],
      ),
    );
    h.source.push(page([run("r1", "fail")], ended("r1", "a", "a", 1, "fail")));
    h.source.push(
      page(
        [run("r1", "fail"), run("r2", "running", 5)],
        [...constructed("r2", "a", "a"), ...started("r2", "a", "a", 1)],
      ),
    );
    expect(h.view()).toMatchObject({ runId: "r1", mode: "pinned" });
    expect(statuses(h.view())).toEqual(["a:fail"]);
    h.controller.selectPhase("r1:a");
    h.controller.allEvents();
    expect(h.view()).toMatchObject({
      runId: "r1",
      mode: "pinned",
      phaseSelected: false,
    });
    expect(h.view().lines.some((line) => line.runId === "r2")).toBe(true); // real events keep arriving
    h.controller.followLive();
    expect(h.view()).toMatchObject({ runId: "r2", mode: "live" });
  });

  it("replaces a successful run with the next one and resets the phase selection", () => {
    const h = harness();
    h.source.push(
      page(
        [run("r1")],
        [...constructed("r1", "a", "a"), ...started("r1", "a", "a", 1)],
      ),
    );
    h.source.push(
      page([run("r1", "success")], ended("r1", "a", "a", 1, "pass")),
    );
    h.controller.selectPhase("r1:a");
    expect(h.view()).toMatchObject({
      runId: "r1",
      mode: "completed",
      phaseSelected: true,
    });
    expect(h.legacy.visible).toBe(false);
    h.source.push(
      page(
        [run("r1", "success"), run("r2", "running", 5)],
        constructed("r2", "a", "a"),
      ),
    );
    expect(h.view()).toMatchObject({
      runId: "r2",
      mode: "live",
      phaseSelected: false,
    });
    expect(h.legacy.visible).toBe(true);
  });

  it("keeps a finished phase's column and its phase filter as the next phase runs", () => {
    const h = harness();
    h.source.push(
      page(
        [run("r1")],
        [
          ...constructed("r1", "a", "a"),
          ...constructed("r1", "b", "b"),
          ...started("r1", "a", "a", 1),
        ],
      ),
    );
    h.controller.selectPhase("r1:a");
    h.source.push(
      page(
        [run("r1")],
        [...ended("r1", "a", "a", 1, "pass"), ...started("r1", "b", "b", 2)],
      ),
    );
    expect(statuses(h.view())).toEqual(["a:pass", "b:running"]);
    expect(h.view().filterLabel).toBe("Run r1 -- phase a (r1:a, attempt 1)");
    expect(h.view().lines.at(-1)?.kind).toBe("phase_end");
  });

  it("shows an interrupted run as stalled-and-uncertain, never as passed or cleaned up", () => {
    const h = harness();
    h.source.push(
      page(
        [run("r1")],
        [...constructed("r1", "a", "a"), ...started("r1", "a", "a", 1)],
      ),
    );
    h.source.push(page([run("r1", "interrupted")], []));
    expect(h.view()).toMatchObject({
      runStatus: "interrupted",
      mode: "pinned",
    });
    expect(phaseColumns(h.view())[0]).toMatchObject({
      status: "stalled",
      detail: "process ended without recording an outcome; no cleanup recorded",
    });
    expect(h.view().diagram.columns[0]).toMatchObject({
      kind: "runner",
      status: "stalled",
    });
  });

  it("reports a lost feed without changing any phase", () => {
    const h = harness();
    h.source.push(
      page(
        [run("r1")],
        [...constructed("r1", "a", "a"), ...started("r1", "a", "a", 1)],
      ),
    );
    h.source.connection({
      status: "disconnected",
      reason: "Failed to fetch",
      attempts: 2,
    });
    expect(h.view().connection.status).toBe("disconnected");
    expect(h.view()).toMatchObject({ runStatus: "running", mode: "live" });
    expect(statuses(h.view())).toEqual(["a:running"]);
  });

  it("keeps the last good diagram and says so when a model cannot be drawn", () => {
    const renderer = new LastGoodDiagramRenderer();
    const column = {
      instanceId: "x",
      name: "x",
      attempt: 1,
      status: "running" as const,
      statusLabel: "Running",
      detail: "",
      purpose: "",
      selected: false,
    };
    const good = { runId: "r1", columns: [column], rows: [] };
    expect(renderer.render(good)).toEqual({ model: good, error: "" });
    const bad = renderer.render({
      runId: "r1",
      columns: [column, column],
      rows: [],
    });
    expect(bad.model).toBe(good);
    expect(bad.error).toMatch(/duplicate or empty phase instance id/);
  });

  it("releases its subscription, timer and the legacy terminal on dispose", () => {
    const h = harness();
    h.controller.selectPhase("nothing");
    h.controller.dispose();
    expect(h.source.listeners.size).toBe(0);
    expect(h.source.started).toBe(false);
    expect(h.timer.pending).toEqual([]);
    expect(h.legacy.visible).toBe(true);
  });

  it("measures how long after recording an event was shown", () => {
    const h = harness();
    h.source.push(
      page([run("r1")], constructed("r1", "a", "a"), { bootstrap: true }),
    );
    expect(h.view().lastDelayMs).toBeNull();
    h.clock.advance(10.4);
    h.source.push(
      page([run("r1")], started("r1", "a", "a", 1, 10), {
        server_now: undefined as unknown as string,
      }),
    );
    expect(h.view().lastDelayMs).toBe(400);
  });
});
