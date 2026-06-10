import { describe, expect, test } from "bun:test";
import {
  buildServerActionRequest,
  ServerActionController,
} from "../implementation/server-action-controller.js";

// Fake HttpClient that records postJSON calls and returns a scripted result.
const fakeHttp = (result) => {
  const calls = [];
  return {
    calls,
    postJSON: async (url, body) => {
      calls.push({ url, body });
      if (result instanceof Error) throw result;
      return result;
    },
  };
};

describe("buildServerActionRequest", () => {
  test("builds the /api/server-action payload", () => {
    expect(buildServerActionRequest("executor", "start")).toEqual({
      url: "/api/server-action",
      body: { server: "executor", action: "start" },
    });
  });

  test("requires both server and action", () => {
    expect(() => buildServerActionRequest("", "start")).toThrow(/requires/);
    expect(() => buildServerActionRequest("executor", "")).toThrow(/requires/);
  });
});

describe("ServerActionController (Command)", () => {
  test("validates the http port", () => {
    expect(() => new ServerActionController({})).toThrow(/requires/);
    expect(() => new ServerActionController({ http: {} })).toThrow(/requires/);
  });

  test("start() POSTs the start action and returns {ok, text}", async () => {
    const http = fakeHttp({
      ok: true,
      text: "Started executor server (exit code 0)",
    });
    const c = new ServerActionController({ http });

    const res = await c.start("executor");

    expect(http.calls).toEqual([
      {
        url: "/api/server-action",
        body: { server: "executor", action: "start" },
      },
    ]);
    expect(res).toEqual({
      ok: true,
      text: "Started executor server (exit code 0)",
    });
  });

  test("start() defaults to the executor server", async () => {
    const http = fakeHttp({ ok: true, text: "ok" });
    const c = new ServerActionController({ http });
    await c.start();
    expect(http.calls[0].body.server).toBe("executor");
  });

  test("start() surfaces a backend not-ok result without throwing", async () => {
    const http = fakeHttp({ ok: false, text: "SSH command timed out" });
    const c = new ServerActionController({ http });
    const res = await c.start("executor");
    expect(res).toEqual({ ok: false, text: "SSH command timed out" });
  });

  test("start() turns a transport error into {ok:false, text}", async () => {
    const http = fakeHttp(new Error("HTTP 502"));
    const c = new ServerActionController({ http });
    const res = await c.start("executor");
    expect(res).toEqual({ ok: false, text: "HTTP 502" });
  });
});
