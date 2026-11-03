// Yolanda's Agent Management page is the same ReceptionistDesk Toyota's and
// Sydney's are, talking to her own sidecar through /api/yolanda-turn.
import { describe, expect, test } from "bun:test";
import { createAgentDetailRenderers } from "../boot/agent-detail-renderers.js";
import { ReceptionistDesk } from "../boot/receptionist-desk.js";
import { AGENT_WINDOWS } from "../implementation/agent-window-handoff.js";
import { YOLANDA_AGENT_ID } from "../implementation/index.js";
import { FakeDocument } from "./_fake-dom.js";

const storage = { getItem: () => null, setItem: () => {} };

function yolandaPage() {
  const doc = new FakeDocument();
  const desks = [];
  const fetched = [];
  const { detailRenderers } = createAgentDetailRenderers({
    http: {
      getJSON: async (url) => {
        fetched.push(url);
        return { ok: true };
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
  const am = { current: { id: YOLANDA_AGENT_ID, name: "Yolanda" } };
  return { detailRenderers, desks, fetched, am };
}

describe("Yolanda's Input Options", () => {
  test("is Toyota's ReceptionistDesk on her own endpoint, once per agent", () => {
    const { detailRenderers, desks, fetched, am } = yolandaPage();
    detailRenderers["agent-detail-input-options"](
      am,
      "agent-detail-input-options",
    );
    detailRenderers["agent-detail-input-options"](
      am,
      "agent-detail-input-options",
    );
    expect(desks).toHaveLength(1);
    expect(desks[0].name).toBe("Yolanda");
    expect(desks[0].conversationAgent.endpoint).toBe("/api/yolanda-turn");
    expect(desks[0].pipecatSelected()).toBe(false);
    expect(fetched).not.toContain(
      `/api/voice-media-backend?agent=${YOLANDA_AGENT_ID}`,
    );
  });

  test("other agents can open her window", () => {
    expect(AGENT_WINDOWS.yolanda.url).toBe(
      `/?agent=${YOLANDA_AGENT_ID}&view=input-options`,
    );
    expect(AGENT_WINDOWS.yolanda.windowName).toBe("rol-agent-yolanda");
  });
});
