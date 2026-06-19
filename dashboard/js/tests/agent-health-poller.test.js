import { describe, expect, test } from "bun:test";
import { AgentHealthPoller } from "../implementation/agent-health-poller.js";

const noopTimers = {
  setInterval: () => 1,
  clearInterval: () => {},
};

describe("AgentHealthPoller", () => {
  test("requires http and setHealth", () => {
    expect(() => new AgentHealthPoller({})).toThrow();
    expect(() => new AgentHealthPoller({ http: {} })).toThrow();
  });

  test("poll forwards ok=false for unhealthy agents (tab turns red)", async () => {
    const calls = [];
    const http = {
      getJSON: async () => ({
        "agent-abc": {
          ok: false,
          text: "Mazda Router: missing run_claude_code_sdk",
        },
        "agent-xyz": {
          ok: true,
          text: "Mazda Parser: run_claude_code_sdk present",
        },
      }),
    };
    const poller = new AgentHealthPoller({
      http,
      setHealth: (id, ok, text) => calls.push([id, ok, text]),
      ...noopTimers,
    });
    await poller.poll();
    expect(calls).toEqual([
      ["agent-abc", false, "Mazda Router: missing run_claude_code_sdk"],
      ["agent-xyz", true, "Mazda Parser: run_claude_code_sdk present"],
    ]);
  });

  test("a fetch failure is swallowed (loop survives)", async () => {
    const http = {
      getJSON: async () => {
        throw new Error("network error");
      },
    };
    const poller = new AgentHealthPoller({
      http,
      setHealth: () => {
        throw new Error("should not be called");
      },
      ...noopTimers,
    });
    await expect(poller.poll()).resolves.toBeUndefined();
  });

  test("polls on 30s interval", async () => {
    let armedMs = null;
    const calls = [];
    const http = {
      getJSON: async () => ({ "agent-abc": { ok: true, text: "ok" } }),
    };
    const poller = new AgentHealthPoller({
      http,
      setHealth: (id, ok) => calls.push([id, ok]),
      setInterval: (_fn, ms) => {
        armedMs = ms;
        return 9;
      },
      clearInterval: () => {},
    });
    await poller.start();
    expect(armedMs).toBe(30000);
    expect(calls).toEqual([["agent-abc", true]]);
  });
});
