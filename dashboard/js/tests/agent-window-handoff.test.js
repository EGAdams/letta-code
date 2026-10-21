import { describe, expect, test } from "bun:test";
import { AgentEventKind } from "../abstract/conversation-agent.interface.js";
import {
  AGENT_WINDOWS,
  AgentWindowHandoff,
  BrowserAgentWindows,
  wakePhraseIntentPolicy,
} from "../implementation/agent-window-handoff.js";
import { FakeConversationAgent } from "../implementation/fake-conversation-agent.js";
import { FakeDocument } from "./_fake-dom.js";
import { runConversationAgentContract } from "./conversation-agent-contract.js";

const quiet = { show() {} };

runConversationAgentContract(
  "AgentWindowHandoff",
  (replyText) =>
    new AgentWindowHandoff(
      new FakeConversationAgent({
        events: [{ kind: AgentEventKind.ASSISTANT_TEXT, text: replyText }],
      }),
      quiet,
    ),
);

const handoffEvents = (agent) => [
  {
    kind: AgentEventKind.TOOL_RESULT,
    name: "agent_handoff",
    detail: { handoff: { agent, name: agent } },
  },
  { kind: AgentEventKind.ASSISTANT_TEXT, text: "Opening it now." },
];

async function drain(agent) {
  const kinds = [];
  for await (const e of agent.submit({ agent: "a", text: "hi" }, "gen-1"))
    kinds.push(e.kind);
  return kinds;
}

describe("AgentWindowHandoff", () => {
  test("shows the named agent and still passes every event through", async () => {
    const shown = [];
    const agent = new AgentWindowHandoff(
      new FakeConversationAgent({ events: handoffEvents("mazda") }),
      { show: (h) => shown.push(h) },
    );
    expect(await drain(agent)).toEqual([
      "tool_result",
      "assistant_text",
      "terminal",
    ]);
    expect(shown).toEqual([{ agent: "mazda", name: "mazda" }]);
  });

  test("a failing window opener never breaks the spoken reply", async () => {
    const agent = new AgentWindowHandoff(
      new FakeConversationAgent({ events: handoffEvents("mazda") }),
      {
        show() {
          throw new Error("blocked");
        },
      },
    );
    expect(await drain(agent)).toContain("assistant_text");
  });

  test("other tool results do not open windows", async () => {
    const shown = [];
    const agent = new AgentWindowHandoff(
      new FakeConversationAgent({
        events: [
          { kind: AgentEventKind.TOOL_RESULT, name: "receptionist_work" },
        ],
      }),
      { show: (h) => shown.push(h) },
    );
    await drain(agent);
    expect(shown).toEqual([]);
  });
});

function fakeWindow({ blocked = false, existing = false, opener = null } = {}) {
  const calls = [];
  const opened = {
    location: { href: existing ? "/already-here" : "about:blank" },
    focused: false,
    focus() {
      this.focused = true;
    },
  };
  return {
    calls,
    opened,
    opener,
    open(url, name) {
      calls.push([url, name]);
      return blocked ? null : opened;
    },
  };
}

describe("BrowserAgentWindows", () => {
  test("opens a fresh window at the agent's page", () => {
    const win = fakeWindow();
    new BrowserAgentWindows({ win, doc: new FakeDocument(), boxId: "b" }).show({
      agent: "mazda",
      name: "Mazda",
    });
    expect(win.calls).toEqual([["", "rol-agent-mazda"]]);
    expect(win.opened.location.href).toBe(AGENT_WINDOWS.mazda.url);
    expect(win.opened.focused).toBe(true);
  });

  test("focuses an already-open window without reloading it", () => {
    const win = fakeWindow({ existing: true });
    new BrowserAgentWindows({ win, doc: new FakeDocument(), boxId: "b" }).show({
      agent: "mazda",
      name: "Mazda",
    });
    expect(win.opened.location.href).toBe("/already-here");
    expect(win.opened.focused).toBe(true);
  });

  test("Mazda's window goes back to the front desk that opened it", () => {
    let focused = false;
    const win = fakeWindow({
      opener: {
        closed: false,
        name: "rol-front-desk",
        focus() {
          focused = true;
        },
      },
    });
    new BrowserAgentWindows({ win, doc: new FakeDocument(), boxId: "b" }).show({
      agent: "toyota",
      name: "Toyota",
    });
    expect(focused).toBe(true);
    expect(win.calls).toEqual([]);
  });

  test("a blocked popup leaves a button that opens it on click", () => {
    const doc = new FakeDocument();
    const box = doc.createElement("section");
    box.id = "b";
    doc.add(box);
    const win = fakeWindow({ blocked: true });
    new BrowserAgentWindows({ win, doc, boxId: "b" }).show({
      agent: "mazda",
      name: "Mazda",
    });
    const button = box.querySelector("button");
    expect(button.textContent).toBe("Open Mazda's window");
    button.click();
    expect(win.calls.at(-1)).toEqual([
      AGENT_WINDOWS.mazda.url,
      "rol-agent-mazda",
    ]);
  });

  test("an unknown agent is ignored", () => {
    const win = fakeWindow();
    new BrowserAgentWindows({ win, doc: new FakeDocument(), boxId: "b" }).show({
      agent: "nobody",
    });
    expect(win.calls).toEqual([]);
  });
});

describe("wakePhraseIntentPolicy", () => {
  const policy = wakePhraseIntentPolicy("mazda");
  test("hears requests addressed to her", async () => {
    expect(await policy.evaluate("Hey Mazda, put Toyota on the horn")).toEqual({
      addressed: true,
      cleaned_text: "put Toyota on the horn",
    });
  });
  test("ignores everything else", async () => {
    expect((await policy.evaluate("Toyota, open Mazda")).addressed).toBe(false);
    expect((await policy.evaluate("Mazda")).addressed).toBe(false);
  });
});
