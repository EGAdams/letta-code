import { describe, expect, test } from "bun:test";
import { HealthMonitor } from "../abstract/health-monitor.interface.js";
import { ServerHealthMonitor } from "../implementation/server-health-monitor.js";

const fakeHttp = (payload, { fail = false } = {}) => ({
  getJSON: async () => {
    if (fail) throw new Error("boom");
    return payload;
  },
});

describe("ServerHealthMonitor (concrete HealthMonitor)", () => {
  test("requires an HttpClient", () => {
    expect(() => new ServerHealthMonitor(null)).toThrow(
      /requires an HttpClient/,
    );
  });

  test("poll fetches, stores, and notifies observers", async () => {
    const payload = { any_down: false, servers: [{ key: "a", status: "up" }] };
    const m = new ServerHealthMonitor(fakeHttp(payload));
    const seen = [];
    m.subscribe((h) => seen.push(h));
    await m.poll();
    expect(m.health).toEqual(payload);
    expect(seen).toEqual([payload]);
  });

  test("poll swallows transport errors and keeps last health", async () => {
    const m = new ServerHealthMonitor(fakeHttp(null, { fail: true }));
    let notified = 0;
    m.subscribe(() => notified++);
    await m.poll();
    expect(m.health).toBeNull();
    expect(notified).toBe(0);
  });

  test("inherits overallStatus reducer (starting wins over down)", () => {
    expect(
      HealthMonitor.overallStatus({
        any_down: true,
        servers: [{ status: "starting" }],
      }),
    ).toBe("starting");
  });
});
