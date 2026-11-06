import { describe, expect, test } from "bun:test";
import { IObserver } from "../abstract/monitors/interfaces/observer.interface.js";
import { worstLevel } from "../abstract/monitors/levels/level-rank.js";
import { statusLevel } from "../abstract/monitors/levels/status-level.js";
import { MonitorSource } from "../abstract/monitors/sources/monitor-source.js";
import { FunctionProcessor } from "../abstract/monitors/sources/parsers/function-processor.js";
import { parseServerHealth } from "../abstract/monitors/sources/parsers/server-health-parser.js";
import { PollScheduler } from "../abstract/monitors/sources/poll-scheduler.js";
import { TabAlertObserver } from "../abstract/monitors/tab-alert-observer.js";
import { FakeDocument } from "./_fake-dom.js";

const source = (runner) =>
  new MonitorSource({
    key: "s",
    label: "Servers",
    url: "/api/server-health",
    view: "gauge",
    processor: new FunctionProcessor(parseServerHealth),
    runner,
  });

class Spy extends IObserver {
  constructor() {
    super();
    this.seen = [];
  }
  update(subject) {
    this.seen.push(subject.snapshot.level);
  }
}

describe("monitor sources", () => {
  test("refresh parses, keeps the snapshot and notifies observers", async () => {
    const src = source({ run: async () => ({ servers: [{ status: "up" }] }) });
    const spy = new Spy();
    src.attach(spy);
    src.attach(spy);
    await src.refresh();
    expect(spy.seen).toEqual(["ok"]);
    src.detach(spy);
    await src.refresh();
    expect(spy.seen).toEqual(["ok"]);
  });

  test("a failed fetch becomes an 'unknown' snapshot, not a throw", async () => {
    const src = source({
      run: async () => {
        throw new Error("HTTP 500");
      },
    });
    expect((await src.refresh()).level).toBe("unknown");
    expect(src.snapshot.detail).toContain("HTTP 500");
  });

  test("scheduler skips ticks while inactive and stops cleanly", async () => {
    let refreshed = 0;
    const timers = {
      setInterval: () => 7,
      clearInterval: (h) => {
        timers.cleared = h;
      },
    };
    let active = false;
    const scheduler = new PollScheduler(
      [
        {
          refresh: async () => {
            refreshed += 1;
          },
        },
      ],
      { isActive: () => active, timers },
    );
    scheduler.start();
    await scheduler.tick();
    active = true;
    await scheduler.tick();
    expect(refreshed).toBe(1);
    scheduler.stop();
    expect(timers.cleared).toBe(7);
  });

  test("tab alert observer blinks the tab by the worst level", async () => {
    const tab = new FakeDocument().createElement("button");
    const down = source({
      run: async () => ({ servers: [{ status: "down" }] }),
    });
    const observer = new TabAlertObserver(tab);
    observer.watch(down);
    await down.refresh();
    expect(tab.classList.contains("tab-alert-red")).toBe(true);
    expect(tab.classList.contains("tab-alert")).toBe(false);
  });

  test("levels", () => {
    expect(worstLevel(["ok", "warn", "unknown"])).toBe("warn");
    expect(worstLevel([])).toBe("unknown");
    expect(statusLevel("Normal")).toBe("ok");
    expect(statusLevel("down")).toBe("crit");
    expect(statusLevel("weird")).toBe("unknown");
  });
  test("scheduler's default timers survive being called as methods", () => {
    const scheduler = new PollScheduler([], { isActive: () => false });
    scheduler.start();
    expect(scheduler._handle).not.toBe(null);
    scheduler.stop();
  });
});
