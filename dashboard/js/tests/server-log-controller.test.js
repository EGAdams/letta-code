import { describe, expect, test } from "bun:test";
import { ConsoleView } from "../abstract/console-view.interface.js";
import {
  classifyServerStatus,
  ServerLogController,
} from "../implementation/server-log-controller.js";

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

const fakeHttp = (script) => ({
  getJSON: async () => {
    const next = script.shift();
    if (next instanceof Error) throw next;
    return next;
  },
});

describe("classifyServerStatus", () => {
  test("up / starting / down / none", () => {
    expect(classifyServerStatus({ ok: true, text: "running" }).kind).toBe("up");
    expect(classifyServerStatus({ ok: false, text: "STARTING up" }).kind).toBe(
      "starting",
    );
    expect(classifyServerStatus({ ok: false, text: "crashed" })).toEqual({
      kind: "down",
      ok: false,
      text: "crashed",
      label: "DOWN — ",
    });
    expect(classifyServerStatus(null).kind).toBe("none");
  });
  test("honors explicit kind:concern (down-but-restartable reads yellow)", () => {
    const r = classifyServerStatus({
      ok: false,
      kind: "concern",
      text: "unreachable: connection refused",
    });
    expect(r.kind).toBe("concern");
    expect(r.label).toBe("NEEDS ATTENTION — ");
  });
  test("kind:starting is honored even without STARTING text", () => {
    expect(
      classifyServerStatus({ ok: false, kind: "starting", text: "booting" })
        .kind,
    ).toBe("starting");
  });
});

describe("ServerLogController (concrete PollingController)", () => {
  test("validates required ports", () => {
    expect(() => new ServerLogController({})).toThrow(/requires/);
  });

  test("reports status and appends seq-deduped rows", async () => {
    const view = new BufferConsole();
    const statuses = [];
    const http = fakeHttp([
      {
        status: { ok: true, text: "running" },
        rows: [{ seq: 1, text: "boot" }],
      },
      {
        status: { ok: true, text: "running" },
        rows: [
          { seq: 1, text: "boot" },
          { seq: 2, text: "ready" },
        ],
      },
    ]);
    const c = new ServerLogController({
      http,
      view,
      serverKey: "executor",
      onStatus: (s) => statuses.push(s),
    });

    await c.poll();
    expect(statuses[0].kind).toBe("up");
    expect(view.buffer).toContain("boot");

    await c.poll();
    expect(view.buffer.match(/boot/g).length).toBe(1); // seq:1 not re-added
    expect(view.buffer).toContain("ready");
  });

  test("first empty poll shows a placeholder", async () => {
    const view = new BufferConsole();
    const http = fakeHttp([{ status: { ok: true, text: "up" }, rows: [] }]);
    const c = new ServerLogController({ http, view, serverKey: "x" });
    await c.poll();
    expect(view.buffer).toContain("no log lines");
  });

  test("transport error reports a down status", async () => {
    const view = new BufferConsole();
    let last;
    const http = fakeHttp([new Error("HTTP 502")]);
    const c = new ServerLogController({
      http,
      view,
      serverKey: "x",
      onStatus: (s) => {
        last = s;
      },
    });
    await c.poll();
    expect(last).toEqual({
      kind: "down",
      ok: false,
      text: "HTTP 502",
      label: "",
    });
  });
});
