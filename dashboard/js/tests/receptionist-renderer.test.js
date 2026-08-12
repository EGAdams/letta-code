import { describe, expect, test } from "bun:test";
import { ListenerState } from "../abstract/continuous-listener.interface.js";
import { RecorderState } from "../abstract/voice-recorder.interface.js";
import { InputOptionsRenderer } from "../implementation/detail-renderers.js";
import { FakeDocument } from "./_fake-dom.js";

class FakeListener {
  constructor() {
    this.state = ListenerState.IDLE;
    this._onResult = () => {};
    this._onStateChange = () => {};
  }
  get isListening() {
    return this.state === ListenerState.LISTENING;
  }
  setCallbacks(callbacks) {
    this._onResult = callbacks.onResult || this._onResult;
    this._onStateChange = callbacks.onStateChange || this._onStateChange;
  }
  emit(text, isFinal) {
    this._onResult(text, isFinal);
  }
}

function setup(policy = null) {
  const doc = new FakeDocument();
  const container = doc.createElement("section");
  container.id = "receptionist-box";
  const listener = new FakeListener();
  const posts = [];
  const http = {
    getJSON: async () => ({ ok: false, options: [] }),
    postJSON: async (url, body) => {
      posts.push({ url, body });
      return { ok: true, reply: "Toyota reply" };
    },
  };
  const recorderFactory = (opts) => ({
    isRecording: false,
    start: async () => {
      opts.onStateChange(RecorderState.RECORDING);
      return true;
    },
    stop: async () => ({ cleaned_text: "" }),
  });
  const api = new InputOptionsRenderer({
    http,
    speech: { supported: false },
    agentName: "Toyota",
    agentId: "toyota-id",
    doc,
    storage: { getItem: () => null, setItem: () => {} },
    recorderFactory,
    listener,
    receptionistIntentPolicy: policy,
  }).render("receptionist-box", "toyota-id");
  return { container, listener, posts, api };
}

describe("Toyota receptionist renderer", () => {
  test("keeps every heard interim and final word in the text box", () => {
    const ctx = setup();
    const input = ctx.container.querySelector(".am-test-input");
    ctx.listener.emit("Hey Toyota", false);
    expect(input.value).toBe("Hey Toyota");
    ctx.listener.emit("Hey Toyota, I need help", true);
    expect(input.value).toBe("Hey Toyota, I need help");
    ctx.listener.emit("with the agenda", false);
    expect(input.value).toBe("Hey Toyota, I need help with the agenda");
    ctx.listener.emit("with the agenda", true);
    expect(input.value).toBe("Hey Toyota, I need help with the agenda");
    expect(ctx.posts).toEqual([]);
  });

  test("cleans and sends an addressed request while retaining the transcript", async () => {
    const ctx = setup({
      evaluate: async () => ({
        addressed: true,
        cleaned_text: "Let me talk to Mazda.",
      }),
    });
    const input = ctx.container.querySelector(".am-test-input");
    ctx.listener.emit("Hey Toyota, let me talk to Mazda", true);
    await Promise.resolve();
    await Promise.resolve();
    expect(input.value).toBe("Hey Toyota, let me talk to Mazda");
    expect(ctx.posts).toContainEqual({
      url: "/api/letta-code-message",
      body: { agent: "toyota-id", text: "Let me talk to Mazda." },
    });
  });

  test("keeps uncertain speech visible without sending", async () => {
    const ctx = setup({
      evaluate: async () => ({ addressed: false, cleaned_text: "" }),
    });
    ctx.listener.emit("I was thinking about Mazda", true);
    await Promise.resolve();
    await Promise.resolve();
    expect(ctx.posts).toEqual([]);
    expect(ctx.container.querySelector(".am-test-input").value).toBe(
      "I was thinking about Mazda",
    );
  });
});
