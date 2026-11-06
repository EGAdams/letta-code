import { describe, expect, test } from "bun:test";
import { BackoffFetchRunner } from "../abstract/monitors/fetch/backoff-fetch-runner.js";
import { DedupFetchRunner } from "../abstract/monitors/fetch/dedup-fetch-runner.js";
import { LastGoodFetchRunner } from "../abstract/monitors/fetch/last-good-fetch-runner.js";

const scripted = (...results) => {
  const calls = [];
  return {
    calls,
    async run(url) {
      calls.push(url);
      const r = results[Math.min(calls.length - 1, results.length - 1)];
      if (r instanceof Error) throw r;
      return r;
    },
  };
};

describe("fetch runner decorators", () => {
  test("dedup shares one in-flight request per url", async () => {
    const inner = scripted({ a: 1 });
    const runner = new DedupFetchRunner(inner);
    const [x, y] = await Promise.all([runner.run("/u"), runner.run("/u")]);
    expect(x).toBe(y);
    expect(inner.calls).toHaveLength(1);
    await runner.run("/u");
    expect(inner.calls).toHaveLength(2);
  });

  test("backoff refuses a failing url until its wait passes, doubling", async () => {
    let now = 0;
    const inner = scripted(new Error("HTTP 500"), new Error("HTTP 500"), {
      ok: true,
    });
    const runner = new BackoffFetchRunner(inner, {
      baseMs: 1000,
      now: () => now,
    });
    await expect(runner.run("/u")).rejects.toThrow("HTTP 500");
    await expect(runner.run("/u")).rejects.toThrow("backing off");
    now = 1000;
    await expect(runner.run("/u")).rejects.toThrow("HTTP 500");
    now = 2500;
    await expect(runner.run("/u")).rejects.toThrow("backing off");
    now = 3000;
    expect(await runner.run("/u")).toEqual({ ok: true });
  });

  test("a 404 waits the long not-found delay", async () => {
    let now = 0;
    const runner = new BackoffFetchRunner(scripted(new Error("HTTP 404")), {
      notFoundMs: 60000,
      now: () => now,
    });
    await expect(runner.run("/u")).rejects.toThrow("HTTP 404");
    now = 59999;
    await expect(runner.run("/u")).rejects.toThrow("backing off");
  });

  test("last-good serves the old payload marked stale", async () => {
    const runner = new LastGoodFetchRunner(
      scripted({ v: 1 }, new Error("HTTP 502")),
    );
    expect(await runner.run("/u")).toEqual({ v: 1 });
    expect(await runner.run("/u")).toEqual({
      v: 1,
      stale: true,
      stale_error: "HTTP 502",
    });
    await expect(
      new LastGoodFetchRunner(scripted(new Error("x"))).run("/u"),
    ).rejects.toThrow("x");
  });
});
