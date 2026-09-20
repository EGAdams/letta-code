import { describe, expect, test } from "bun:test";
import { ListenerState } from "../abstract/continuous-listener.interface.js";
import { SpokenOutputPolicy } from "../abstract/spoken-output-policy.js";
import { RecorderState } from "../abstract/voice-recorder.interface.js";
import { VoiceSession } from "../abstract/voice-session.js";
import {
  InputOptionsRenderer,
  LISTEN_ACTIVE_BG,
  LISTEN_IDLE_BG,
} from "../implementation/detail-renderers.js";
import { LettaAgentAdapter } from "../implementation/letta-agent-adapter.js";
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

  setState(state) {
    this.state = state;
    this._onStateChange(state);
  }
}

function setup({ policy, speech = { supported: false } } = {}) {
  const doc = new FakeDocument();
  const container = doc.createElement("section");
  container.id = "receptionist-box";
  doc.add(container);
  const listener = new FakeListener();
  const posts = [];
  const http = {
    getJSON: async () => ({ ok: false, options: [] }),
    postJSON: async (url, body) => {
      posts.push({ url, body });
      return url === "/api/letta-code-message"
        ? { ok: true, reply: "Toyota reply" }
        : { ok: true };
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
  const voiceSession = new VoiceSession();
  const api = new InputOptionsRenderer({
    http,
    voiceSession,
    spokenOutputPolicy: new SpokenOutputPolicy({ session: voiceSession }),
    conversationAgent: new LettaAgentAdapter({ http }),
    speech,
    agentName: "Toyota",
    agentId: "toyota-id",
    doc,
    storage: { getItem: () => null, setItem: () => {} },
    recorderFactory,
    listener,
    receptionistIntentPolicy: policy,
  }).render("receptionist-box", "toyota-id");
  return { container, listener, posts, api, voiceSession };
}

function playingSpeech() {
  let cancellations = 0;
  let finish;
  const finished = new Promise((resolve) => {
    finish = resolve;
  });
  return {
    speech: {
      supported: true,
      speak: () => ({
        pending: Promise.resolve("edge-tts"),
        finished,
        cancel: () => {
          cancellations += 1;
          finish();
        },
      }),
    },
    get cancellations() {
      return cancellations;
    },
  };
}

describe("Toyota receptionist renderer", () => {
  test("new recognized words interrupt an answer already playing", async () => {
    const audio = playingSpeech();
    const ctx = setup({ speech: audio.speech });
    await ctx.api.send({ textOverride: "First question" });
    expect(ctx.voiceSession.state).toBe("speaking");
    ctx.listener.emit(" ", false);
    expect(audio.cancellations).toBe(0);
    ctx.listener.emit("Second question", false);
    expect(audio.cancellations).toBe(1);
    expect(ctx.voiceSession.state).toBe("interrupted");
  });

  test("starting push-to-talk stops an answer already playing", async () => {
    const audio = playingSpeech();
    const ctx = setup({ speech: audio.speech });
    await ctx.api.send({ textOverride: "First question" });
    const startBtn = ctx.container.querySelector(".voice-btn");
    // The continuous-listening button is first; push-to-talk is the next one.
    const pushToTalk = ctx.container
      .querySelectorAll("button")
      .find((button) => button.textContent === "Start");
    expect(startBtn).not.toBeNull();
    pushToTalk.click();
    await Promise.resolve();
    expect(audio.cancellations).toBe(1);
    expect(ctx.voiceSession.state).toBe("interrupted");
  });
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

  test("cleans and sends only an addressed final utterance while retaining the transcript", async () => {
    const ctx = setup({
      policy: {
        evaluate: async () => ({
          addressed: true,
          cleaned_text: "Let me talk to Mazda.",
        }),
      },
    });
    const input = ctx.container.querySelector(".am-test-input");
    ctx.listener.emit("Hey Toyota, let me talk to Mazda", true);
    await Promise.resolve();
    await Promise.resolve();

    expect(input.value).toBe("Hey Toyota, let me talk to Mazda");
    expect(ctx.posts).toContainEqual({
      url: "/api/letta-code-message",
      body: {
        agent: "toyota-id",
        text: "Let me talk to Mazda.",
        conversation_id: null,
      },
    });
  });

  test("does not send when the policy is uncertain", async () => {
    const ctx = setup({
      policy: {
        evaluate: async () => ({ addressed: false, cleaned_text: "" }),
      },
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

describe("Toyota note-taking controls", () => {
  const buttonNamed = (container, label) =>
    container.querySelectorAll("button").find((b) => b.textContent === label) ||
    null;

  test("gives the editing conversation its own text box, separate from the note", () => {
    const ctx = setup();
    const note = ctx.container.querySelector(".am-test-input");
    const edit = ctx.container.querySelector(".am-edit-input");

    expect(edit).not.toBeNull();
    expect(edit).not.toBe(note);
    // Dictation must never leak into the box the user talks to Toyota in.
    ctx.listener.emit("buy milk", true);
    expect(note.value).toBe("buy milk");
    expect(edit.value).toBeFalsy();
  });

  test("Start Editing toggles to a blinking red Stop Editing and back", () => {
    const ctx = setup();
    const editBtn = buttonNamed(ctx.container, "Start Editing");

    expect(editBtn).not.toBeNull();
    expect(editBtn.style.background).toBe(LISTEN_IDLE_BG);
    expect(editBtn.style.animation).toBeFalsy();

    editBtn.click();
    expect(editBtn.textContent).toBe("Stop Editing");
    expect(editBtn.style.background).toBe(LISTEN_ACTIVE_BG);
    expect(editBtn.style.animation).toContain("listen-blink");

    editBtn.click();
    expect(editBtn.textContent).toBe("Start Editing");
    expect(editBtn.style.background).toBe(LISTEN_IDLE_BG);
    expect(editBtn.style.animation).toBeFalsy();
  });

  test("Start Listening uses the same green-to-blinking-red treatment", () => {
    const ctx = setup();
    const listenBtn = buttonNamed(ctx.container, "Start Listening");

    expect(listenBtn.style.background).toBe(LISTEN_IDLE_BG);
    ctx.listener.setState(ListenerState.LISTENING);
    expect(listenBtn.textContent).toBe("Stop Listening");
    expect(listenBtn.style.background).toBe(LISTEN_ACTIVE_BG);
    expect(listenBtn.style.animation).toContain("listen-blink");
  });
});
