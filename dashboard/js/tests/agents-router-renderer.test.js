import { describe, expect, test } from "bun:test";
import { ListenerState } from "../abstract/continuous-listener.interface.js";
import { RecorderState } from "../abstract/voice-recorder.interface.js";
import { AgentsRouterRenderer } from "../implementation/agents-router-renderer.js";
import { FakeDocument } from "./_fake-dom.js";

/** Test double standing in for the long-lived listener singleton. */
class FakeListener {
  constructor() {
    this.state = ListenerState.IDLE;
    this._onStateChange = () => {};
    this._onResult = () => {};
    this.startCalls = 0;
    this.stopCalls = 0;
  }
  get isListening() {
    return this.state === ListenerState.LISTENING;
  }
  setCallbacks({ onStateChange, onResult }) {
    if (onStateChange) this._onStateChange = onStateChange;
    if (onResult) this._onResult = onResult;
  }
  async start() {
    this.startCalls += 1;
    this.state = ListenerState.LISTENING;
    this._onStateChange(this.state);
    return true;
  }
  stop() {
    this.stopCalls += 1;
    this.state = ListenerState.IDLE;
    this._onStateChange(this.state);
  }
  /** Test helper: simulate a recognized chunk. */
  emit(text, isFinal) {
    this._onResult(text, isFinal);
  }
}

function routerSetup({
  routeDetectResult = { ok: true, agent: null, remainder: "" },
  agents = { Suzuki: "agent-suzuki" },
} = {}) {
  const doc = new FakeDocument();
  const container = doc.createElement("section");
  container.id = "agents-home-status";

  const posts = [];
  const gets = [];
  const http = {
    getJSON: async (url) => {
      gets.push(url);
      if (url === "/api/router-agent") {
        return { ok: true, agent_id: "agent-router-x" };
      }
      return { ok: false, options: [] }; // /api/agent-model default
    },
    postJSON: async (url, body) => {
      posts.push({ url, body });
      if (url === "/api/route-detect") return routeDetectResult;
      if (url === "/api/agent-model") return { ok: true, model: body.model };
      return { ok: false };
    },
  };

  const listener = new FakeListener();

  const openedAgents = [];
  const agentApis = new Map();
  const openAgent = async (id) => {
    openedAgents.push(id);
    if (!agentApis.has(id)) {
      const calls = { setText: [], appendText: [] };
      agentApis.set(id, {
        _calls: calls,
        setText: (t) => calls.setText.push(t),
        appendText: (t) => calls.appendText.push(t),
      });
    }
    return agentApis.get(id);
  };

  const resolveAgentId = (name) => agents[name] || null;

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
        opts.onStateChange(RecorderState.RECORDING);
        return true;
      },
      stop: async () => {
        recording = false;
        opts.onStateChange(RecorderState.IDLE);
        return { raw_transcript: "hi", cleaned_text: "hi Suzuki" };
      },
    };
    return recorder;
  };

  const statuses = [];
  const r = new AgentsRouterRenderer({
    http,
    listener,
    resolveAgentId,
    openAgent,
    onStatus: (agentId, status) => statuses.push({ agentId, status }),
    doc,
    recorderFactory,
  });
  const api = r.render("agents-home-status");

  return {
    doc,
    container,
    http,
    posts,
    gets,
    listener,
    openedAgents,
    agentApis,
    statuses,
    api,
    get recorder() {
      return recorder;
    },
  };
}

describe("AgentsRouterRenderer (Strategy)", () => {
  test("renders the expected controls and no Copy to Clipboard button", () => {
    const ctx = routerSetup();
    expect(ctx.container.querySelector(".am-test-input")).not.toBeNull();
    const buttons = ctx.container
      .querySelectorAll("button")
      .map((b) => b.textContent);
    expect(buttons).toContain("Send");
    expect(buttons).toContain("Start Recording");
    expect(buttons).toContain("Start Listening");
    expect(buttons).toContain("Auto Send");
    expect(buttons).not.toContain("Copy to Clipboard");
  });

  test("model dropdown resolves the router agent's real id first", async () => {
    const ctx = routerSetup();
    await Promise.resolve();
    await Promise.resolve();
    expect(ctx.gets).toContain("/api/router-agent");
    expect(ctx.gets).toContain("/api/agent-model?agent=agent-router-x");
  });

  test("manual Send with no agent detected shows an error and does not route", async () => {
    const ctx = routerSetup({
      routeDetectResult: { ok: true, agent: null, remainder: "" },
    });
    ctx.container.querySelector(".am-test-input").value = "just thinking aloud";
    await ctx.api.runDetection("just thinking aloud", { manual: true });
    expect(ctx.openedAgents).toEqual([]);
    expect(ctx.statuses).toEqual([]);
  });

  test("manual Send with an agent detected routes and hands off the remainder", async () => {
    const ctx = routerSetup({
      routeDetectResult: {
        ok: true,
        agent: "Suzuki",
        remainder: "check the undo logic",
      },
    });
    const input = ctx.container.querySelector(".am-test-input");
    input.value = "background, Suzuki, check the undo logic";
    await ctx.api.runDetection(input.value, { manual: true });
    expect(ctx.openedAgents).toEqual(["agent-suzuki"]);
    const suzukiApi = ctx.agentApis.get("agent-suzuki");
    expect(suzukiApi._calls.setText).toEqual(["check the undo logic"]);
    expect(input.value).toBe(""); // router box cleared once routed
  });

  test("continuous listening auto-routes on a final chunk without a Send click", async () => {
    const ctx = routerSetup({
      routeDetectResult: {
        ok: true,
        agent: "Suzuki",
        remainder: "check the undo logic",
      },
    });
    ctx.listener.emit("background, Suzuki, check the undo logic", true);
    await Promise.resolve();
    await Promise.resolve();
    expect(ctx.openedAgents).toEqual(["agent-suzuki"]);
  });

  test("continuous listening routes to Mazda and keeps the mic on", async () => {
    const ctx = routerSetup({
      routeDetectResult: {
        ok: true,
        agent: "Mazda",
        remainder: "",
      },
      agents: { Mazda: "agent-mazda" },
    });
    const listenBtn = ctx.container.querySelectorAll("button")[2];
    await listenBtn._listeners.click[0]();
    expect(ctx.listener.isListening).toBe(true);

    ctx.listener.emit("can we talk to Mazda", true);
    await Promise.resolve();
    await Promise.resolve();

    expect(ctx.openedAgents).toEqual(["agent-mazda"]);
    expect(ctx.listener.isListening).toBe(true);
    expect(listenBtn.textContent).toBe("Stop Listening");
  });

  test("continuous listening stays quiet (no error) when nothing matches yet", async () => {
    const ctx = routerSetup({
      routeDetectResult: { ok: true, agent: null, remainder: "" },
    });
    ctx.listener.emit("I was thinking about the scoreboard", true);
    await Promise.resolve();
    await Promise.resolve();
    expect(ctx.openedAgents).toEqual([]);
    // No manual-only error status was raised for background speech.
    const errorPost = ctx.posts.find((p) => p.url === "/api/route-detect");
    expect(errorPost).toBeDefined(); // it did classify, just found nothing
  });

  test("interim (non-final) results are not classified", async () => {
    const ctx = routerSetup();
    ctx.listener.emit("Suzuki", false);
    await Promise.resolve();
    expect(ctx.posts.filter((p) => p.url === "/api/route-detect")).toEqual([]);
  });

  test("after routing, further final chunks append to the agent instead of re-classifying", async () => {
    const ctx = routerSetup({
      routeDetectResult: {
        ok: true,
        agent: "Suzuki",
        remainder: "check the undo logic",
      },
    });
    ctx.listener.emit("Suzuki, check the undo logic", true);
    await Promise.resolve();
    await Promise.resolve();
    expect(ctx.openedAgents).toEqual(["agent-suzuki"]);

    const detectCallsBefore = ctx.posts.filter(
      (p) => p.url === "/api/route-detect",
    ).length;
    ctx.listener.emit("also check the animation timing", true);
    await Promise.resolve();

    expect(ctx.posts.filter((p) => p.url === "/api/route-detect").length).toBe(
      detectCallsBefore,
    ); // no re-classification
    const suzukiApi = ctx.agentApis.get("agent-suzuki");
    expect(suzukiApi._calls.appendText).toEqual([
      "also check the animation timing",
    ]);
  });

  test("Start Recording and Start Listening are mutually exclusive", async () => {
    const ctx = routerSetup();
    const recordBtn = ctx.container.querySelectorAll("button")[1];
    const listenBtn = ctx.container.querySelectorAll("button")[2];
    expect(recordBtn.textContent).toBe("Start Recording");
    expect(listenBtn.textContent).toBe("Start Listening");

    await recordBtn._listeners.click[0]();
    expect(ctx.recorder.isRecording).toBe(true);
    expect(listenBtn.disabled).toBe(true);

    await recordBtn._listeners.click[0](); // stop recording
    expect(listenBtn.disabled).toBe(false);

    await listenBtn._listeners.click[0]();
    expect(ctx.listener.isListening).toBe(true);
    expect(recordBtn.disabled).toBe(true);
  });

  test("Auto Send routes automatically after a completed recording", async () => {
    const ctx = routerSetup({
      routeDetectResult: {
        ok: true,
        agent: "Suzuki",
        remainder: "check the undo logic",
      },
    });
    const buttons = ctx.container.querySelectorAll("button");
    const recordBtn = buttons[1];
    const autoSendBtn = buttons.find((b) => b.textContent === "Auto Send");
    autoSendBtn.click();
    await recordBtn._listeners.click[0](); // start
    await recordBtn._listeners.click[0](); // stop -> transcribes -> auto-routes
    expect(ctx.openedAgents).toEqual(["agent-suzuki"]);
  });
});
