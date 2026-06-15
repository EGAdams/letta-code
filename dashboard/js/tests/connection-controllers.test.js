import { describe, expect, test } from "bun:test";
import { ConsoleView } from "../abstract/console-view.interface.js";
import {
  ConnectionLogController,
  ConnectionTestController,
  classifyConnectionStatus,
} from "../implementation/connection-controllers.js";

class BufferConsole extends ConsoleView {
  constructor() {
    super();
    this.buffer = "";
  }
  writeHtml(h) {
    this.buffer += h;
  }
  replaceHtml(h) {
    this.buffer = h;
  }
  scrollToBottom() {}
}

const noopTimers = { setInterval: () => 1, clearInterval: () => {} };
const fakeHttp = (script) => ({
  getJSON: async () => {
    const next = Array.isArray(script) ? script.shift() : script;
    if (next instanceof Error) throw next;
    return next;
  },
});

describe("classifyConnectionStatus", () => {
  test("missing status => checking", () => {
    expect(classifyConnectionStatus(null)).toEqual({
      kind: "checking",
      ok: false,
      text: "checking…",
      label: "",
    });
  });
  test("ok => CONNECTED label", () => {
    expect(classifyConnectionStatus({ ok: true, text: "1ms" })).toEqual({
      kind: "up",
      ok: true,
      text: "1ms",
      label: "CONNECTED — ",
    });
  });
  test("not ok => DOWN label", () => {
    expect(classifyConnectionStatus({ ok: false, text: "timeout" })).toEqual({
      kind: "down",
      ok: false,
      text: "timeout",
      label: "DOWN — ",
    });
  });
});

describe("ConnectionLogController", () => {
  test("requires http, view, connKey", () => {
    expect(() => new ConnectionLogController({})).toThrow();
  });

  test("reports status and appends deduped rows", async () => {
    const view = new BufferConsole();
    const statuses = [];
    const c = new ConnectionLogController({
      http: fakeHttp([
        { status: { ok: true, text: "ok" }, rows: [{ seq: 1, text: "ping" }] },
        { status: { ok: true, text: "ok" }, rows: [{ seq: 1, text: "ping" }] },
      ]),
      view,
      connKey: "win10",
      onStatus: (s) => statuses.push(s),
      ...noopTimers,
    });
    await c.poll();
    await c.poll();
    expect(statuses[0].label).toBe("CONNECTED — ");
    // seq 1 appended once despite two polls.
    expect(view.buffer.match(/ping/g).length).toBe(1);
  });

  test("empty first render shows the connection placeholder", async () => {
    const view = new BufferConsole();
    const c = new ConnectionLogController({
      http: fakeHttp([{ status: { ok: true }, rows: [] }]),
      view,
      connKey: "win10",
      ...noopTimers,
    });
    await c.poll();
    expect(view.buffer).toContain("no connection tests recorded yet");
  });

  test("fetch error reports a down status", async () => {
    const view = new BufferConsole();
    let last;
    const c = new ConnectionLogController({
      http: fakeHttp(new Error("ssh boom")),
      view,
      connKey: "win10",
      onStatus: (s) => {
        last = s;
      },
      ...noopTimers,
    });
    await c.poll();
    expect(last).toEqual({
      kind: "down",
      ok: false,
      text: "ssh boom",
      label: "",
    });
  });
});

describe("ConnectionTestController", () => {
  test("returns the status on success", async () => {
    const c = new ConnectionTestController({
      http: fakeHttp({ ok: true, text: "12ms" }),
    });
    expect(await c.test("win10")).toEqual({
      ok: true,
      text: "12ms",
      failed: false,
    });
  });

  test("flags a transport failure", async () => {
    const c = new ConnectionTestController({
      http: fakeHttp(new Error("unreachable")),
    });
    expect(await c.test("win10")).toEqual({
      ok: false,
      text: "unreachable",
      failed: true,
    });
  });
});
