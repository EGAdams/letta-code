import { describe, expect, test } from "bun:test";
import { AgentActivityPoller } from "../implementation/agent-activity-poller.js";

const noopTimers = {
  setInterval: () => 1,
  clearInterval: () => {},
};

describe("AgentActivityPoller", () => {
  test("requires http and setStatus", () => {
    expect(() => new AgentActivityPoller({})).toThrow();
    expect(() => new AgentActivityPoller({ http: {} })).toThrow();
  });

  test("poll reports each agent's status via setStatus", async () => {
    const calls = [];
    const http = {
      getJSON: async () => ({ a1: "active", a2: "idle", a3: "error" }),
    };
    const poller = new AgentActivityPoller({
      http,
      setStatus: (id, status) => calls.push([id, status]),
      ...noopTimers,
    });
    await poller.poll();
    expect(calls).toEqual([
      ["a1", "active"],
      ["a2", "idle"],
      ["a3", "error"],
    ]);
  });

  test("a fetch failure is swallowed (loop survives)", async () => {
    const http = {
      getJSON: async () => {
        throw new Error("boom");
      },
    };
    const poller = new AgentActivityPoller({
      http,
      setStatus: () => {
        throw new Error("should not be called");
      },
      ...noopTimers,
    });
    await expect(poller.poll()).resolves.toBeUndefined();
  });

  test("start runs an immediate poll then arms the 5s interval", async () => {
    let armedMs = null;
    const http = { getJSON: async () => ({ a1: "active" }) };
    const calls = [];
    const poller = new AgentActivityPoller({
      http,
      setStatus: (id, s) => calls.push([id, s]),
      setInterval: (_fn, ms) => {
        armedMs = ms;
        return 7;
      },
      clearInterval: () => {},
    });
    await poller.start();
    expect(calls).toEqual([["a1", "active"]]);
    expect(armedMs).toBe(5000);
  });
});
