import { describe, expect, test } from "bun:test";
import { FetchHttpClient } from "../implementation/fetch-http-client.js";

const okJson = (data) => ({ ok: true, status: 200, json: async () => data });

describe("FetchHttpClient (concrete HttpClient)", () => {
  test("throws without a fetch implementation", () => {
    expect(() => new FetchHttpClient(null)).toThrow(/requires a fetch/);
  });

  test("getJSON delegates to the injected fetch and unwraps", async () => {
    const calls = [];
    const client = new FetchHttpClient((url, opts) => {
      calls.push({ url, opts });
      return Promise.resolve(okJson({ a: 1 }));
    });
    expect(await client.getJSON("/api/x")).toEqual({ a: 1 });
    expect(calls[0].url).toBe("/api/x");
    expect(calls[0].opts).toBeUndefined();
  });

  test("postJSON builds a POST through the base policy", async () => {
    let seen;
    const client = new FetchHttpClient((url, opts) => {
      seen = { url, opts };
      return Promise.resolve(okJson({ ok: true }));
    });
    await client.postJSON("/api/test", { agent: "a1", text: "hi" });
    expect(seen.opts.method).toBe("POST");
    expect(JSON.parse(seen.opts.body)).toEqual({ agent: "a1", text: "hi" });
  });

  test("inherits the trimmed-error policy on non-OK", async () => {
    const client = new FetchHttpClient(() =>
      Promise.resolve({
        ok: false,
        status: 404,
        json: async () => ({ detail: "nope" }),
      }),
    );
    await expect(client.getJSON("/x")).rejects.toThrow("HTTP 404 — nope");
  });
});
