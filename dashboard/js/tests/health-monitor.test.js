import { describe, expect, test } from "bun:test";
import { HealthMonitor } from "../abstract/health-monitor.interface.js";

class FakeMonitor extends HealthMonitor {
  constructor(payloads) {
    super();
    this.payloads = payloads;
    this.i = 0;
  }
  async fetchHealth() {
    const p = this.payloads[Math.min(this.i, this.payloads.length - 1)];
    this.i += 1;
    if (p instanceof Error) throw p;
    return p;
  }
}

describe("HealthMonitor.overallStatus", () => {
  test("starting beats down beats up", () => {
    expect(
      HealthMonitor.overallStatus({
        any_down: true,
        servers: [{ status: "starting" }, { status: "down" }],
      }),
    ).toBe("starting");
  });
  test("any_down with no starting => down", () => {
    expect(
      HealthMonitor.overallStatus({
        any_down: true,
        servers: [{ status: "down" }],
      }),
    ).toBe("down");
  });
  test("all healthy => up", () => {
    expect(
      HealthMonitor.overallStatus({
        any_down: false,
        servers: [{ status: "up" }],
      }),
    ).toBe("up");
  });
  test("concern (no down/starting) => concern", () => {
    expect(
      HealthMonitor.overallStatus({
        any_down: false,
        any_concern: true,
        servers: [{ status: "up" }, { status: "concern" }],
      }),
    ).toBe("concern");
  });
  test("down beats concern", () => {
    expect(
      HealthMonitor.overallStatus({
        any_down: true,
        any_concern: true,
        servers: [{ status: "down" }, { status: "concern" }],
      }),
    ).toBe("down");
  });
  test("null => unknown", () => {
    expect(HealthMonitor.overallStatus(null)).toBe("unknown");
  });
});

describe("HealthMonitor (Observer subject)", () => {
  test("abstract fetchHealth throws via poll path only after subscribe", async () => {
    expect(() => new HealthMonitor().fetchHealth()).toThrow(
      /fetchHealth\(\) is abstract/,
    );
  });

  test("poll stores health and notifies all observers", async () => {
    const health = { any_down: false, servers: [{ key: "a", status: "up" }] };
    const m = new FakeMonitor([health]);
    const seenA = [];
    const seenB = [];
    m.subscribe((h) => seenA.push(h));
    m.subscribe((h) => seenB.push(h));
    await m.poll();
    expect(m.health).toBe(health);
    expect(seenA).toEqual([health]);
    expect(seenB).toEqual([health]);
  });

  test("unsubscribe stops further notifications", async () => {
    const m = new FakeMonitor([
      { any_down: false, servers: [] },
      { any_down: true, servers: [] },
    ]);
    const seen = [];
    const off = m.subscribe((h) => seen.push(h));
    await m.poll();
    off();
    await m.poll();
    expect(seen).toHaveLength(1);
  });

  test("transport errors are swallowed; last health retained", async () => {
    const good = { any_down: false, servers: [] };
    const m = new FakeMonitor([good, new Error("ECONNREFUSED")]);
    await m.poll();
    await m.poll(); // throws internally, swallowed
    expect(m.health).toBe(good);
  });
});
