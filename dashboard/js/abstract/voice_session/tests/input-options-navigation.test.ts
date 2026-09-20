import { describe, expect, test } from "bun:test";
import { createAgentDetailRenderers } from "../../../boot/agent-detail-renderers.js";
import { FakeDocument } from "../../../tests/_fake-dom.js";

function deferred() {
  let resolve!: () => void;
  const promise = new Promise<void>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

describe("Input Options renderer navigation", () => {
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

  test("leaving Input Options interrupts audio from the current agent", async () => {
    const doc = new FakeDocument();
    const container = doc.createElement("section");
    container.id = "input-options";
    doc.add(container);
    const finished = deferred();
    let cancellations = 0;
    const { detailRenderers, interruptVoiceTurns } = createAgentDetailRenderers(
      {
        http: {
          getJSON: async () => ({ ok: false, options: [] }),
          postJSON: async () => ({
            ok: true,
            reply: "April answer",
            run: { conversation_id: "april" },
          }),
        },
        poller: { stop() {} },
        speech: {
          supported: true,
          speak: () => ({
            pending: Promise.resolve("edge-tts"),
            finished: finished.promise,
            cancel: () => {
              cancellations += 1;
              finished.resolve();
            },
          }),
        },
        setAgentTabStatus() {},
        getAgentManager: () => ({ agents: [] }),
        storage: { getItem: () => null, setItem() {} },
        doc,
      },
    );
    const ui = detailRenderers["agent-detail-input-options"](
      { current: { id: "agent-mazda", name: "Mazda" } },
      "input-options",
    );
    await ui.send({ textOverride: "April" });
    interruptVoiceTurns();
    interruptVoiceTurns();
    expect(cancellations).toBe(1);
  });
});
