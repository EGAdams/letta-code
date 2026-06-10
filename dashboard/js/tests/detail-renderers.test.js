import { describe, expect, test } from "bun:test";
import {
  ChatDetailRenderer,
  composeSpokenText,
  renderReplyRows,
  StreamDetailRenderer,
} from "../implementation/detail-renderers.js";
import { FakeDocument } from "./_fake-dom.js";

describe("chat pure helpers", () => {
  test("composeSpokenText prefers assistant/send_message replies", () => {
    const replies = [
      { type: "reasoning_message", text: "thinking" },
      { type: "assistant_message", text: "Hello" },
      { type: "send_message", text: "there" },
    ];
    expect(composeSpokenText(replies)).toBe("Hello. there");
  });

  test("composeSpokenText falls back to all replies when none preferred", () => {
    expect(composeSpokenText([{ type: "tool_call", text: "x" }])).toBe("x");
    expect(composeSpokenText([])).toBe("");
  });

  test("renderReplyRows escapes and labels rows", () => {
    expect(renderReplyRows([])).toContain("no reply content");
    const html = renderReplyRows([{ type: "assistant_message", text: "<b>" }]);
    expect(html).toContain('<span class="hdr">assistant</span>');
    expect(html).toContain("&lt;b&gt;");
  });
});

describe("StreamDetailRenderer (Strategy)", () => {
  test("mounts a view, builds a controller, and hands it to the poller", () => {
    const doc = new FakeDocument();
    const container = doc.createElement("section");
    container.id = "agent-detail-thoughts";

    const poller = {
      ran: [],
      run(c) {
        this.ran.push(c);
      },
    };
    let args;
    const r = new StreamDetailRenderer({
      http: { tag: "http" },
      url: "/api/thoughts",
      label: "thoughts",
      poller,
      doc,
      viewFactory: () => ({ view: true }),
      controllerFactory: (opts) => {
        args = opts;
        return { ctrl: true };
      },
    });

    const ctrl = r.render("agent-detail-thoughts", "a1");
    expect(args.url).toBe("/api/thoughts");
    expect(args.agentId).toBe("a1");
    expect(args.label).toBe("thoughts");
    expect(args.http).toEqual({ tag: "http" });
    expect(poller.ran[0]).toBe(ctrl);
  });

  test("missing container is a no-op", () => {
    const doc = new FakeDocument();
    const poller = {
      ran: [],
      run(c) {
        this.ran.push(c);
      },
    };
    const r = new StreamDetailRenderer({ http: {}, url: "/x", poller, doc });
    expect(r.render("nope", "a1")).toBeUndefined();
    expect(poller.ran.length).toBe(0);
  });
});

function chatSetup({ replies = [] } = {}) {
  const doc = new FakeDocument();
  const container = doc.createElement("section");
  container.id = "chat";

  const posts = [];
  const http = {
    postJSON: async (url, body) => {
      posts.push({ url, body });
      return { replies };
    },
  };
  const spoken = [];
  const speech = {
    supported: true,
    cancel: () => {},
    speak: (t) => spoken.push(t),
  };
  const storage = new Map();
  const storagePort = {
    getItem: (k) => (storage.has(k) ? storage.get(k) : null),
    setItem: (k, v) => storage.set(k, v),
  };

  let recorder;
  const recorderFactory = (opts) => {
    let recording = false;
    recorder = {
      opts,
      get isRecording() {
        return recording;
      },
      start: async () => {
        recording = true;
        return true;
      },
      stop: async () => {
        recording = false;
        return { raw_transcript: "hi", cleaned_text: "Hi." };
      },
    };
    return recorder;
  };

  const r = new ChatDetailRenderer({
    http,
    speech,
    agentName: "Scissari",
    doc,
    storage: storagePort,
    recorderFactory,
  });
  const api = r.render("chat", "a1");
  return {
    doc,
    container,
    posts,
    spoken,
    storage,
    api,
    get recorder() {
      return recorder;
    },
  };
}

describe("ChatDetailRenderer (Strategy)", () => {
  test("sendText posts to /api/test with the agent id and renders replies", async () => {
    const ctx = chatSetup({
      replies: [{ type: "assistant_message", text: "yo" }],
    });
    await ctx.api.sendText("hello");
    expect(ctx.posts[0]).toEqual({
      url: "/api/test",
      body: { agent: "a1", text: "hello" },
    });
    const out = ctx.container.querySelector(".msi-inner");
    expect(out.innerHTML).toContain("yo");
  });

  test("speak toggle persists preference and speaks on reply when on", async () => {
    const ctx = chatSetup({
      replies: [{ type: "assistant_message", text: "spoken reply" }],
    });
    const speakBtn = ctx.container.querySelector(".am-speak");
    speakBtn.click();
    expect(ctx.storage.get("dash-speak-replies")).toBe("1");
    expect(speakBtn.textContent).toContain("Speaking On");

    await ctx.api.sendText("hi");
    expect(ctx.spoken).toEqual(["spoken reply"]);
  });

  test("voice capture: start then stop auto-sends the cleaned transcript", async () => {
    const ctx = chatSetup({ replies: [] });
    const voiceBtn = ctx.container.querySelector(".voice-btn");
    const handler = voiceBtn._listeners.click[0];

    await handler(); // idle -> recording
    expect(ctx.recorder.isRecording).toBe(true);

    await handler(); // recording -> stop -> auto send (mode defaults to auto)
    expect(ctx.posts[0].body.text).toBe("Hi.");
  });

  test("mode toggle flips auto/review label", () => {
    const ctx = chatSetup();
    const modeBtn = ctx.container.querySelector(".am-mode");
    expect(modeBtn.dataset.mode).toBe("auto");
    modeBtn.click();
    expect(modeBtn.dataset.mode).toBe("review");
    expect(modeBtn.textContent).toBe("Review then Send");
  });
});
