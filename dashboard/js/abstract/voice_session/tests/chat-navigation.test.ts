import { describe, expect, test } from "bun:test";
import { createAgentDetailRenderers } from "../../../boot/agent-detail-renderers.js";
import { FakeDocument } from "../../../tests/_fake-dom.js";

function deferred<T = void>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

function setup(http: object, speech: object) {
  const doc = new FakeDocument();
  const container = doc.createElement("section");
  container.id = "chat";
  doc.add(container);
  const boot = createAgentDetailRenderers({
    http,
    poller: { stop() {} },
    speech,
    setAgentTabStatus() {},
    getAgentManager: () => ({ agents: [] }),
    storage: { getItem: () => "1", setItem() {} },
    doc,
  });
  const render = () =>
    boot.detailRenderers["agent-detail-tests"](
      { current: { id: "agent-scissari", name: "Scissari" } },
      "chat",
    );
  return { ...boot, render, container };
}

describe("Chat navigation", () => {
  test("leaving Chat cancels a pending reply before it reaches speech", async () => {
    const entered = deferred();
    const release = deferred();
    const spoken: string[] = [];
    const ctx = setup(
      {
        postJSON: async () => {
          entered.resolve();
          await release.promise;
          return { replies: [{ type: "assistant_message", text: "late" }] };
        },
      },
      {
        supported: true,
        speak: (text: string) => {
          spoken.push(text);
        },
        cancel() {},
      },
    );
    const ui = ctx.render();
    const sending = ui.sendText("old question");
    await entered.promise;
    ctx.interruptVoiceTurns();
    release.resolve();
    await sending;
    expect(spoken).toEqual([]);
    expect(ctx.container.querySelector(".msi-inner").innerHTML).not.toContain(
      "late",
    );
  });

  test("leaving Chat stops the audio owned by its current turn", async () => {
    const finished = deferred();
    let cancellations = 0;
    const ctx = setup(
      {
        postJSON: async () => ({
          replies: [{ type: "assistant_message", text: "answer" }],
        }),
      },
      {
        supported: true,
        speak: () => ({
          pending: Promise.resolve("edge-tts"),
          finished: finished.promise,
          cancel: () => {
            cancellations += 1;
            finished.resolve();
          },
        }),
        cancel() {},
      },
    );
    await ctx.render().sendText("question");
    ctx.interruptVoiceTurns();
    ctx.interruptVoiceTurns();
    expect(cancellations).toBe(1);
  });
});
