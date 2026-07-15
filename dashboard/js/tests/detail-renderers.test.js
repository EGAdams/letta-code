import { describe, expect, test } from "bun:test";
import {
  AgentCardRenderer,
  ChatDetailRenderer,
  composeSpokenText,
  InputOptionsRenderer,
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
    expect(html).toContain('<span class="hdr">assistant:</span>');
    expect(html).toContain("&lt;b&gt;");
  });

  test("renderReplyRows substitutes the agent's name for the assistant label", () => {
    const html = renderReplyRows(
      [{ type: "assistant_message", text: "hi" }],
      "Frita",
    );
    expect(html).toContain('<span class="hdr">Frita:</span>');
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
    speak: (t, name) => spoken.push({ t, name }),
  };
  const statuses = [];
  const onStatus = (agentId, status) => statuses.push({ agentId, status });
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
    onStatus,
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
    statuses,
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
    expect(speakBtn.textContent).toBe("🔊 Speak");

    await ctx.api.sendText("hi");
    // Spoken in the agent's own voice (per-agent voice).
    expect(ctx.spoken).toEqual([{ t: "spoken reply", name: "Scissari" }]);
  });

  test("sendText reports active then idle/error via onStatus", async () => {
    const ok = chatSetup({
      replies: [{ type: "assistant_message", text: "y" }],
    });
    await ok.api.sendText("hi");
    expect(ok.statuses).toEqual([
      { agentId: "a1", status: "active" },
      { agentId: "a1", status: "idle" },
    ]);

    const bad = chatSetup({ replies: [{ type: "error", text: "boom" }] });
    await bad.api.sendText("hi");
    expect(bad.statuses[1]).toEqual({ agentId: "a1", status: "error" });
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

  test("mode toggle flips auto/review label and Copy visibility", () => {
    const ctx = chatSetup();
    const modeBtn = ctx.container.querySelector(".am-mode");
    const copyBtn = ctx.container.querySelector(".am-copy");
    expect(modeBtn.dataset.mode).toBe("auto");
    expect(copyBtn.style.display).toBe("none"); // hidden while Auto Send
    modeBtn.click();
    expect(modeBtn.dataset.mode).toBe("review");
    expect(modeBtn.textContent).toBe("Review then Send");
    expect(copyBtn.style.display).toBe(""); // shown while reviewing
  });
});

describe("AgentCardRenderer (Strategy)", () => {
  test("fetches the card and renders identity / system message / lists", async () => {
    const doc = new FakeDocument();
    const c = doc.createElement("section");
    c.id = "agent-detail-agent-card";
    const http = {
      getJSON: async (url) => {
        expect(url).toBe("/api/agent-card?agent=a1");
        return {
          identity: "Frita",
          agent_id: "a1",
          system_message: "<sys>",
          role: "helper",
          responsibilities: ["r1", "r2"],
          tools: ["t1"],
          memory_summary: "mem",
        };
      },
    };
    await new AgentCardRenderer({ http, doc }).render(
      "agent-detail-agent-card",
      "a1",
    );
    expect(c.innerHTML).toContain("Frita");
    expect(c.innerHTML).toContain("&lt;sys&gt;"); // escaped system message
    expect(c.innerHTML).toContain("<li>r1</li>");
    expect(c.innerHTML).toContain("mem");
  });

  test("renders an error line when the fetch fails", async () => {
    const doc = new FakeDocument();
    const c = doc.createElement("section");
    c.id = "agent-detail-agent-card";
    const http = {
      getJSON: async () => {
        throw new Error("boom");
      },
    };
    await new AgentCardRenderer({ http, doc }).render(
      "agent-detail-agent-card",
      "a1",
    );
    expect(c.innerHTML).toContain("msi-line err");
    expect(c.innerHTML).toContain("boom");
  });
});

function inputOptionsSetup({ modelInfo } = {}) {
  const doc = new FakeDocument();
  const container = doc.createElement("section");
  container.id = "io";
  // The raw /api/test HTTP path must never be hit anymore — text only
  // reaches the agent through the letta-code terminal session.
  const posts = [];
  const gets = [];
  const http = {
    getJSON: async (url) => {
      gets.push(url);
      // /api/agent-model — the model dropdown loader. Default mimics a
      // non-Letta tab (dropdown hides) unless the test passes modelInfo.
      return modelInfo ?? { ok: false, options: [] };
    },
    postJSON: async (url, body) => {
      posts.push({ url, body });
      if (url === "/api/agent-model") return { ok: true, model: body.model };
      if (url === "/api/letta-code-message")
        return { ok: true, reply: "Hello from Mazda." };
      return { replies: [] };
    },
  };
  const spoken = [];
  const speech = {
    supported: true,
    cancel: () => {},
    speak: (t, name) => spoken.push({ t, name }),
  };
  const statuses = [];
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
  const sentLines = [];
  let terminalDisposed = false;
  const terminalFactory = () => ({
    dispose: () => {
      terminalDisposed = true;
    },
    sendLine: (text) => sentLines.push(text),
  });
  const r = new InputOptionsRenderer({
    http,
    speech,
    agentName: "Mazda",
    onStatus: (agentId, status) => statuses.push({ agentId, status }),
    doc,
    recorderFactory,
    terminalFactory,
  });
  const api = r.render("io", "a9");
  return {
    container,
    posts,
    gets,
    spoken,
    statuses,
    sentLines,
    api,
    get recorder() {
      return recorder;
    },
    get terminalDisposed() {
      return terminalDisposed;
    },
  };
}

describe("InputOptionsRenderer (Strategy)", () => {
  test("Send uses the clean Letta Code endpoint, never /api/test or terminal keystrokes", async () => {
    const ctx = inputOptionsSetup();
    ctx.container.querySelector(".am-test-input").value = "hello there";
    await ctx.api.send();
    expect(ctx.sentLines).toEqual([]);
    expect(ctx.posts).toEqual([
      {
        url: "/api/letta-code-message",
        body: { agent: "a9", text: "hello there" },
      },
    ]);
    expect(ctx.statuses).toEqual([{ agentId: "a9", status: "active" }]);
  });

  test("Send clears the input and echoes the user message", async () => {
    const ctx = inputOptionsSetup();
    const input = ctx.container.querySelector(".am-test-input");
    input.value = "hello there";
    await ctx.api.send();
    expect(input.value).toBe("");
    const out = ctx.container.querySelector(".am-test-out").innerHTML;
    expect(out).toContain('<span class="hdr">user:</span> hello there');
  });

  test("voice stop fills the textarea; Auto Send off does not send", async () => {
    const ctx = inputOptionsSetup();
    const startBtn = ctx.container.querySelector(".voice-btn");
    const handler = startBtn._listeners.click[0];
    await handler(); // start
    expect(ctx.recorder.isRecording).toBe(true);
    await handler(); // stop -> fills textarea, Auto Send off so no send
    expect(ctx.sentLines.length).toBe(0);
  });

  test("render() does not wire the klunky background terminal", async () => {
    const ctx = inputOptionsSetup();
    ctx.container.querySelector(".am-test-input").value = "hi";
    await ctx.api.send();
    expect(ctx.sentLines).toEqual([]);
    expect(ctx.terminalDisposed).toBe(false);
    expect(ctx.api.terminal).toBe(null);
  });

  test("model dropdown loads options from /api/agent-model and shows current", async () => {
    const ctx = inputOptionsSetup({
      modelInfo: {
        ok: true,
        current: "chatgpt-plus-pro/gpt-5.4-mini",
        options: [
          "chatgpt-plus-pro/gpt-5.5",
          "chatgpt-plus-pro/gpt-5.4",
          "chatgpt-plus-pro/gpt-5.4-mini",
        ],
      },
    });
    await Promise.resolve(); // let the getJSON .then() settle
    expect(ctx.gets).toEqual(["/api/agent-model?agent=a9"]);
    const sel = ctx.container.querySelector(".io-model-select");
    expect(sel.children.length).toBe(3);
    expect(sel.value).toBe("chatgpt-plus-pro/gpt-5.4-mini");
    expect(sel.disabled).toBe(false);
  });

  test("model dropdown change POSTs /api/agent-model with the new handle", async () => {
    const ctx = inputOptionsSetup({
      modelInfo: {
        ok: true,
        current: "chatgpt-plus-pro/gpt-5.4",
        options: ["chatgpt-plus-pro/gpt-5.4", "chatgpt-plus-pro/gpt-5.4-mini"],
      },
    });
    await Promise.resolve();
    const sel = ctx.container.querySelector(".io-model-select");
    sel.value = "chatgpt-plus-pro/gpt-5.4-mini";
    sel.dispatch("change", {});
    await Promise.resolve();
    await Promise.resolve();
    const modelPosts = ctx.posts.filter((p) => p.url === "/api/agent-model");
    expect(modelPosts).toEqual([
      {
        url: "/api/agent-model",
        body: { agent: "a9", model: "chatgpt-plus-pro/gpt-5.4-mini" },
      },
    ]);
  });

  test("model dropdown hides when the tab has no Letta agent", async () => {
    const ctx = inputOptionsSetup(); // default mock: { ok: false, options: [] }
    await Promise.resolve();
    const sel = ctx.container.querySelector(".io-model-select");
    expect(sel.parent.style.display).toBe("none");
  });
});
