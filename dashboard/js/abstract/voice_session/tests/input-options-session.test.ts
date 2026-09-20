import { describe, expect, test } from "bun:test";
import { AgentEventKind } from "../../../abstract/conversation-agent.interface.js";
import { SpokenOutputPolicy } from "../../../abstract/spoken-output-policy.js";
import { createAgentDetailRenderers } from "../../../boot/agent-detail-renderers.js";
import { InputOptionsRenderer } from "../../../implementation/detail-renderers.js";
import { FakeDocument } from "../../../tests/_fake-dom.js";
import { VoiceSession } from "../src/voice-session.ts";

function deferred() {
  let resolve!: () => void;
  const promise = new Promise<void>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

function build() {
  const doc = new FakeDocument();
  const container = doc.createElement("section");
  container.id = "input-options";
  const session = new VoiceSession();
  const policy = new SpokenOutputPolicy({ session });
  const entered = deferred();
  const release = deferred();
  const submitted: string[] = [];
  const spoken: string[] = [];
  const conversationAgent = {
    async *submit(_turn: unknown, generationId: string) {
      submitted.push(generationId);
      entered.resolve();
      await release.promise;
      yield {
        kind: AgentEventKind.ASSISTANT_TEXT,
        text: "The old answer arrived late.",
        generationId,
      };
    },
    cancel(_generationId: string) {},
  };
  const storage = { getItem: () => null, setItem: () => {} };
  const renderer = new InputOptionsRenderer({
    http: {
      getJSON: async () => ({ ok: false, options: [] }),
      postJSON: async () => ({ ok: true }),
    },
    conversationAgent,
    voiceSession: session,
    spokenOutputPolicy: policy,
    speech: {
      supported: true,
      speak: (text: string) => {
        spoken.push(text);
        return { pending: Promise.resolve("speech") };
      },
    },
    agentName: "Mazda",
    doc,
    storage,
    recorderFactory: () => ({ isRecording: false }),
  });
  const ui = renderer.render("input-options", "agent-mazda");
  if (!ui) throw new Error("Input Options did not render");
  return { session, entered, release, submitted, spoken, ui };
}

describe("Input Options voice session", () => {
  test("an interrupted turn's late reply never reaches speech", async () => {
    const { session, entered, release, submitted, spoken, ui } = build();
    // A prior turn is in flight when the renderer is rebuilt. The new Send
    // should supersede it using this same session, then carry its new id.
    session.startListening();
    session.beginTurn();

    const sending = ui.send({ textOverride: "Ask about April" });
    await entered.promise;
    const interrupted = session.interrupt();
    release.resolve();
    await sending;

    expect(spoken).toEqual([]);
    expect(submitted).toEqual([interrupted]);
  });

  test("closing a session while an answer is pending keeps it silent", async () => {
    const { session, entered, release, spoken, ui } = build();
    const sending = ui.send({ textOverride: "Ask about March" });
    await entered.promise;
    session.close();
    release.resolve();
    await sending;

    expect(spoken).toEqual([]);
  });

  test("a current answer is spoken and its turn is completed", async () => {
    const { session, entered, release, spoken, ui } = build();
    const sending = ui.send({ textOverride: "Ask about April" });
    await entered.promise;
    release.resolve();
    await sending;
    await Promise.resolve();

    expect(spoken).toEqual(["The old answer arrived late."]);
    expect(session.currentGeneration).toBeNull();
  });

  test("a renderer rebuild keeps the session fence for the prior reply", async () => {
    const doc = new FakeDocument();
    const container = doc.createElement("section");
    container.id = "input-options";
    doc.add(container);
    const firstEntered = deferred();
    const releaseFirst = deferred();
    const spoken: string[] = [];
    const saved = new Map<string, string>();
    let calls = 0;
    const http = {
      getJSON: async () => ({ ok: false, options: [] }),
      postJSON: async (url: string) => {
        if (url !== "/api/letta-code-message") return { ok: true };
        calls += 1;
        if (calls === 1) {
          firstEntered.resolve();
          await releaseFirst.promise;
          return {
            ok: true,
            reply: "March answer",
            run: { conversation_id: "march" },
          };
        }
        return {
          ok: true,
          reply: "April answer",
          run: { conversation_id: "april" },
        };
      },
    };
    const { detailRenderers } = createAgentDetailRenderers({
      http,
      poller: { stop() {} },
      speech: {
        supported: true,
        speak: (text: string) => {
          spoken.push(text);
          return { pending: Promise.resolve("speech") };
        },
      },
      setAgentTabStatus() {},
      getAgentManager: () => ({ agents: [] }),
      storage: {
        getItem: (key: string) => saved.get(key) ?? null,
        setItem: (key: string, value: string) => {
          saved.set(key, value);
        },
      },
      doc,
    });
    const render = () =>
      detailRenderers["agent-detail-input-options"](
        { current: { id: "agent-mazda", name: "Mazda" } },
        "input-options",
      );
    const first = render().send({ textOverride: "March" });
    await firstEntered.promise;
    const second = render().send({ textOverride: "April" });
    await second;
    releaseFirst.resolve();
    await first;

    expect(spoken).toEqual(["April answer"]);
    expect(saved.get("msi-conv-agent-mazda")).toBe("april");
  });
});
