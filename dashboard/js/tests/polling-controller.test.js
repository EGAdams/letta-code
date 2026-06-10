import { describe, expect, test } from "bun:test";
import { PollingController } from "../abstract/polling-controller.interface.js";

/** A manual scheduler so tests control ticks deterministically. */
function fakeScheduler() {
  let handle = 0;
  const timers = new Map();
  return {
    setInterval: (fn, ms) => {
      handle += 1;
      timers.set(handle, { fn, ms });
      return handle;
    },
    clearInterval: (h) => timers.delete(h),
    tick: (h) => timers.get(h)?.fn(),
    count: () => timers.size,
  };
}

class CountingPoller extends PollingController {
  constructor(opts) {
    super(opts);
    this.polls = 0;
  }
  async poll() {
    this.polls += 1;
  }
}

describe("PollingController (Template Method)", () => {
  test("abstract poll throws until overridden", async () => {
    const sched = fakeScheduler();
    const p = new PollingController(sched);
    await expect(p.start()).rejects.toThrow(/poll\(\) is abstract/);
  });

  test("start polls immediately then arms the interval", async () => {
    const sched = fakeScheduler();
    const p = new CountingPoller({ intervalMs: 1000, ...sched });
    await p.start();
    expect(p.polls).toBe(1); // immediate
    expect(p.isPolling).toBe(true);
    expect(sched.count()).toBe(1);
  });

  test("each tick triggers another poll", async () => {
    const sched = fakeScheduler();
    const p = new CountingPoller({ ...sched });
    await p.start();
    sched.tick(p._timer);
    sched.tick(p._timer);
    expect(p.polls).toBe(3); // 1 immediate + 2 ticks
  });

  test("stop clears the timer and is idempotent", async () => {
    const sched = fakeScheduler();
    const p = new CountingPoller({ ...sched });
    await p.start();
    p.stop();
    expect(p.isPolling).toBe(false);
    expect(sched.count()).toBe(0);
    expect(() => p.stop()).not.toThrow();
  });

  test("start stops any previous loop first (no leaks)", async () => {
    const sched = fakeScheduler();
    const p = new CountingPoller({ ...sched });
    await p.start();
    await p.start();
    expect(sched.count()).toBe(1);
  });
});
