// Which brain Toyota's home-screen box talks to.
//
// The server decides (`conversation_backend`) and the boot code turns that into
// one endpoint on one adapter. Worth a test because the failure mode is silent:
// a wrong endpoint means a box that looks fine and answers nothing.
import { describe, expect, test } from "bun:test";
import { startReceptionist } from "../boot/receptionist.js";
import { FakeDocument } from "./_fake-dom.js";

async function bootWith(payload: Record<string, unknown>) {
  const doc = new FakeDocument();
  const container = doc.createElement("section");
  container.id = "receptionist-box";
  doc.add(container);
  let rendererOptions: Record<string, unknown> | undefined;
  await startReceptionist({
    http: {
      getJSON: async () => ({
        ok: true,
        agent_id: "toyota-id",
        name: "Toyota",
        voice_media_backend: "whisper",
        ...payload,
      }),
    },
    speech: { supported: false },
    storage: { getItem: () => null, setItem: () => {} },
    recorderFactoryBuilder: () => () => ({}),
    rendererFactory: (options: Record<string, unknown>) => {
      rendererOptions = options;
      return { render: () => ({}) };
    },
    listenerFactory: () => ({}),
    workAgentFactory: ({ inner }: { inner: unknown }) => ({
      agent: inner,
      mount() {},
    }),
    doc,
  });
  return (rendererOptions?.conversationAgent as { endpoint: string }).endpoint;
}

describe("Toyota's conversation backend", () => {
  test("talks to the receptionist_team sidecar when the server prefers it", async () => {
    expect(await bootWith({ conversation_backend: "receptionist-team" })).toBe(
      "/api/receptionist-turn",
    );
  });

  test("falls back to the Letta stream when the sidecar is down", async () => {
    expect(await bootWith({ conversation_backend: "letta" })).toBe(
      "/api/letta-code-stream",
    );
  });

  test("an older server that reports no backend still gets a working box", async () => {
    expect(await bootWith({})).toBe("/api/letta-code-stream");
  });

  test("an unrecognized backend does not become an unknown route", async () => {
    expect(await bootWith({ conversation_backend: "mazda-team" })).toBe(
      "/api/letta-code-stream",
    );
  });
});
