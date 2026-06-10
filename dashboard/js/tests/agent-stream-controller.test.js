import { describe, expect, test } from "bun:test";
import { ConsoleView } from "../abstract/console-view.interface.js";
import { AgentStreamController } from "../implementation/agent-stream-controller.js";

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

const fakeHttp = (script) => {
  const calls = [];
  return {
    calls,
    getJSON: async (url) => {
      calls.push(url);
      const next = script.shift();
      if (next instanceof Error) throw next;
      return next;
    },
  };
};

describe("AgentStreamController (concrete PollingController)", () => {
  test("validates required ports", () => {
    expect(() => new AgentStreamController({})).toThrow(/requires/);
  });

  test("first empty poll shows the placeholder", async () => {
    const view = new BufferConsole();
    const http = fakeHttp([[]]);
    const c = new AgentStreamController({
      http,
      view,
      url: "/api/thoughts",
      agentId: "a1",
      label: "thoughts",
    });
    await c.poll();
    expect(http.calls[0]).toBe("/api/thoughts?agent=a1");
    expect(view.buffer).toContain("no thoughts recorded yet");
  });

  test("formats and dedups rows across polls", async () => {
    const view = new BufferConsole();
    const row = {
      date: "2026-06-07T10:00:00",
      type: "reasoning_message",
      text: "**Plan** do it",
    };
    const http = fakeHttp([
      [row],
      [row, { date: "2026-06-07T10:00:01", type: "x", text: "next" }],
    ]);
    const c = new AgentStreamController({
      http,
      view,
      url: "/api/thoughts",
      agentId: "a1",
    });

    await c.poll();
    expect(view.buffer).toContain('<span class="hdr">Plan</span>');
    expect(view.buffer).toContain("[2026-06-07 10:00:00]");

    await c.poll(); // the repeated row must not duplicate
    expect(view.buffer.match(/Plan/g).length).toBe(1);
    expect(view.buffer).toContain("next");
  });

  test("transport errors render an inline error line", async () => {
    const view = new BufferConsole();
    const http = fakeHttp([new Error("HTTP 500")]);
    const c = new AgentStreamController({
      http,
      view,
      url: "/api/messages",
      agentId: "a1",
    });
    await c.poll();
    expect(view.buffer).toContain("msi-line err");
    expect(view.buffer).toContain("HTTP 500");
  });

  test("start runs one poll then arms the injected scheduler", async () => {
    const view = new BufferConsole();
    const http = fakeHttp([[], []]);
    let armed = null;
    const c = new AgentStreamController({
      http,
      view,
      url: "/api/thoughts",
      agentId: "a1",
      intervalMs: 1234,
      setInterval: (fn, ms) => {
        armed = { fn, ms };
        return 99;
      },
      clearInterval: () => {},
    });
    await c.start();
    expect(http.calls.length).toBe(1);
    expect(armed.ms).toBe(1234);
    expect(c.isPolling).toBe(true);
    c.stop();
    expect(c.isPolling).toBe(false);
  });
});
