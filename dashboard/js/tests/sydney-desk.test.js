// Sydney's Agent Management page is Toyota's desk, not a box like it.
//
// Worth a test because the failure is quiet: Sydney once got Mazda's box, which
// looks the same until you reach for the Pause button (missing) or press
// Start (her audio went to a transcriber Toyota never uses).
import { describe, expect, test } from "bun:test";
import { createAgentDetailRenderers } from "../boot/agent-detail-renderers.js";
import { ReceptionistDesk } from "../boot/receptionist-desk.js";
import { SYDNEY_AGENT_ID } from "../implementation/index.js";
import { FakeDocument } from "./_fake-dom.js";

const storage = { getItem: () => null, setItem: () => {} };

function sydneyPage({ backend }) {
  const doc = new FakeDocument();
  const desks = [];
  const fetched = [];
  const { detailRenderers } = createAgentDetailRenderers({
    http: {
      getJSON: async (url) => {
        fetched.push(url);
        return { ok: true, voice_media_backend: backend };
      },
    },
    poller: {},
    speech: { supported: false },
    setAgentTabStatus: () => {},
    getAgentManager: () => ({ agents: [] }),
    storage,
    doc,
    win: {},
    deskFactory: (desk, deps) => {
      desks.push(desk);
      return new ReceptionistDesk(desk, {
        ...deps,
        listenerFactory: () => ({ setCallbacks() {}, state: "idle" }),
        speechFactory: () => ({ supported: false }),
      });
    },
  });
  const am = { current: { id: SYDNEY_AGENT_ID, name: "Sydney" } };
  return { detailRenderers, desks, fetched, am };
}

describe("Sydney's Input Options", () => {
  test("is built from Toyota's ReceptionistDesk, once per agent", () => {
    const { detailRenderers, desks, am } = sydneyPage({ backend: "pipecat" });
    detailRenderers["agent-detail-input-options"](
      am,
      "agent-detail-input-options",
    );
    detailRenderers["agent-detail-input-options"](
      am,
      "agent-detail-input-options",
    );
    expect(desks).toHaveLength(1);
    expect(desks[0].name).toBe("Sydney");
    expect(desks[0].conversationAgent.endpoint).toBe("/api/sydney-turn");
  });

  test("records through the voice pilot once the server admits her", async () => {
    const { detailRenderers, desks, fetched, am } = sydneyPage({
      backend: "pipecat",
    });
    detailRenderers["agent-detail-input-options"](
      am,
      "agent-detail-input-options",
    );
    expect(desks[0].pipecatSelected()).toBe(false);
    await Promise.resolve();
    await Promise.resolve();
    expect(fetched).toEqual([
      `/api/voice-media-backend?agent=${SYDNEY_AGENT_ID}`,
    ]);
    expect(desks[0].pipecatSelected()).toBe(true);
  });

  test("stays on the default recorder when the server says whisper", async () => {
    const { detailRenderers, desks, am } = sydneyPage({ backend: "whisper" });
    detailRenderers["agent-detail-input-options"](
      am,
      "agent-detail-input-options",
    );
    await Promise.resolve();
    await Promise.resolve();
    expect(desks[0].pipecatSelected()).toBe(false);
  });
});

describe("ReceptionistDesk", () => {
  const descriptor = (pipecatSelected) => ({
    name: "Sydney",
    agentId: SYDNEY_AGENT_ID,
    boxId: "box",
    conversationAgent: { endpoint: "/api/sydney-turn" },
    intentPolicy: { evaluate: async () => ({ addressed: false }) },
    pipecatSelected,
  });

  test("gives every render the same Pause gate, voice and listener", () => {
    const voice = { kind: "her own voice" };
    const desk = new ReceptionistDesk(descriptor(false), {
      http: {},
      storage,
      doc: new FakeDocument(),
      win: {},
      listenerFactory: () => ({ kind: "listener" }),
      speechFactory: () => voice,
    });
    const first = desk.rendererOptions();
    const second = desk.rendererOptions();
    expect(first.playbackControl).toBeTruthy();
    expect(first.playbackControl.paused).toBe(true);
    expect(second.playbackControl).toBe(first.playbackControl);
    expect(first.speech).toBe(voice);
    expect(second.listener).toBe(first.listener);
    expect(second.voiceSession).toBe(first.voiceSession);
    expect(first.agentName).toBe("Sydney");
  });

  test("asks pipecatSelected per recording, not once at construction", () => {
    let selected = false;
    const seen = [];
    new ReceptionistDesk(
      descriptor(() => selected),
      {
        http: {},
        storage,
        doc: new FakeDocument(),
        win: {},
        listenerFactory: () => ({}),
        speechFactory: () => ({}),
        recorderFactoryBuilder: (_id, _storage, { serverSelected }) => {
          seen.push(serverSelected);
          return () => ({});
        },
      },
    );
    expect(seen[0]()).toBe(false);
    selected = true;
    expect(seen[0]()).toBe(true);
  });
});
