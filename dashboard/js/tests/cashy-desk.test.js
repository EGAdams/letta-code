// Cashy's Agent Management page is the same ReceptionistDesk Toyota's and
// Sydney's are, talking to her own sidecar through /api/cashy-turn.
import { describe, expect, test } from "bun:test";
import { createAgentDetailRenderers } from "../boot/agent-detail-renderers.js";
import { ReceptionistDesk } from "../boot/receptionist-desk.js";
import { AGENT_WINDOWS } from "../implementation/agent-window-handoff.js";
import { CASHY_AGENT_ID } from "../implementation/index.js";
import { FakeDocument } from "./_fake-dom.js";

const storage = { getItem: () => null, setItem: () => {} };

function cashyPage() {
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
  const am = { current: { id: CASHY_AGENT_ID, name: "Cashy" } };
  return { detailRenderers, desks, fetched, am };
}

describe("Cashy's Input Options", () => {
  test("is Toyota's ReceptionistDesk on her own endpoint, once per agent", () => {
    const { detailRenderers, desks, fetched, am } = cashyPage();
    detailRenderers["agent-detail-input-options"](
      am,
      "agent-detail-input-options",
    );
    detailRenderers["agent-detail-input-options"](
      am,
      "agent-detail-input-options",
    );
    expect(desks).toHaveLength(1);
    expect(desks[0].name).toBe("Cashy");
    expect(desks[0].conversationAgent.endpoint).toBe("/api/cashy-turn");
    expect(desks[0].pipecatSelected()).toBe(false);
    expect(fetched).not.toContain(
      `/api/voice-media-backend?agent=${CASHY_AGENT_ID}`,
    );
  });

  test("other agents can open her window", () => {
    expect(AGENT_WINDOWS.cashy.url).toBe(
      `/?agent=${CASHY_AGENT_ID}&view=input-options`,
    );
    expect(AGENT_WINDOWS.cashy.windowName).toBe("rol-agent-cashy");
  });
});
