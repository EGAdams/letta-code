import { describe, expect, test } from "bun:test";
import { HttpClient } from "../abstract/http-client.interface.js";

/** Test double: implement only the abstract transport. */
class FakeHttpClient extends HttpClient {
  constructor(responder) {
    super();
    this.responder = responder;
    this.calls = [];
  }
  async request(url, opts) {
    this.calls.push({ url, opts });
    return this.responder(url, opts);
  }
}

const okJson = (data) => ({ ok: true, status: 200, json: async () => data });
const errJson = (status, body) => ({
  ok: false,
  status,
  json: async () => body,
});

describe("HttpClient (Template Method)", () => {
  test("abstract request throws until overridden", async () => {
    await expect(new HttpClient().getJSON("/x")).rejects.toThrow(
      /request\(\) is abstract/,
    );
  });

  test("getJSON returns parsed body on 200", async () => {
    const c = new FakeHttpClient(() => okJson({ hello: "world" }));
    expect(await c.getJSON("/api/x")).toEqual({ hello: "world" });
    expect(c.calls[0].url).toBe("/api/x");
  });

  test("postJSON sends JSON body + content-type header", async () => {
    const c = new FakeHttpClient(() => okJson({ ok: true }));
    await c.postJSON("/api/test", { agent: "a1", text: "hi" });
    const { opts } = c.calls[0];
    expect(opts.method).toBe("POST");
    expect(opts.headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(opts.body)).toEqual({ agent: "a1", text: "hi" });
  });

  test("non-OK with detail throws trimmed HTTP error", async () => {
    const c = new FakeHttpClient(() =>
      errJson(404, { detail: "agent not found here" }),
    );
    await expect(c.getJSON("/api/x")).rejects.toThrow(
      "HTTP 404 — agent not found here",
    );
  });

  test("non-OK with non-JSON body still throws status", async () => {
    const c = new FakeHttpClient(() => ({
      ok: false,
      status: 500,
      json: async () => {
        throw new Error("not json");
      },
    }));
    await expect(c.getJSON("/api/x")).rejects.toThrow("HTTP 500");
  });
});
