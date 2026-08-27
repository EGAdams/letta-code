import { describe, expect, test } from "bun:test";
import { AgentEventKind } from "../abstract/conversation-agent.interface.js";
import {
  LETTA_TURN_TIMEOUT_MS,
  LettaAgentAdapter,
} from "../implementation/letta-agent-adapter.js";
import { runConversationAgentContract } from "./conversation-agent-contract.js";

/** Records every POST and answers with a scripted reply. */
function fakeHttp(reply) {
  const posts = [];
  return {
    posts,
    postJSON: async (url, body, opts) => {
      posts.push({ url, body, opts });
      return typeof reply === "function" ? reply(body) : reply;
    },
  };
}

function makeStorage(initial = {}) {
  const store = { ...initial };
  return {
    store,
    getItem: (k) => (k in store ? store[k] : null),
    setItem: (k, v) => {
      store[k] = v;
    },
  };
}

runConversationAgentContract(
  "LettaAgentAdapter",
  (replyText) =>
    new LettaAgentAdapter({ http: fakeHttp({ ok: true, reply: replyText }) }),
);

const drain = async (agent, turn, gen) => {
  const events = [];
  for await (const e of agent.submit(turn, gen)) events.push(e);
  return events;
};

describe("LettaAgentAdapter — the call the renderers used to make by hand", () => {
  test("posts the shape the endpoint expects, with the 930s budget", async () => {
    // Characterization: this pins today's request so the port can be adopted
    // without changing what the server sees.
    const http = fakeHttp({ ok: true, reply: "hi" });
    const adapter = new LettaAgentAdapter({ http });
    await drain(adapter, { agent: "agent-7", text: "hello" }, "gen-1");

    expect(http.posts).toHaveLength(1);
    expect(http.posts[0].url).toBe("/api/letta-code-message");
    expect(http.posts[0].body).toEqual({
      agent: "agent-7",
      text: "hello",
      conversation_id: null,
    });
    expect(http.posts[0].opts).toEqual({ timeout: LETTA_TURN_TIMEOUT_MS });
    expect(LETTA_TURN_TIMEOUT_MS).toBe(930000);
  });

  test("a reply becomes assistant text then terminal", async () => {
    const adapter = new LettaAgentAdapter({
      http: fakeHttp({ ok: true, reply: "we spent $412" }),
    });
    const events = await drain(adapter, { agent: "a", text: "?" }, "gen-1");
    expect(events.map((e) => e.kind)).toEqual([
      AgentEventKind.ASSISTANT_TEXT,
      AgentEventKind.TERMINAL,
    ]);
    expect(events[0].text).toBe("we spent $412");
  });

  test("remembers the conversation so the next turn resumes it", async () => {
    const storage = makeStorage();
    const http = fakeHttp({
      ok: true,
      reply: "hi",
      run: { conversation_id: "conv-42" },
    });
    const adapter = new LettaAgentAdapter({ http, storage });

    await drain(adapter, { agent: "agent-7", text: "one" }, "gen-1");
    expect(storage.store["msi-conv-agent-7"]).toBe("conv-42");

    await drain(adapter, { agent: "agent-7", text: "two" }, "gen-2");
    expect(http.posts[1].body.conversation_id).toBe("conv-42");
  });

  test("conversations are per agent, not global", async () => {
    const storage = makeStorage({ "msi-conv-agent-7": "conv-42" });
    const http = fakeHttp({ ok: true, reply: "hi" });
    const adapter = new LettaAgentAdapter({ http, storage });
    await drain(adapter, { agent: "agent-9", text: "?" }, "gen-1");
    expect(http.posts[0].body.conversation_id).toBeNull();
  });

  test("an explicit conversation id on the turn wins over the stored one", async () => {
    const storage = makeStorage({ "msi-conv-agent-7": "conv-42" });
    const http = fakeHttp({ ok: true, reply: "hi" });
    const adapter = new LettaAgentAdapter({ http, storage });
    await drain(
      adapter,
      { agent: "agent-7", text: "?", conversationId: "conv-99" },
      "gen-1",
    );
    expect(http.posts[0].body.conversation_id).toBe("conv-99");
  });

  test("without storage every turn starts fresh", async () => {
    const http = fakeHttp({
      ok: true,
      reply: "hi",
      run: { conversation_id: "conv-42" },
    });
    const adapter = new LettaAgentAdapter({ http });
    await drain(adapter, { agent: "a", text: "one" }, "gen-1");
    await drain(adapter, { agent: "a", text: "two" }, "gen-2");
    expect(http.posts[1].body.conversation_id).toBeNull();
  });

  test("ok:false surfaces the server's error", async () => {
    const adapter = new LettaAgentAdapter({
      http: fakeHttp({ ok: false, error: "agent is busy" }),
    });
    await expect(
      drain(adapter, { agent: "a", text: "?" }, "gen-1"),
    ).rejects.toThrow("agent is busy");
  });

  test("ok:true with no reply is an error, not a silent empty turn", async () => {
    const adapter = new LettaAgentAdapter({
      http: fakeHttp({ ok: true, reply: "" }),
    });
    await expect(
      drain(adapter, { agent: "a", text: "?" }, "gen-1"),
    ).rejects.toThrow("Mazda returned no answer.");
  });

  test("a failed turn does not overwrite the remembered conversation", async () => {
    const storage = makeStorage({ "msi-conv-agent-7": "conv-42" });
    const adapter = new LettaAgentAdapter({
      http: fakeHttp({
        ok: false,
        error: "nope",
        run: { conversation_id: "x" },
      }),
      storage,
    });
    await expect(
      drain(adapter, { agent: "agent-7", text: "?" }, "gen-1"),
    ).rejects.toThrow("nope");
    expect(storage.store["msi-conv-agent-7"]).toBe("conv-42");
  });

  test("refuses an empty turn or one with no agent before touching the network", async () => {
    const http = fakeHttp({ ok: true, reply: "hi" });
    const adapter = new LettaAgentAdapter({ http });
    await expect(
      drain(adapter, { agent: "a", text: "  " }, "g"),
    ).rejects.toThrow("nothing to send");
    await expect(drain(adapter, { text: "hi" }, "g")).rejects.toThrow(
      "needs an agent id",
    );
    expect(http.posts).toHaveLength(0);
  });

  test("cancelling after the request is sent suppresses delivery", async () => {
    // There is no server-side cancel for this endpoint, so the guarantee is
    // narrower than it looks: the work still runs, the answer is just dropped.
    const http = fakeHttp({ ok: true, reply: "stale answer" });
    const adapter = new LettaAgentAdapter({ http });
    adapter.cancel("gen-1");
    await expect(
      drain(adapter, { agent: "a", text: "?" }, "gen-1"),
    ).rejects.toThrow("was cancelled");
    expect(http.posts).toHaveLength(1);
  });

  test("requires an HttpClient", () => {
    expect(() => new LettaAgentAdapter({})).toThrow("requires an HttpClient");
  });
});
